# Hackathon 2026 – Orchestration & Pipeline de Documents AdminDocs

Pipeline de traitement automatique de documents administratifs (factures, devis, kbis, attestations URSSAF, RIB, SIRET), orchestré par **Apache Airflow**, avec stockage **MinIO** (Data Lake S3-compatible), service **OCR Gemini Vision** et backend **Express** du groupe.

---

## Architecture

```
┌───────────────┐      ┌────────────────────────┐
│  Frontend /   │─────▶│  Team Backend (Express) │  port 4000
│  Upload web   │      │  POST /api/upload        │
└───────────────┘      └────────────┬───────────┘
                                    │
                         ┌──────────▼──────────┐
                         │   MinIO (raw)        │  port 9000
                         │   Stockage brut      │  console: 8900
                         └──────────┬──────────┘
                                    │
                         ┌──────────▼──────────┐
                         │   OCR Service        │  port 8000
                         │   FastAPI + Gemini   │
                         │   POST /documents/   │
                         │        upload        │
                         └──────────┬──────────┘
                                    │
                         ┌──────────▼──────────┐
                         │   MinIO (clean)      │
                         │   Résultat OCR JSON  │
                         └──────────┬──────────┘
                                    │
                         ┌──────────▼──────────┐
                         │  Anomaly Detector    │  port 8002
                         │  (mock FastAPI)      │
                         │  POST /analyze       │
                         └──────────┬──────────┘
                                    │
                         ┌──────────▼──────────┐
                         │   MinIO (curated)    │
                         │   Résultat enrichi   │
                         └──────┬───────┬───────┘
                                │       │       │
              ┌─────────────────┘       │       └──────────────┐
              ▼                         ▼                       ▼
   ┌──────────────────┐    ┌──────────────────┐   ┌─────────────────────┐
   │  Business (mock) │    │  Business (mock) │   │  Team Backend       │
   │  POST /crm/      │    │  POST /conformite│   │  Notification       │
   │  submit          │    │  /check          │   │  pipeline/result    │
   └──────────────────┘    └──────────────────┘   └─────────────────────┘

          ══════════════════════════════════════════════
                      Orchestré par Apache Airflow
                      http://localhost:8080
          ══════════════════════════════════════════════
```

---

## Services et ports

| Service                   | Port  | Image / Source                    | Usage                               |
|---------------------------|-------|-----------------------------------|-------------------------------------|
| team-backend (groupe)     | 4000  | `team_backend/` (Express Node.js) | Upload + API documents              |
| ocr-service (groupe)      | 8000  | `ocr_pipeline/` (FastAPI+Gemini)  | Extraction texte documents          |
| anomaly-service (**v2**)  | 8002  | `mocks/anomaly_service/`          | Détection anomalies (10 règles)     |
| business-service          | 8003  | `mocks/business_service/`         | CRM + Conformité                    |
| airflow-webserver         | 8080  | `apache/airflow:2.8.1-python3.11` | Orchestration DAG                   |
| minio (API S3)            | 9000  | `minio/minio:latest`              | Data Lake raw/clean/curated         |
| minio (console)           | 8900  | même conteneur                    | Interface web MinIO                 |
| postgres                  | 5432  | `postgres:16-alpine`              | Base de données Airflow             |
| frontend (groupe)         | 3000  | `frontend/` (React+Vite+nginx)    | Interface utilisateur               |

---

## Anomaly Detector — règles implémentées (v2)

| # | Type                    | Sévérité | Description                                            |
|---|-------------------------|----------|--------------------------------------------------------|
| 1 | `IMAGE_QUALITY_LOW`     | high     | Confiance OCR < 75% ou qualite_scan mauvaise           |
| 2 | `DOC_TYPE_MISMATCH`     | high     | Type déclaré ≠ type détecté par Gemini                 |
| 3 | `MISSING_REQUIRED_FIELD`| high     | Champ obligatoire absent selon le type de document     |
| 4 | `INVALID_SIRET`         | high     | SIRET 14 chiffres — clé Luhn invalide                  |
| 5 | `INVALID_SIREN`         | medium   | SIREN 9 chiffres — clé Luhn invalide                   |
| 6 | `TVA_NUMBER_MISMATCH`   | medium   | N° TVA FR incohérent avec le SIRET                     |
| 7 | `TTC_INCONSISTENT`      | high     | HT + TVA ≠ TTC (tolérance 5 centimes)                  |
| 8 | `ATTESTATION_EXPIRED`   | high     | Date d'expiration dépassée (attestations, kbis)        |
| 9 | `SIRET_MISMATCH`        | high     | SIRET différents dans un dossier multi-docs (cross-doc)|
|10 | `COMPANY_NAME_MISMATCH` | medium   | Raisons sociales différentes (cross-doc)               |

