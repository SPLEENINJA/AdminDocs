# =============================================================================
# Mock Business Service – FastAPI
# Simule 2 applications métiers :
#   - CRM : enregistrement des données client
#   - Conformité : vérification réglementaire
# =============================================================================

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Dict, Any, Optional, List
import uuid
from datetime import datetime

app = FastAPI(title="Mock Business Service (CRM + Conformité)", version="1.0.0")

# ---------- Stockage en mémoire (pour la démo) ----------
crm_records: List[Dict] = []
conformite_records: List[Dict] = []


# ---------- Modèles ----------
class CRMPayload(BaseModel):
    """Données à envoyer au CRM."""
    document_key: str
    fields: Dict[str, Any]         # Champs extraits par OCR
    analysis_result: Dict[str, Any] # Résultat de l'anomaly detector

class ConformitePayload(BaseModel):
    """Données à envoyer au module Conformité."""
    document_key: str
    fields: Dict[str, Any]
    analysis_result: Dict[str, Any]
    document_type: Optional[str] = "CNI"


# ---------- Health ----------
@app.get("/health")
def health():
    """Endpoint de santé pour Docker healthcheck."""
    return {"status": "ok", "service": "business-service"}


# ---------- CRM ----------
@app.post("/crm/submit")
async def crm_submit(payload: CRMPayload):
    """
    Simule l'auto-remplissage du CRM avec les données extraites.
    
    Le CRM reçoit les données client et crée/met à jour une fiche.
    """
    record = {
        "crm_id": str(uuid.uuid4()),
        "received_at": datetime.utcnow().isoformat(),
        "document_key": payload.document_key,
        "status": "OK",
        "client": {
            "nom": payload.fields.get("nom", "N/A"),
            "prenom": payload.fields.get("prenom", "N/A"),
            "date_naissance": payload.fields.get("date_naissance", "N/A"),
            "adresse": payload.fields.get("adresse", "N/A"),
            "numero_document": payload.fields.get("numero_document", "N/A"),
        },
        "anomalies_detected": payload.analysis_result.get("anomaly_count", 0),
        "is_valid": payload.analysis_result.get("is_valid", False),
        "message": "Fiche client créée/mise à jour avec succès dans le CRM."
    }
    crm_records.append(record)

    return JSONResponse(content=record, status_code=200)


@app.get("/crm/records")
async def crm_list():
    """Liste toutes les fiches CRM enregistrées (pour la démo)."""
    return {"count": len(crm_records), "records": crm_records}


# ---------- CONFORMITÉ ----------
@app.post("/conformite/check")
async def conformite_check(payload: ConformitePayload):
    """
    Simule la vérification de conformité réglementaire.
    
    Vérifie que le document et les données sont conformes
    aux exigences réglementaires (KYC, RGPD, etc.).
    """
    is_valid = payload.analysis_result.get("is_valid", False)
    anomaly_count = payload.analysis_result.get("anomaly_count", 0)

    # Logique de conformité simulée
    if is_valid and anomaly_count == 0:
        conformite_status = "CONFORME"
        conformite_message = "Document conforme aux exigences réglementaires."
        risk_level = "low"
    elif anomaly_count <= 2:
        conformite_status = "A_VERIFIER"
        conformite_message = "Anomalies mineures détectées. Vérification manuelle recommandée."
        risk_level = "medium"
    else:
        conformite_status = "NON_CONFORME"
        conformite_message = "Trop d'anomalies. Document rejeté."
        risk_level = "high"

    record = {
        "conformite_id": str(uuid.uuid4()),
        "received_at": datetime.utcnow().isoformat(),
        "document_key": payload.document_key,
        "document_type": payload.document_type,
        "conformite_status": conformite_status,
        "risk_level": risk_level,
        "message": conformite_message,
        "checks": {
            "identity_verified": True,
            "document_not_expired": is_valid,
            "no_anomalies": anomaly_count == 0,
            "rgpd_compliant": True,
            "kyc_passed": is_valid,
        }
    }
    conformite_records.append(record)

    return JSONResponse(content=record, status_code=200)


@app.get("/conformite/records")
async def conformite_list():
    """Liste tous les résultats de conformité (pour la démo)."""
    return {"count": len(conformite_records), "records": conformite_records}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)
