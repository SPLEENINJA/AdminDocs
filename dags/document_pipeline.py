# =============================================================================
# DAG Airflow – Pipeline de traitement de documents administratifs
# Hackathon 2026 – Adapté aux vrais services du groupe (AdminDocs)
#
# Flux complet :
#   1. Détecter les nouveaux documents dans MinIO bucket "raw"
#   2. Appeler le service OCR du groupe (FastAPI + Gemini Vision, port 8000)
#   3. Stocker le résultat OCR dans MinIO bucket "clean"
#   4. Appeler le service Anomaly Detector (mock, port 8002)
#   5. Stocker le résultat enrichi dans MinIO bucket "curated"
#   6. Envoyer les données vers le backend du groupe (port 4000) :
#      - Mise à jour statut document
#      - Auto-remplissage CRM / fournisseur
#      - Vérification conformité
#
# Services du groupe :
#   - team-backend (Express)  : POST /api/upload, GET /api/documents,
#                                GET /api/crm/suppliers/:id, GET /api/compliance/:id
#   - ocr-service (FastAPI)   : POST /documents/upload, GET /documents,
#                                POST /documents/cross-validate, GET /health
#   - anomaly-service (mock)  : POST /analyze, GET /health
#   - business-service (mock) : POST /crm/submit, POST /conformite/check
# =============================================================================

import os
import sys
import json
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator, BranchPythonOperator
from airflow.operators.empty import EmptyOperator

# Ajouter le dossier utils au path pour les imports
sys.path.insert(0, "/opt/airflow")

from utils.minio_client import (
    list_objects,
    get_file_bytes,
    upload_json,
    download_json,
)
from utils.api_client import (
    call_ocr_service,
    call_anomaly_service,
    call_anomaly_cross_service,
    call_crm_service,
    call_conformite_service,
    check_service_health,
    notify_backend_document,
)
from utils.logger import get_logger, log_step, log_pipeline_start, log_pipeline_end


# ---------- Configuration du DAG ----------
default_args = {
    "owner": "hackathon2026",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=1),
}

# Variables d'environnement (injectées par Docker Compose)
BUCKET_RAW = os.getenv("MINIO_BUCKET_RAW", "raw")
BUCKET_CLEAN = os.getenv("MINIO_BUCKET_CLEAN", "clean")
BUCKET_CURATED = os.getenv("MINIO_BUCKET_CURATED", "curated")

logger = get_logger("document_pipeline")


# =============================================================================
# ÉTAPE 0 : Vérifier la santé des services
# =============================================================================
def check_services(**context):
    """
    Vérifie que tous les services sont en ligne avant de lancer le pipeline.
    Services vérifiés : OCR (groupe), Anomaly (mock), Business (mock), Backend (groupe).
    """
    log_step(logger, "HEALTH_CHECK", "START", "Vérification des services...")

    services = ["ocr", "anomaly", "business", "backend"]
    all_ok = True

    for service in services:
        healthy = check_service_health(service)
        status = "OK" if healthy else "FAIL"
        log_step(logger, "HEALTH_CHECK", status, f"Service '{service}' : {status}")
        if not healthy:
            all_ok = False

    if not all_ok:
        raise Exception("Un ou plusieurs services sont indisponibles !")

    log_step(logger, "HEALTH_CHECK", "SUCCESS", "Tous les services sont en ligne.")


# =============================================================================
# ÉTAPE 1 : Détecter les documents dans le bucket "raw"
# =============================================================================
def detect_documents(**context):
    """
    Scanne le bucket 'raw' de MinIO pour trouver les documents à traiter.
    Pousse la liste des clés de documents via XCom pour les étapes suivantes.
    """
    log_step(logger, "DETECT_DOCUMENTS", "START", f"Scan du bucket '{BUCKET_RAW}'...")

    # Lister tous les objets dans le bucket raw
    documents = list_objects(BUCKET_RAW)

    if not documents:
        log_step(logger, "DETECT_DOCUMENTS", "SKIP", "Aucun document trouvé dans 'raw'.")
        # On pousse une liste vide, le branchement décidera
        context["ti"].xcom_push(key="documents", value=[])
        return []

    log_step(
        logger, "DETECT_DOCUMENTS", "SUCCESS",
        f"{len(documents)} document(s) trouvé(s) : {documents}"
    )

    # Stocker la liste dans XCom pour les tâches suivantes
    context["ti"].xcom_push(key="documents", value=documents)
    return documents