Score de risque : `high=35` / `medium=20` / `low=10` — plafonné à 100.

---

## Arborescence du projet

```
hackathon2026/
├── docker-compose.yml           # Orchestration de tous les services
├── .env                         # Variables d'environnement (copie de .env.example)
├── .env.example                 # Template des variables
├── requirements-airflow.txt     # Dépendances Python pour Airflow
│
├── dags/
│   └── document_pipeline.py     # DAG principal (10 tâches)
│
├── utils/
│   ├── minio_client.py          # Lecture/écriture MinIO (boto3)
│   ├── api_client.py            # Appels HTTP vers tous les services
│   └── logger.py                # Journalisation structurée
│
├── team_backend/                # Backend Express du groupe
│   ├── Dockerfile
│   └── backend/src/             # Code source
│
├── ocr_pipeline/                # Service OCR du groupe
│   ├── Dockerfile
│   └── api/app.py               # FastAPI + Gemini Vision
│
├── mocks/
│   ├── anomaly_service/         # Anomaly Detector v2 (port 8002)
│   │   └── main.py              # 10 règles + /analyze-cross
│   └── business_service/        # CRM + Conformité (port 8003)
│
├── scripts/
│   ├── demo_scenarios.py        # 3 scénarios de démonstration (NOUVEAU)
│   ├── upload_test_document.py  # Upload d'un doc de test dans MinIO
│   └── test_services.py         # Health check de tous les services
│
├── examples/                    # Exemples JSON (raw / clean / curated)
├── logs/                        # Logs Airflow
└── docs/                        # Documentation technique
```

---

## Prérequis

- **Docker** et **Docker Compose** installés
- **Clé API Gemini** pour le service OCR (obligatoire)
- Ports libres : `3000`, `4000`, `5432`, `8000`, `8002`, `8003`, `8080`, `8900`, `9000`

---

## Arborescence du projet

```
hackathon2026/
├── docker-compose.yml           # Orchestration de tous les services
├── .env                         # Variables d'environnement (copie de .env.example)
├── .env.example                 # Template des variables
├── requirements-airflow.txt     # Dépendances Python pour Airflow
│
├── dags/
│   └── document_pipeline.py     # DAG principal (7 étapes)
│
├── utils/
│   ├── __init__.py
│   ├── minio_client.py          # Lecture/écriture MinIO (boto3)
│   ├── api_client.py            # Appels HTTP vers tous les services
│   └── logger.py                # Journalisation structurée
│
├── team_backend/                # Backend Express du groupe
│   ├── Dockerfile
│   └── backend/                 # Code source (branche feature/frontend-admindocs)
│       └── src/
│
├── ocr_pipeline/                # Service OCR du groupe
│   ├── Dockerfile               # (branche dev/ocr-pipeline)
│   ├── requirements.txt
│   └── api/app.py               # FastAPI + Gemini Vision
│
├── mocks/
│   ├── anomaly_service/         # Mock Anomaly Detector (port 8002)
│   └── business_service/        # Mock CRM + Conformité (port 8003)
│
├── scripts/
│   ├── upload_test_document.py  # Upload d'un doc de test dans MinIO
│   └── test_services.py         # Test de santé de tous les services
│
├── examples/                    # Exemples JSON (raw / clean / curated)
├── logs/                        # Logs Airflow (volume Docker)
└── plugins/                     # Plugins Airflow (volume Docker)
```

---

## Prérequis

- **Docker** et **Docker Compose** installés
- **Clé API Gemini** pour le service OCR (obligatoire)
- Ports libres : `4000`, `5432`, `8000`, `8002`, `8003`, `8080`, `8900`, `9000`

---

## Démarrage

### 1. Configurer les variables d'environnement

```bash
cd hackathon2026
cp .env.example .env
```

Éditer `.env` pour renseigner la clé Gemini :

```
GEMINI_API_KEY=your_gemini_api_key_here
```

### 2. Lancer tous les services

```bash
docker-compose up --build -d

# Suivre les logs en temps réel
docker-compose logs -f
```

### 3. Accéder aux interfaces

| Interface         | URL                           | Identifiants                 |
|-------------------|-------------------------------|------------------------------|
| Airflow UI        | http://localhost:8080         | admin / admin                |
| MinIO Console     | http://localhost:8900         | minio_user / minio_password  |
| Backend API       | http://localhost:4000/api     | –                            |
| OCR Swagger       | http://localhost:8000/docs    | –                            |
| Anomaly Swagger   | http://localhost:8002/docs    | –                            |
| Business Swagger  | http://localhost:8003/docs    | –                            |

