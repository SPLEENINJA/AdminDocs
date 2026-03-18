# =============================================================================
# Utilitaire API – Appels HTTP vers les services du groupe + mocks
# Adapté aux vrais endpoints du projet AdminDocs (Hackathon 2026)
#
# Services :
#   - ocr      : FastAPI + Gemini Vision (port 8000)
#   - anomaly  : Mock Anomaly Detector (port 8002)
#   - business : Mock CRM + Conformité (port 8003)
#   - backend  : Backend Express du groupe (port 4000)
# =============================================================================

import os
import io
import requests
from typing import Dict, Any

from utils.minio_client import get_file_bytes


def get_service_url(service_name: str) -> str:
    """Retourne l'URL de base d'un service via les variables d'environnement."""
    urls = {
        "ocr": os.getenv("OCR_SERVICE_URL", "http://ocr-service:8000"),
        "anomaly": os.getenv("ANOMALY_SERVICE_URL", "http://anomaly-service:8002"),
        "business": os.getenv("BUSINESS_SERVICE_URL", "http://business-service:8003"),
        "backend": os.getenv("BACKEND_URL", "http://team-backend:4000"),
    }
    return urls.get(service_name, "")


def call_ocr_service(document_key: str, bucket: str = "raw") -> Dict[str, Any]:
    """
    Appelle le service OCR du groupe (POST /documents/upload).
    Récupère le fichier depuis MinIO et l'envoie en multipart.
    """
    url = f"{get_service_url('ocr')}/documents/upload"

    # Lire le fichier brut depuis MinIO
    file_bytes = get_file_bytes(bucket, document_key)

    # Le service OCR du groupe attend un champ "files" en multipart
    files = [("files", (document_key, io.BytesIO(file_bytes)))]

    print(f"[API] Appel OCR (groupe) : {url} – fichier : {document_key}")
    response = requests.post(url, files=files, timeout=60)
    response.raise_for_status()

    result = response.json()
    # Le service peut retourner une liste de résultats (un par fichier)
    if isinstance(result, list) and len(result) > 0:
        result = result[0]

    print(f"[API] OCR terminé – type: {result.get('type_document', 'N/A')}, "
          f"confiance: {result.get('confiance', result.get('confidence', 'N/A'))}")
    return result


def call_anomaly_service(
    document_key: str,
    ocr_result: Dict[str, Any],
    document_type: str = "inconnu"
) -> Dict[str, Any]:
    """Appelle le service Anomaly Detector (mock) pour vérifier les incohérences."""
    url = f"{get_service_url('anomaly')}/analyze"
    payload = {
        "document_key": document_key,
        "ocr_result": ocr_result,
        "document_type": document_type,
    }

    print(f"[API] Appel Anomaly Detector : {url}")
    response = requests.post(url, json=payload, timeout=30)
    response.raise_for_status()

    result = response.json()
    print(f"[API] Analyse terminée – valide : {result.get('is_valid', 'N/A')}, "
          f"anomalies : {result.get('anomaly_count', 0)}")
    return result


def call_crm_service(
    document_key: str,
    fields: Dict[str, Any],
    analysis_result: Dict[str, Any]
) -> Dict[str, Any]:
    """Envoie les données extraites au CRM (mock) pour auto-remplissage."""
    url = f"{get_service_url('business')}/crm/submit"
    payload = {
        "document_key": document_key,
        "fields": fields,
        "analysis_result": analysis_result,
    }

    print(f"[API] Appel CRM : {url}")
    response = requests.post(url, json=payload, timeout=30)
    response.raise_for_status()

    result = response.json()
    print(f"[API] CRM – statut : {result.get('status', 'N/A')}")
    return result


def call_conformite_service(
    document_key: str,
    fields: Dict[str, Any],
    analysis_result: Dict[str, Any],
    document_type: str = "inconnu"
) -> Dict[str, Any]:
    """Envoie les données au module de conformité (mock) pour vérification."""
    url = f"{get_service_url('business')}/conformite/check"
    payload = {
        "document_key": document_key,
        "fields": fields,
        "analysis_result": analysis_result,
        "document_type": document_type,
    }

    print(f"[API] Appel Conformité : {url}")
    response = requests.post(url, json=payload, timeout=30)
    response.raise_for_status()

    result = response.json()
    print(f"[API] Conformité – statut : {result.get('conformite_status', 'N/A')}")
    return result


def notify_backend_document(
    document_key: str,
    curated_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Notifie le backend Express du groupe qu'un document a été traité.
    Envoie les données curated au backend via POST /api/pipeline/result.
    """
    url = f"{get_service_url('backend')}/api/pipeline/result"
    payload = {
        "document_key": document_key,
        "curated_data": curated_data,
    }

    print(f"[API] Notification backend : {url}")
    try:
        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()
        result = response.json()
        print(f"[API] Backend notifié – statut : {result.get('status', 'OK')}")
        return result
    except requests.exceptions.HTTPError:
        # Le backend n'a peut-être pas encore cet endpoint, c'est OK
        print(f"[API] Backend – endpoint non disponible (à implémenter par le groupe)")
        return {"status": "skipped", "reason": "endpoint not available"}


def check_service_health(service_name: str) -> bool:
    """Vérifie qu'un service est en ligne via son endpoint /health."""
    base_url = get_service_url(service_name)
    # Le backend du groupe utilise /api/health
    if service_name == "backend":
        url = f"{base_url}/api/health"
    else:
        url = f"{base_url}/health"
    try:
        response = requests.get(url, timeout=5)
        return response.status_code == 200
    except requests.exceptions.ConnectionError:
        print(f"[API] Service '{service_name}' non accessible à {url}")
        return False


def call_anomaly_cross_service(documents: list) -> Dict[str, Any]:
    """
    Appelle POST /analyze-cross pour vérifier la cohérence d'un groupe de documents.
    Détecte SIRET_MISMATCH, COMPANY_NAME_MISMATCH, TVA_NUMBER_MISMATCH entre docs.

    :param documents: liste de dicts [{document_key, fields, document_type}, ...]
    :returns: résultat de l'analyse croisée
    """
    url = f"{get_service_url('anomaly')}/analyze-cross"
    payload = {"documents": documents}

    print(f"[API] Analyse croisée inter-documents : {len(documents)} doc(s) → {url}")
    try:
        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()
        result = response.json()
        print(
            f"[API] Cross-doc – cohérent : {result.get('is_coherent')}, "
            f"score risque : {result.get('risk_score', 0)}/100"
        )
        return result
    except Exception as e:
        print(f"[API] Analyse croisée échouée (non bloquant) : {e}")
        return {"is_coherent": True, "cross_anomalies": [], "risk_score": 0, "error": str(e)}