# =============================================================================
# BRANCHEMENT : Documents trouvés ou non ?
# =============================================================================
def branch_on_documents(**context):
    """
    Branche le pipeline en fonction de la présence de documents.
    Si aucun document → skip vers la fin.
    Si documents → continuer le traitement.
    """
    documents = context["ti"].xcom_pull(task_ids="detect_documents", key="documents")

    if not documents:
        logger.info("Aucun document à traiter → skip.")
        return "no_documents"
    else:
        logger.info(f"{len(documents)} document(s) à traiter → processing.")
        return "process_documents"


# =============================================================================
# ÉTAPE 2 : Traitement OCR de tous les documents
# =============================================================================
def process_ocr(**context):
    """
    Pour chaque document détecté dans 'raw' :
      1. Appelle le service OCR
      2. Stocke le résultat JSON dans le bucket 'clean'
    
    Les résultats sont poussés via XCom pour l'étape suivante.
    """
    documents = context["ti"].xcom_pull(task_ids="detect_documents", key="documents")
    ocr_results = {}

    for doc_key in documents:
        log_step(logger, "OCR", "START", f"Traitement de : {doc_key}")
        log_pipeline_start(logger, doc_key)

        try:
            # Appel au service OCR du groupe (FastAPI + Gemini Vision)
            ocr_result = call_ocr_service(doc_key, BUCKET_RAW)

            # Construire la clé de destination dans 'clean'
            clean_key = doc_key.rsplit(".", 1)[0] + "_ocr.json"

            # Stocker le résultat OCR dans le bucket 'clean'
            upload_json(BUCKET_CLEAN, clean_key, ocr_result)

            ocr_results[doc_key] = {
                "ocr_result": ocr_result,
                "clean_key": clean_key,
            }

            # Le service OCR du groupe retourne type_document / confiance
            log_step(logger, "OCR", "SUCCESS",
                     f"{doc_key} → {clean_key} "
                     f"(type: {ocr_result.get('type_document', ocr_result.get('documentType', 'N/A'))})")

        except Exception as e:
            log_step(logger, "OCR", "ERROR", f"{doc_key} : {str(e)}")
            ocr_results[doc_key] = {"error": str(e)}

    # Pousser tous les résultats via XCom
    context["ti"].xcom_push(key="ocr_results", value=ocr_results)
    return ocr_results