### 4. Uploader un document et lancer les scénarios de démo

```bash
pip install requests boto3

# Upload les 3 documents de démo dans MinIO bucket 'raw'
python scripts/demo_scenarios.py --upload

# Exécuter directement les 3 scénarios de démo
python scripts/demo_scenarios.py

# Scénario 1 uniquement (document valide)
python scripts/demo_scenarios.py --scenario 1

# Scénario 2 (anomalies métier : SIRET invalide + TTC incohérent)
python scripts/demo_scenarios.py --scenario 2

# Scénario 3 (qualité basse + attestation expirée + SIRET mismatch inter-docs)
python scripts/demo_scenarios.py --scenario 3
```

### 5. Déclencher le DAG

Le DAG `document_processing_pipeline` se lance automatiquement toutes les 5 minutes.

Pour un déclenchement manuel :
1. Ouvrir Airflow → http://localhost:8080
2. Trouver `document_processing_pipeline`
3. Cliquer ▶ **Trigger DAG**

### 6. Vérifier les résultats

```bash
python scripts/test_services.py
```

Dans MinIO Console (http://localhost:8900) :
- **raw** → documents d'entrée
- **clean** → résultats OCR (`*_ocr.json`)
- **curated** → résultats finaux enrichis (`*_curated.json`)

---

## Étapes du DAG (document_pipeline.py)

| Tâche                        | Description                                                         |
|------------------------------|---------------------------------------------------------------------|
| `check_services`             | Health check OCR + anomaly + business + backend                     |
| `detect_documents`           | Scan du bucket MinIO `raw`                                          |
| `branch_on_documents`        | Skip si aucun document, sinon → pipeline                            |
| `process_ocr`                | POST /documents/upload → OCR Gemini Vision + stockage `clean`       |
| `process_anomaly_detection`  | POST /analyze (mono-doc) + POST /analyze-cross (cohérence dossier)  |
| `store_curated`              | Stockage JSON enrichi dans bucket `curated` (OCR + anomalies)       |
| `send_to_crm` (parallèle)    | POST /crm/submit → auto-remplissage CRM                             |
| `send_to_conformite` (||)    | POST /conformite/check → vérification réglementaire                 |
| `notify_backend` (parallèle) | POST /api/pipeline/result → notification backend groupe   |
| `pipeline_summary`        | Log du résumé complet                                        |

---

## Tests manuels (curl)

```bash
# Health checks
curl http://localhost:4000/api/health
curl http://localhost:8000/health
curl http://localhost:8002/health
curl http://localhost:8003/health

# OCR – uploader un fichier
curl -X POST http://localhost:8000/documents/upload \
  -F "files=@/chemin/vers/facture.pdf"

# Anomaly Detector
curl -X POST http://localhost:8002/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "document_key": "facture_dupont.pdf",
    "ocr_result": {"confiance": 0.94, "champs": {"siret": "12345678901234"}},
    "document_type": "facture"
  }'

# CRM (mock)
curl -X POST http://localhost:8003/crm/submit \
  -H "Content-Type: application/json" \
  -d '{
    "document_key": "facture_dupont.pdf",
    "fields": {"nom": "DUPONT", "siret": "12345678901234"},
    "analysis_result": {"is_valid": true, "anomaly_count": 0}
  }'

# Documents backend
curl http://localhost:4000/api/documents
```

---

## Variables d'environnement clés

| Variable          | Valeur par défaut          | Description                  |
|-------------------|----------------------------|------------------------------|
| `GEMINI_API_KEY`  | *(vide)*                   | Clé API Gemini (obligatoire) |
| `MINIO_ACCESS_KEY`| `minio_user`               | Credentials MinIO            |
| `MINIO_SECRET_KEY`| `minio_password`           | Credentials MinIO            |
| `OCR_SERVICE_URL` | `http://ocr-service:8000`  | URL OCR (interne Docker)     |
| `BACKEND_URL`     | `http://team-backend:4000` | URL backend (interne Docker) |

---

## Notes

- Le mock OCR (`mocks/ocr_service/`) n'est plus utilisé – remplacé par le vrai service OCR Gemini du groupe.
- Les mocks `anomaly_service` et `business_service` restent actifs en attendant l'implémentation complète par le groupe.
- L'endpoint `POST /api/pipeline/result` sur le backend est un endpoint à implémenter par l'équipe backend pour la notification de fin de pipeline.


