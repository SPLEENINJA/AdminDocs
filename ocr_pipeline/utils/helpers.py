"""
utils/helpers.py — Fonctions utilitaires générales
"""
import hashlib
import json
import logging
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("ocr_service.helpers")


def generate_document_id(file_path: str) -> str:
    base = Path(file_path).stem
    ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
    uid  = str(uuid.uuid4())[:8]
    return f"{base}_{ts}_{uid}"


def file_sha256(file_path: str) -> str:
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def clean_json_response(raw: str) -> str:
    """
    Extrait le JSON valide depuis la réponse brute du LLM.

    Stratégies dans l'ordre :
      1. Extraction entre ```json ... ``` ou ``` ... ```
      2. Extraction du premier { ... } bien formé (recherche la paire externe)
      3. Réparation d'un JSON tronqué (ferme les accolades manquantes)
      4. Retourne la chaîne nettoyée en dernier recours
    """
    if not raw:
        return "{}"

    text = raw.strip()

    # ── Stratégie 1 : bloc markdown ```json ... ``` ────────────────────────
    md_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL | re.IGNORECASE)
    if md_match:
        candidate = md_match.group(1).strip()
        if _is_valid_json(candidate):
            return candidate
        text = candidate  # essayer de réparer ce bloc

    # Enlever les backticks résiduels
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```\s*$", "", text)
    text = text.strip()

    # ── Stratégie 2 : trouver la paire { ... } externe ────────────────────
    start = text.find("{")
    if start != -1:
        end = _find_matching_brace(text, start)
        if end != -1:
            candidate = text[start:end + 1]
            if _is_valid_json(candidate):
                return candidate
            # Trouvé mais invalide → tenter réparation
            text = candidate

    # ── Stratégie 3 : réparer JSON tronqué ────────────────────────────────
    repaired = _repair_truncated_json(text)
    if repaired and _is_valid_json(repaired):
        logger.warning("JSON tronqué réparé automatiquement.")
        return repaired

    # ── Fallback : retourner tel quel (laissera json.loads lever l'erreur) ──
    return text


def _is_valid_json(s: str) -> bool:
    try:
        json.loads(s)
        return True
    except (json.JSONDecodeError, ValueError):
        return False


def _find_matching_brace(text: str, start: int) -> int:
    """
    Trouve la position de l'accolade fermante correspondant à text[start].
    Gère les strings JSON correctement (ignore les accolades dans les strings).
    Retourne -1 si pas trouvé.
    """
    depth   = 0
    in_str  = False
    escape  = False

    for i, ch in enumerate(text[start:], start=start):
        if escape:
            escape = False
            continue
        if ch == "\\" and in_str:
            escape = True
            continue
        if ch == '"' and not escape:
            in_str = not in_str
            continue
        if in_str:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return i

    return -1


def _repair_truncated_json(text: str) -> Optional[str]:
    """
    Tente de fermer un JSON tronqué.
    Stratégie : tronque au dernier champ complet de niveau 1 avant de fermer,
    pour préserver les champs déjà parsés (siret, montants, etc.)
    plutôt que de perdre tout ce qui suit un texte_brut trop long.
    """
    if not text.strip().startswith("{"):
        return None

    # ── Tentative 1 : tronquer au dernier champ complet ──────────────────
    last_comma = _find_last_top_level_comma(text)
    if last_comma > 0:
        candidate = _close_open_json(text[:last_comma])
        if candidate and _is_valid_json(candidate):
            parsed = json.loads(candidate)
            # Garder seulement si on a récupéré des données utiles
            champs = parsed.get("champs") or {}
            has_data = any(v is not None for v in champs.values())
            if has_data or parsed.get("type_document", "inconnu") != "inconnu":
                logger.warning("JSON tronqué réparé automatiquement.")
                return candidate

    # ── Tentative 2 : fermeture brutale ───────────────────────────────────
    closed = _close_open_json(text)
    if closed:
        logger.warning("JSON tronqué réparé automatiquement.")
    return closed


def _find_last_top_level_comma(text: str) -> int:
    """Trouve la position du dernier ',' au niveau d'imbrication 1 (hors strings)."""
    depth  = 0
    in_str = False
    escape = False
    last   = -1
    for i, ch in enumerate(text):
        if escape:
            escape = False
            continue
        if ch == "\\" and in_str:
            escape = True
            continue
        if ch == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if ch in "{[":
            depth += 1
        elif ch in "}]":
            depth -= 1
        elif ch == "," and depth == 1:
            last = i
    return last


def _close_open_json(text: str) -> Optional[str]:
    """Ferme les accolades/crochets/strings ouverts dans un fragment JSON."""
    text = re.sub(r",\s*([}\]])", r"\1", text)
    depth_brace   = 0
    depth_bracket = 0
    in_str = False
    escape = False
    for ch in text:
        if escape:
            escape = False
            continue
        if ch == "\\" and in_str:
            escape = True
            continue
        if ch == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if ch == "{":
            depth_brace += 1
        elif ch == "}":
            depth_brace -= 1
        elif ch == "[":
            depth_bracket += 1
        elif ch == "]":
            depth_bracket -= 1
    if in_str:
        text += '"'
    text += "]" * max(0, depth_bracket)
    text += "}" * max(0, depth_brace)
    return text if text.strip() else None


def save_json(data: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)


def load_json(path: Path) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def is_supported_file(file_path: str) -> bool:
    supported = {".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".webp"}
    return Path(file_path).suffix.lower() in supported