# =============================================================================
# ÉTAPE 3 : Analyse d'anomalies
# =============================================================================
def process_anomaly_detection(**context):
    """
    Pour chaque résultat OCR :
      1. Appelle le service Anomaly Detector (règles mono-document)
      2. Appelle /analyze-cross pour la cohérence inter-documents
      3. Enrichit les résultats avec l'analyse combinée

    Les résultats sont poussés via XCom pour l'étape de stockage curated.
    """
    ocr_results = context["ti"].xcom_pull(task_ids="process_ocr", key="ocr_results")
    analysis_results = {}
    # Liste pour l'analyse croisée inter-documents
    cross_doc_inputs = []

    for doc_key, ocr_data in ocr_results.items():
        # Ignorer les documents en erreur
        if "error" in ocr_data:
            log_step(logger, "ANOMALY", "SKIP", f"{doc_key} : erreur OCR précédente")
            analysis_results[doc_key] = ocr_data
            continue

        log_step(logger, "ANOMALY", "START", f"Analyse de : {doc_key}")

        try:
            ocr_result = ocr_data["ocr_result"]

            # Adapter le format — le service OCR retourne "champs" ou "fields"
            fields = ocr_result.get("champs", ocr_result.get("extractedData",
                      ocr_result.get("fields", {})))
            confidence = ocr_result.get("confiance", ocr_result.get("confidence", 0.9))
            doc_type = ocr_result.get("type_document", ocr_result.get("documentType", "inconnu"))
            qualite_scan = ocr_result.get("qualite_scan", "")  # qualité image via Gemini

            anomaly_input = {
                "confidence": confidence,
                "fields": fields,
                "qualite_scan": qualite_scan,  # transmis à l'anomaly detector v2
            }
            analysis = call_anomaly_service(doc_key, anomaly_input, doc_type)

            analysis_results[doc_key] = {
                "ocr_result": ocr_result,
                "clean_key": ocr_data["clean_key"],
                "analysis_result": analysis,
                "fields": fields,
                "document_type": doc_type,
            }

            # Préparer pour l'analyse croisée
            cross_doc_inputs.append({
                "document_key": doc_key,
                "fields": fields,
                "document_type": doc_type,
            })

            log_step(
                logger, "ANOMALY", "SUCCESS",
                f"{doc_key} – valide: {analysis.get('is_valid')}, "
                f"score: {analysis.get('risk_score', 0)}/100, "
                f"anomalies: {analysis.get('anomaly_count', 0)}"
            )

        except Exception as e:
            log_step(logger, "ANOMALY", "ERROR", f"{doc_key} : {str(e)}")
            analysis_results[doc_key] = {**ocr_data, "error_anomaly": str(e)}

    # ── Analyse croisée : cohérence inter-documents ───────────────────────────
    cross_result = {"is_coherent": True, "cross_anomalies": [], "risk_score": 0}
    if len(cross_doc_inputs) > 1:
        log_step(logger, "ANOMALY_CROSS", "START",
                 f"Vérification cohérence sur {len(cross_doc_inputs)} documents…")
        cross_result = call_anomaly_cross_service(cross_doc_inputs)
        log_step(
            logger, "ANOMALY_CROSS",
            "SUCCESS" if cross_result.get("is_coherent") else "WARN",
            f"Cohérent: {cross_result.get('is_coherent')}, "
            f"anomalies: {cross_result.get('cross_anomaly_count', 0)}, "
            f"score: {cross_result.get('risk_score', 0)}/100"
        )

    # Stocker le résultat croisé au niveau du lot
    analysis_results["__cross__"] = cross_result

    context["ti"].xcom_push(key="analysis_results", value=analysis_results)
    return analysis_results


# =============================================================================
# ÉTAPE 4 : Stocker le résultat enrichi dans le bucket "curated"
# =============================================================================
def store_curated(**context):
    """
    Stocke le résultat final (OCR + anomalies) dans le bucket 'curated'.
    Chaque document a son propre fichier JSON final.
    """
    analysis_results = context["ti"].xcom_pull(
        task_ids="process_anomaly_detection", key="analysis_results"
    )
    curated_keys = {}

    # Extraire le résultat croisé (clé réservée __cross__)
    cross_result = analysis_results.pop("__cross__", {})

    for doc_key, data in analysis_results.items():
        if "error" in data or "error_anomaly" in data:
            log_step(logger, "CURATED", "SKIP", f"{doc_key} : erreur précédente")
            continue

        log_step(logger, "CURATED", "START", f"Stockage curated pour : {doc_key}")

        try:
            ocr_result = data["ocr_result"]
            analysis = data["analysis_result"]
            fields = data.get("fields", ocr_result.get("champs", ocr_result.get("fields", {})))
            doc_type = data.get("document_type", ocr_result.get("type_document", "inconnu"))

            # Document curated final enrichi
            curated_doc = {
                "document_key": doc_key,
                "processed_at": datetime.utcnow().isoformat(),
                "pipeline_version": "2.0.0",
                "document_type": doc_type,
                "ocr": {
                    "source_key": data["clean_key"],
                    "confidence": ocr_result.get("confiance", ocr_result.get("confidence")),
                    "fields": fields,
                    "extracted_text": ocr_result.get("extracted_text",
                                     ocr_result.get("ocrText", "")),
                },
                "quality": {
                    "is_valid": analysis.get("is_valid"),
                    "is_anomalous": analysis.get("is_anomalous", not analysis.get("is_valid")),
                    "risk_score": analysis.get("risk_score", 0),
                    "anomaly_count": analysis.get("anomaly_count"),
                    "anomalies": analysis.get("anomalies", []),
                    "recommendation": analysis.get("recommendation"),
                    "scan_quality": ocr_result.get("qualite_scan", "N/A"),
                    # Anomalies inter-documents (si dossier multi-docs)
                    "cross_anomalies": cross_result.get("cross_anomalies", []),
                    "cross_risk_score": cross_result.get("risk_score", 0),
                    "dossier_coherent": cross_result.get("is_coherent", True),
                },
                "status": "READY_FOR_BUSINESS" if analysis.get("is_valid")
                    else "REQUIRES_REVIEW",
            }

            # Clé curated : ex "doc_001_curated.json"
            curated_key = doc_key.rsplit(".", 1)[0] + "_curated.json"
            upload_json(BUCKET_CURATED, curated_key, curated_doc)

            curated_keys[doc_key] = curated_key

            log_step(logger, "CURATED", "SUCCESS", f"{doc_key} → {curated_key}")

        except Exception as e:
            log_step(logger, "CURATED", "ERROR", f"{doc_key} : {str(e)}")

    context["ti"].xcom_push(key="curated_keys", value=curated_keys)
    return curated_keys


