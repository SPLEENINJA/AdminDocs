"""
config.py — Configuration centralisée depuis .env

Modèles Gemini gratuits disponibles (mars 2026) :
  - gemini-2.5-flash         →  5 RPM / 20 RPD
  - gemini-2.5-flash-lite    → 10 RPM / 20 RPD
  - gemini-3-flash           →  5 RPM / 20 RPD   (alias gemini-2.0-flash ?)
  - gemini-3.1-flash-lite    → 15 RPM / 500 RPD  ← meilleur quota gratuit
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent

# ── API Gemini ────────────────────────────────────────────────────────────────
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")

# Modèle principal
GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# Fallback dans l'ordre si quota épuisé sur le modèle principal
# Seuls les modèles avec RPD > 0 sur le free tier sont listés ici.
# gemini-3.1-flash-lite en dernier car 500 RPD → quasi illimité pour un hackathon.
GEMINI_FALLBACK_MODELS: list[str] = [
    m.strip()
    for m in os.getenv(
        "GEMINI_FALLBACK_MODELS",
        "gemini-2.5-flash-lite,gemini-3-flash,gemini-3.1-flash-lite",
    ).split(",")
    if m.strip()
]

# ── Stockage local ────────────────────────────────────────────────────────────
STORAGE_RAW     = BASE_DIR / os.getenv("STORAGE_RAW",     "storage/raw")
STORAGE_CLEAN   = BASE_DIR / os.getenv("STORAGE_CLEAN",   "storage/clean")
STORAGE_CURATED = BASE_DIR / os.getenv("STORAGE_CURATED", "storage/curated")
LOGS_DIR        = BASE_DIR / os.getenv("LOGS_DIR",        "logs")

# ── OCR ───────────────────────────────────────────────────────────────────────
MAX_RETRIES        = int(os.getenv("MAX_RETRIES", 3))
RETRY_WAIT_SECONDS = int(os.getenv("RETRY_WAIT_SECONDS", 5))
PDF_DPI            = int(os.getenv("PDF_DPI", 200))

# ── Types de documents ────────────────────────────────────────────────────────
DOCUMENT_TYPES = [
    "facture", "devis", "attestation_urssaf",
    "extrait_kbis", "rib", "attestation_siret", "contrat",
    "facture_etrangere", "inconnu",
]

for _dir in [STORAGE_RAW, STORAGE_CLEAN, STORAGE_CURATED, LOGS_DIR]:
    _dir.mkdir(parents=True, exist_ok=True)


def validate_config() -> None:
    if not GEMINI_API_KEY:
        raise EnvironmentError(
            "GEMINI_API_KEY manquant. "
            "Copie .env.example en .env et renseigne ta clé."
        )
