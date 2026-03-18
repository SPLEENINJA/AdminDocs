# =============================================================================
# Mock OCR Service – FastAPI
# Simule l'extraction de texte à partir d'un document (PDF, image).
# En production, ce service serait remplacé par le vrai module OCR du groupe.
# =============================================================================

from fastapi import FastAPI, UploadFile, File
from fastapi.responses import JSONResponse
import uuid
from datetime import datetime

app = FastAPI(title="Mock OCR Service", version="1.0.0")


@app.get("/health")
def health():
    """Endpoint de santé pour Docker healthcheck."""
    return {"status": "ok", "service": "ocr-service"}


@app.post("/extract")
async def extract_text(file: UploadFile = File(...)):
    """
    Simule l'extraction OCR d'un document uploadé.
    
    En entrée : un fichier (PDF, image, etc.)
    En sortie : un JSON avec le texte extrait (simulé) et des métadonnées.
    """
    # Lire le contenu du fichier pour simuler un traitement
    content = await file.read()
    file_size = len(content)

    # Résultat OCR simulé (mock réaliste)
    result = {
        "ocr_id": str(uuid.uuid4()),
        "filename": file.filename,
        "file_size_bytes": file_size,
        "extracted_at": datetime.utcnow().isoformat(),
        "confidence": 0.94,
        "language": "fr",
        "extracted_text": (
            "RÉPUBLIQUE FRANÇAISE\n"
            "CARTE NATIONALE D'IDENTITÉ N° 1234567890\n"
            "Nom : DUPONT\n"
            "Prénom(s) : Jean Marie\n"
            "Date de naissance : 15/03/1985\n"
            "Lieu de naissance : PARIS (75)\n"
            "Adresse : 42 Rue des Lilas, 75011 PARIS\n"
            "Date de délivrance : 01/06/2020\n"
            "Date d'expiration : 01/06/2030\n"
        ),
        "fields": {
            "nom": "DUPONT",
            "prenom": "Jean Marie",
            "date_naissance": "1985-03-15",
            "lieu_naissance": "PARIS (75)",
            "adresse": "42 Rue des Lilas, 75011 PARIS",
            "numero_document": "1234567890",
            "date_delivrance": "2020-06-01",
            "date_expiration": "2030-06-01",
            "type_document": "CNI"
        }
    }

    return JSONResponse(content=result, status_code=200)


@app.post("/extract/json")
async def extract_text_from_json(payload: dict):
    """
    Variante : reçoit un JSON avec le chemin MinIO du document.
    Utile pour l'appel depuis le DAG Airflow.
    
    Payload attendu :
    {
        "document_key": "raw/doc_xxx.pdf",
        "bucket": "raw"
    }
    """
    document_key = payload.get("document_key", "unknown.pdf")

    result = {
        "ocr_id": str(uuid.uuid4()),
        "source_key": document_key,
        "extracted_at": datetime.utcnow().isoformat(),
        "confidence": 0.91,
        "language": "fr",
        "extracted_text": (
            "RÉPUBLIQUE FRANÇAISE\n"
            "CARTE NATIONALE D'IDENTITÉ N° 9876543210\n"
            "Nom : MARTIN\n"
            "Prénom(s) : Sophie\n"
            "Date de naissance : 22/07/1990\n"
            "Lieu de naissance : LYON (69)\n"
            "Adresse : 10 Avenue Foch, 69003 LYON\n"
        ),
        "fields": {
            "nom": "MARTIN",
            "prenom": "Sophie",
            "date_naissance": "1990-07-22",
            "lieu_naissance": "LYON (69)",
            "adresse": "10 Avenue Foch, 69003 LYON",
            "numero_document": "9876543210",
            "type_document": "CNI"
        }
    }

    return JSONResponse(content=result, status_code=200)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