# =============================================================================
# ÉTAPE 5a : Envoi vers le CRM (auto-remplissage)
# =============================================================================
def send_to_crm(**context):
    """
    Envoie les données extraites au CRM pour auto-remplissage de fiche client.
    """
    analysis_results = context["ti"].xcom_pull(
        task_ids="process_anomaly_detection", key="analysis_results"
    )
    crm_responses = {}

    for doc_key, data in analysis_results.items():
        if "error" in data or "error_anomaly" in data:
            log_step(logger, "CRM", "SKIP", f"{doc_key} : erreur précédente")
            continue

        log_step(logger, "CRM", "START", f"Envoi vers CRM pour : {doc_key}")

        try:
            fields = data.get("fields", data["ocr_result"].get("champs",
                      data["ocr_result"].get("fields", {})))
            analysis = data["analysis_result"]

            crm_response = call_crm_service(doc_key, fields, analysis)
            crm_responses[doc_key] = crm_response

            log_step(logger, "CRM", "SUCCESS",
                     f"{doc_key} – CRM ID: {crm_response.get('crm_id')}")

        except Exception as e:
            log_step(logger, "CRM", "ERROR", f"{doc_key} : {str(e)}")

    context["ti"].xcom_push(key="crm_responses", value=crm_responses)
    return crm_responses


# =============================================================================
# ÉTAPE 5b : Envoi vers la Conformité (vérification réglementaire)
# =============================================================================
def send_to_conformite(**context):
    """
    Envoie les données au module Conformité pour vérification réglementaire.
    (KYC, RGPD, validité du document, etc.)
    """
    analysis_results = context["ti"].xcom_pull(
        task_ids="process_anomaly_detection", key="analysis_results"
    )
    conformite_responses = {}

    for doc_key, data in analysis_results.items():
        if "error" in data or "error_anomaly" in data:
            log_step(logger, "CONFORMITE", "SKIP", f"{doc_key} : erreur précédente")
            continue

        log_step(logger, "CONFORMITE", "START", f"Vérification conformité pour : {doc_key}")

        try:
            fields = data.get("fields", data["ocr_result"].get("champs",
                      data["ocr_result"].get("fields", {})))
            analysis = data["analysis_result"]
            doc_type = data.get("document_type",
                      data["ocr_result"].get("type_document", "inconnu"))

            conformite_response = call_conformite_service(doc_key, fields, analysis, doc_type)
            conformite_responses[doc_key] = conformite_response

            log_step(
                logger, "CONFORMITE", "SUCCESS",
                f"{doc_key} – statut: {conformite_response.get('conformite_status')}"
            )

        except Exception as e:
            log_step(logger, "CONFORMITE", "ERROR", f"{doc_key} : {str(e)}")

    context["ti"].xcom_push(key="conformite_responses", value=conformite_responses)
    return conformite_responses


# =============================================================================
# ÉTAPE 5c : Notifier le backend du groupe
# =============================================================================
def notify_backend(**context):
    """
    Notifie le backend Express du groupe que le pipeline est terminé
    pour chaque document curated.
    """
    curated_keys = context["ti"].xcom_pull(task_ids="store_curated", key="curated_keys") or {}

    for doc_key, curated_key in curated_keys.items():
        log_step(logger, "BACKEND_NOTIFY", "START", f"Notification pour : {doc_key}")
        try:
            curated_data = download_json(BUCKET_CURATED, curated_key)
            notify_backend_document(doc_key, curated_data)
            log_step(logger, "BACKEND_NOTIFY", "SUCCESS", f"{doc_key} – backend notifié")
        except Exception as e:
            log_step(logger, "BACKEND_NOTIFY", "ERROR", f"{doc_key} : {str(e)}")


