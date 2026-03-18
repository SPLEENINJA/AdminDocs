"""
services/storage.py — Stockage local simulant les 3 zones Data Lake
  Raw     → fichier original copié
  Clean   → texte OCR brut (txt)
  Curated → JSON structuré validé
"""
from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path
from datetime import datetime

from config import STORAGE_RAW, STORAGE_CLEAN, STORAGE_CURATED
from utils.helpers import save_json

logger = logging.getLogger("ocr_service.storage")


def _today_subdir() -> Path:
    """Sous-dossier par date : YYYY/MM/DD"""
    today = datetime.now()
    return Path(str(today.year)) / f"{today.month:02d}" / f"{today.day:02d}"


# ── Zone RAW ──────────────────────────────────────────────────────────────────

def save_raw(source_path: str, document_id: str) -> Path:
    """
    Copie le fichier original dans la zone RAW.
    Retourne le chemin de destination.
    """
    src     = Path(source_path)
    subdir  = STORAGE_RAW / _today_subdir()
    subdir.mkdir(parents=True, exist_ok=True)

    dest = subdir / f"{document_id}{src.suffix.lower()}"
    shutil.copy2(src, dest)
    logger.debug(f"[RAW]     Sauvegardé → {dest}")
    return dest


# ── Zone CLEAN ────────────────────────────────────────────────────────────────

def save_clean(document_id: str, texte_brut: str) -> Path:
    """
    Sauvegarde le texte OCR brut dans la zone CLEAN (fichier .txt).
    """
    subdir = STORAGE_CLEAN / _today_subdir()
    subdir.mkdir(parents=True, exist_ok=True)

    dest = subdir / f"{document_id}.txt"
    dest.write_text(texte_brut, encoding="utf-8")
    logger.debug(f"[CLEAN]   Sauvegardé → {dest}")
    return dest


# ── Zone CURATED ──────────────────────────────────────────────────────────────

def save_curated(document_id: str, result: dict) -> Path:
    """
    Sauvegarde les données structurées + validées dans la zone CURATED (JSON).
    """
    subdir = STORAGE_CURATED / _today_subdir()
    subdir.mkdir(parents=True, exist_ok=True)

    dest = subdir / f"{document_id}.json"
    save_json(result, dest)
    logger.debug(f"[CURATED] Sauvegardé → {dest}")
    return dest


# ── Lecture ────────────────────────────────────────────────────────────────────

def load_curated(document_id: str, date_str: str | None = None) -> dict | None:
    """
    Charge un document curated par son ID.
    date_str format : YYYY/MM/DD (optionnel pour optimiser la recherche)
    """
    if date_str:
        path = STORAGE_CURATED / date_str / f"{document_id}.json"
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        return None

    # Recherche globale (moins performant)
    for path in STORAGE_CURATED.rglob(f"{document_id}.json"):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def list_curated(limit: int = 50) -> list[dict]:
    """
    Liste les derniers documents de la zone CURATED.
    """
    files  = sorted(STORAGE_CURATED.rglob("*.json"), reverse=True)[:limit]
    result = []
    for f in files:
        try:
            with open(f, "r", encoding="utf-8") as fp:
                result.append(json.load(fp))
        except Exception:
            pass
    return result


# ── Résumé du stockage ────────────────────────────────────────────────────────

def storage_summary() -> dict:
    """Retourne un résumé des documents stockés par zone."""
    return {
        "raw":     len(list(STORAGE_RAW.rglob("*.*"))),
        "clean":   len(list(STORAGE_CLEAN.rglob("*.txt"))),
        "curated": len(list(STORAGE_CURATED.rglob("*.json"))),
    }
