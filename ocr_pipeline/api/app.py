"""
api/app.py — API REST FastAPI exposant le pipeline OCR au frontend MERN

Endpoints :
  POST /documents/upload         → Traite 1 ou N fichiers
  GET  /documents                → Liste les derniers documents traités
  GET  /documents/{id}           → Récupère un document par ID
  POST /documents/cross-validate → Vérification croisée inter-documents
  GET  /stats                    → Stats des 3 zones de stockage
  GET  /health                   → Healthcheck

Lancement :
  pip install fastapi uvicorn python-multipart
  uvicorn api.app:app --reload --port 8000
"""
from __future__ import annotations

import sys
import tempfile
import traceback
from pathlib import Path
from typing import List, Optional

# ── Ajout du chemin racine au path ─────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from config import validate_config, LOGS_DIR
from utils.logger import get_logger
from pipeline import process_document, process_batch
from services.storage import list_curated, load_curated, storage_summary
from services.validator import validate_cross

logger = get_logger("ocr_service.api", LOGS_DIR)

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="OCR Service — Hackathon 2026",
    description="Classification et extraction automatique de documents administratifs",
    version="1.0.0",
)

# CORS — à restreindre en production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],      # En prod : ["http://localhost:3000"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Validation config au démarrage ────────────────────────────────────────────
@app.on_event("startup")
async def startup():
    try:
        validate_config()
        logger.info("✓ OCR Service démarré")
    except EnvironmentError as e:
        logger.error(f"Configuration invalide : {e}")


# ── Schémas de réponse ────────────────────────────────────────────────────────

class DocumentResponse(BaseModel):
    document_id:       str
    fichier_source:    str
    type_document:     str
    confiance:         float
    champs:            dict
    qualite_scan:      str
    anomalies:         List[str]
    validation_errors: List[str]
    nb_pages:          Optional[int] = None
    sha256:            Optional[str] = None


class BatchResponse(BaseModel):
    total:     int
    success:   int
    errors:    int
    documents: List[dict]


class CrossValidateRequest(BaseModel):
    document_ids: Optional[List[str]] = None   # None = derniers 50


class StatsResponse(BaseModel):
    raw:     int
    clean:   int
    curated: int


# ── Helpers ───────────────────────────────────────────────────────────────────

ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".webp"}
MAX_FILE_SIZE_MB   = 20


async def _save_upload_temp(upload: UploadFile) -> str:
    """Sauvegarde un UploadFile dans un fichier temporaire et retourne son chemin."""
    suffix = Path(upload.filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail=f"Format non supporté : '{suffix}'. "
                   f"Formats acceptés : {', '.join(ALLOWED_EXTENSIONS)}"
        )

    content = await upload.read()

    if len(content) > MAX_FILE_SIZE_MB * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail=f"Fichier trop volumineux (max {MAX_FILE_SIZE_MB} Mo)"
        )

    with tempfile.NamedTemporaryFile(
        delete=False, suffix=suffix, prefix="ocr_upload_"
    ) as tmp:
        tmp.write(content)
        return tmp.name


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/health", tags=["System"])
async def health():
    """Healthcheck simple."""
    return {"status": "ok", "service": "ocr-service"}


@app.get("/stats", response_model=StatsResponse, tags=["System"])
async def get_stats():
    """Statistiques des 3 zones de stockage."""
    return storage_summary()


@app.post("/documents/upload", tags=["Documents"])
async def upload_documents(files: List[UploadFile] = File(...)):
    """
    Upload et traitement d'un ou plusieurs documents.
    Retourne les résultats extraits (type, champs, anomalies).
    """
    if not files:
        raise HTTPException(status_code=400, detail="Aucun fichier fourni")

    tmp_paths = []
    try:
        # Sauvegarde temporaire de tous les fichiers
        for upload in files:
            tmp_path = await _save_upload_temp(upload)
            tmp_paths.append((tmp_path, upload.filename))

        # Traitement
        if len(tmp_paths) == 1:
            tmp_path, original_name = tmp_paths[0]
            result = process_document(tmp_path, original_filename=original_name)
            return JSONResponse(content=result)
        else:
            paths = [p for p, _ in tmp_paths]
            names = [n for _, n in tmp_paths]
            results = process_batch(paths, original_filenames=names)

            ok     = sum(1 for r in results if "erreur" not in r)
            return JSONResponse(content={
                "total":     len(results),
                "success":   ok,
                "errors":    len(results) - ok,
                "documents": results,
            })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur upload : {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Erreur traitement : {str(e)}")
    finally:
        # Nettoyage fichiers temporaires
        for tmp_path, _ in tmp_paths:
            try:
                Path(tmp_path).unlink(missing_ok=True)
            except Exception:
                pass


@app.get("/documents", tags=["Documents"])
async def list_documents(limit: int = 20):
    """Liste les derniers documents traités (zone Curated)."""
    docs = list_curated(limit=min(limit, 100))
    return {"count": len(docs), "documents": docs}


@app.get("/documents/{document_id}", tags=["Documents"])
async def get_document(document_id: str):
    """Récupère un document par son ID."""
    doc = load_curated(document_id)
    if not doc:
        raise HTTPException(
            status_code=404,
            detail=f"Document '{document_id}' introuvable"
        )
    return doc


@app.post("/documents/cross-validate", tags=["Documents"])
async def cross_validate(body: CrossValidateRequest):
    """
    Vérifie la cohérence inter-documents.
    Si document_ids est null → analyse les 50 derniers documents.
    """
    if body.document_ids:
        docs = []
        for doc_id in body.document_ids:
            doc = load_curated(doc_id)
            if doc:
                docs.append(doc)
            else:
                logger.warning(f"Document '{doc_id}' introuvable pour cross-validation")
    else:
        docs = list_curated(limit=50)

    warnings = validate_cross(docs)
    return {
        "documents_analysed": len(docs),
        "warnings":           warnings,
        "is_coherent":        len(warnings) == 0,
    }


# ── Lancement direct ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.app:app", host="0.0.0.0", port=8000, reload=True)