# =============================================================================
# ÉTAPE 6 : Résumé / Log final du pipeline
# =============================================================================
def pipeline_summary(**context):
    """
    Produit un résumé du pipeline complet pour chaque document traité.
    Log le statut final et les résultats métier.
    """
    documents = context["ti"].xcom_pull(task_ids="detect_documents", key="documents")
    curated_keys = context["ti"].xcom_pull(task_ids="store_curated", key="curated_keys") or {}
    crm_responses = context["ti"].xcom_pull(task_ids="send_to_crm", key="crm_responses") or {}
    conformite_responses = context["ti"].xcom_pull(
        task_ids="send_to_conformite", key="conformite_responses"
    ) or {}

    logger.info("=" * 70)
    logger.info("RÉSUMÉ DU PIPELINE – Hackathon 2026")
    logger.info("=" * 70)
    logger.info(f"Documents détectés : {len(documents)}")
    logger.info(f"Documents en curated : {len(curated_keys)}")
    logger.info(f"Fiches CRM créées : {len(crm_responses)}")
    logger.info(f"Vérifications conformité : {len(conformite_responses)}")

    for doc_key in documents:
        curated = "OK" if doc_key in curated_keys else "FAIL"
        crm = "OK" if doc_key in crm_responses else "FAIL"
        conf = "OK" if doc_key in conformite_responses else "FAIL"
        logger.info(f"  {doc_key} → curated:{curated} | CRM:{crm} | conformité:{conf}")
        log_pipeline_end(logger, doc_key, success=(doc_key in curated_keys))

    logger.info("=" * 70)


# =============================================================================
# DÉFINITION DU DAG
# =============================================================================
with DAG(
    dag_id="document_processing_pipeline",
    default_args=default_args,
    description="Pipeline de traitement de documents administratifs – Hackathon 2026",
    schedule_interval=timedelta(minutes=5),    # Scan toutes les 5 minutes
    start_date=datetime(2026, 3, 15),
    catchup=False,
    max_active_runs=1,
    tags=["hackathon", "documents", "pipeline", "admindocs"],
) as dag:

    # ---  Vérification des services ---
    t_check_services = PythonOperator(
        task_id="check_services",
        python_callable=check_services,
    )

    # ---  Détecter les documents dans raw ---
    t_detect = PythonOperator(
        task_id="detect_documents",
        python_callable=detect_documents,
    )

    # --- Branchement : documents trouvés ? ---
    t_branch = BranchPythonOperator(
        task_id="branch_on_documents",
        python_callable=branch_on_documents,
    )

    # --- Tâche vide : aucun document ---
    t_no_docs = EmptyOperator(
        task_id="no_documents",
    )

    # --- Tâche intermédiaire pour le branchement ---
    t_process = EmptyOperator(
        task_id="process_documents",
    )

    # ---  OCR ---
    t_ocr = PythonOperator(
        task_id="process_ocr",
        python_callable=process_ocr,
    )

    # ---  Anomaly Detection ---
    t_anomaly = PythonOperator(
        task_id="process_anomaly_detection",
        python_callable=process_anomaly_detection,
    )

    # ---  Stocker en curated ---
    t_curated = PythonOperator(
        task_id="store_curated",
        python_callable=store_curated,
    )

    # ---  Envoi CRM ---
    t_crm = PythonOperator(
        task_id="send_to_crm",
        python_callable=send_to_crm,
    )

    # ---  Envoi Conformité ---
    t_conformite = PythonOperator(
        task_id="send_to_conformite",
        python_callable=send_to_conformite,
    )

    # ---  Notifier le backend du groupe ---
    t_notify = PythonOperator(
        task_id="notify_backend",
        python_callable=notify_backend,
    )

   
    t_summary = PythonOperator(
        task_id="pipeline_summary",
        python_callable=pipeline_summary,
        trigger_rule="none_failed_min_one_success",  # s'exécute même si branche skip
    )

   

    t_check_services >> t_detect >> t_branch

    t_branch >> t_no_docs >> t_summary

    t_branch >> t_process >> t_ocr >> t_anomaly >> t_curated

    t_curated >> [t_crm, t_conformite, t_notify] >> t_summary
