"""
services/ocr.py — OCR + classification via Gemini Vision
- Nouveau SDK google.genai (fallback sur google.generativeai si absent)
- Détection quota journalier épuisé (limit: 0) → bascule immédiatement
  sur les modèles de fallback sans attente inutile
- Retry intelligent : respecte le retry_delay fourni par l'API (429/min)
"""
from __future__ import annotations

import io
import json
import logging
import re
import time
from typing import Dict, Any

from PIL import Image

from config import (
    GEMINI_API_KEY, GEMINI_MODEL, GEMINI_FALLBACK_MODELS,
    MAX_RETRIES, DOCUMENT_TYPES,
)
from utils.helpers import clean_json_response

logger = logging.getLogger("ocr_service.ocr")

# ── Init SDK ──────────────────────────────────────────────────────────────────
_SDK    = None
_client = None
_legacy_genai   = None
_legacy_model   = None

try:
    from google import genai
    from google.genai import types as genai_types
    _client = genai.Client(api_key=GEMINI_API_KEY)
    _SDK    = "new"
    logger.debug("✓ SDK google.genai chargé.")
except ImportError:
    pass

if _SDK is None:
    try:
        import google.generativeai as _legacy_genai
        _legacy_genai.configure(api_key=GEMINI_API_KEY)
        _SDK = "legacy"
        logger.warning("Fallback google.generativeai (déprécié). pip install google-genai")
    except ImportError:
        raise ImportError("Aucun SDK Gemini trouvé. Lance : pip install google-genai")


# ── Prompt ────────────────────────────────────────────────────────────────────
_SYSTEM_PROMPT = f"""
Tu es un expert comptable et juridique français.
Tu analyses des images de documents administratifs (factures, devis, RIB, Kbis, URSSAF…).

RÈGLES CRITIQUES :
1. Commence IMMÉDIATEMENT par {{ — aucun texte avant.
2. Termine par }} — aucun texte après, pas de balises markdown.
3. Champs absents → null. Montants → float. Dates → YYYY-MM-DD. SIRET → 14 chiffres sans espaces.
4. Types : {", ".join(DOCUMENT_TYPES)}
5. texte_brut : maximum 200 caractères (résumé court). JAMAIS de texte long.
6. ORDRE IMPÉRATIF des clés : type_document → confiance → champs → anomalies → qualite_scan → texte_brut
7. DÉTECTION DOCUMENT ÉTRANGER : Si le document est émis par une entreprise étrangère (UK, US, etc.), sans SIRET ni adresse française, utilise type_document = "facture_etrangere".
8. NE JAMAIS INVENTER : Si un champ (siret, iban, tva, montant...) n'est PAS EXPLICITEMENT écrit dans le document, retourne null. INTERDIT d'inventer ou déduire des valeurs absentes.
9. COHÉRENCE MONTANTS : Ne retourne que les montants réellement écrits dans le document. Ne calcule rien.

STRUCTURE EXACTE (respecter l'ordre des clés) :
{{
  "type_document": "<type>",
  "confiance": <0.0-1.0>,
  "champs": {{
    "siret": null,
    "siren": null,
    "raison_sociale": null,
    "date_emission": null,
    "date_expiration": null,
    "montant_ht": null,
    "montant_ttc": null,
    "tva_taux": null,
    "numero_document": null,
    "iban": null,
    "bic": null,
    "emetteur": null,
    "destinataire": null,
    "adresse_emetteur": null,
    "adresse_destinataire": null
  }},
  "anomalies": [],
  "qualite_scan": "bonne",
  "texte_brut": "<résumé court max 200 chars>"
}}
"""
_USER_PROMPT = "Analyse ce document. Réponds avec UNIQUEMENT le JSON (ordre des clés obligatoire, texte_brut en dernier)."


# ── Helpers 429 ───────────────────────────────────────────────────────────────

def _parse_retry_delay(exc: Exception) -> float:
    """Extrait le retry_delay en secondes depuis le message d'erreur 429."""
    msg = str(exc)
    # Format proto : retryDelay: '55s' ou retry_delay { seconds: 37 }
    for pattern in [
        r"retryDelay['\"]?\s*[:=]\s*['\"]?(\d+)s",
        r"retry_delay\s*\{[^}]*seconds:\s*(\d+)",
        r"retry in (\d+(?:\.\d+)?)\s*s",
    ]:
        m = re.search(pattern, msg, re.IGNORECASE)
        if m:
            return float(m.group(1)) + 3.0
    return 65.0


def _is_rate_limit(exc: Exception) -> bool:
    msg = str(exc)
    return (
        "429" in msg
        or "ResourceExhausted" in type(exc).__name__
        or "RESOURCE_EXHAUSTED" in msg
    )


def _is_daily_quota_exhausted(exc: Exception) -> bool:
    """
    Détecte si le quota JOURNALIER est épuisé (limit: 0 ou PerDay dans violations).
    Dans ce cas, attendre n'a aucun sens → basculer sur le modèle suivant.
    """
    msg = str(exc)
    return (
        "limit: 0" in msg
        or "PerDay" in msg
        or "GenerateRequestsPerDay" in msg
        or "per_day" in msg.lower()
    )


# ── Appels API ────────────────────────────────────────────────────────────────

def _call_new_sdk(image: Image.Image, model: str) -> str:
    buf = io.BytesIO()
    image.save(buf, format="JPEG", quality=90)
    response = _client.models.generate_content(
        model=model,
        contents=[
            genai_types.Part.from_bytes(data=buf.getvalue(), mime_type="image/jpeg"),
            genai_types.Part.from_text(text=_SYSTEM_PROMPT + "\n\n" + _USER_PROMPT),
        ],
        config=genai_types.GenerateContentConfig(temperature=0.1, max_output_tokens=4096),
    )
    return response.text


def _call_legacy_sdk(image: Image.Image, model: str) -> str:
    m = _legacy_genai.GenerativeModel(model)
    response = m.generate_content(
        [_SYSTEM_PROMPT + "\n\n" + _USER_PROMPT, image],
        generation_config=_legacy_genai.GenerationConfig(temperature=0.1, max_output_tokens=4096),
    )
    return response.text


def _call_gemini(image: Image.Image, model: str) -> str:
    if _SDK == "new":
        return _call_new_sdk(image, model)
    return _call_legacy_sdk(image, model)


# ── Retry intelligent avec fallback de modèle ─────────────────────────────────

def _call_with_retry(image: Image.Image) -> tuple[str, str]:
    """
    Essaie GEMINI_MODEL, puis chaque modèle de GEMINI_FALLBACK_MODELS.
    Pour chaque modèle :
      - quota journalier épuisé → passe au modèle suivant immédiatement
      - quota par minute        → attend le retry_delay puis réessaie (MAX_RETRIES fois)
      - autre erreur            → backoff exponentiel

    Retourne (texte_réponse, modèle_utilisé).
    """
    all_models = [GEMINI_MODEL] + GEMINI_FALLBACK_MODELS

    for model in all_models:
        logger.info(f"  → Essai modèle : {model}")
        last_exc = None

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                text = _call_gemini(image, model)
                return text, model

            except Exception as exc:
                last_exc = exc

                if _is_rate_limit(exc):
                    if _is_daily_quota_exhausted(exc):
                        logger.warning(
                            f"  ⚠ Quota journalier épuisé pour {model} "
                            f"→ bascule sur le modèle suivant."
                        )
                        break  # passe au modèle suivant, pas la peine de retenter

                    # Quota par minute → attendre et retenter
                    wait = _parse_retry_delay(exc)
                    logger.warning(
                        f"  ⏳ Limite par minute sur {model} "
                        f"(tentative {attempt}/{MAX_RETRIES}) — attente {wait:.0f}s..."
                    )
                    if attempt < MAX_RETRIES:
                        time.sleep(wait)

                else:
                    # Erreur réseau / autre → backoff exponentiel
                    wait = min(5.0 * (2 ** (attempt - 1)), 60.0)
                    logger.warning(
                        f"  ⚠ Erreur {type(exc).__name__} sur {model} "
                        f"(tentative {attempt}/{MAX_RETRIES}) — retry dans {wait:.0f}s"
                    )
                    if attempt < MAX_RETRIES:
                        time.sleep(wait)

        if last_exc and not (_is_rate_limit(last_exc) and _is_daily_quota_exhausted(last_exc)):
            logger.error(f"  ✗ Échec définitif sur {model} après {MAX_RETRIES} tentatives.")

    raise RuntimeError(
        f"Tous les modèles Gemini sont en quota épuisé ou en erreur.\n"
        f"Modèles essayés : {', '.join(all_models)}\n"
        f"Attends la réinitialisation du quota (minuit heure du Pacifique) "
        f"ou active la facturation sur Google Cloud."
    )


# ── Point d'entrée public ─────────────────────────────────────────────────────

def extract_from_image(image: Image.Image, page_num: int = 1) -> Dict[str, Any]:
    """Envoie une image à Gemini et retourne le dict extrait."""
    logger.info(f"  → Page {page_num} — envoi à Gemini (SDK={_SDK})...")

    try:
        raw, model_used = _call_with_retry(image)
        logger.debug(f"  Réponse brute ({model_used}, {len(raw)} chars) : {raw[:300]}...")

        cleaned = clean_json_response(raw)

        try:
            result = json.loads(cleaned)
        except json.JSONDecodeError as je:
            # Log la réponse complète pour diagnostic
            logger.error(
                f"  ✗ JSON invalide après nettoyage.\n"
                f"  Réponse brute complète :\n{raw}\n"
                f"  Après nettoyage :\n{cleaned}\n"
                f"  Erreur : {je}"
            )
            raise

        result.setdefault("type_document", "inconnu")
        result.setdefault("confiance",      0.0)
        result.setdefault("texte_brut",     "")
        result.setdefault("champs",         {})
        result.setdefault("anomalies",      [])
        result.setdefault("qualite_scan",   "inconnue")
        result["_model_used"] = model_used

        if result["type_document"] not in DOCUMENT_TYPES:
            logger.warning(f"  Type non reconnu : '{result['type_document']}' → 'inconnu'")
            result["type_document"] = "inconnu"

        logger.info(
            f"  ✓ {result['type_document']} "
            f"(confiance {result['confiance']:.0%}, modèle: {model_used})"
        )
        return result

    except json.JSONDecodeError as e:
        logger.error(f"  ✗ JSON invalide : {e}")
        return _error_result(f"JSON invalide : {e}")

    except Exception as e:
        logger.error(f"  ✗ Échec page {page_num} : {e}")
        return _error_result(str(e))


def merge_page_results(pages: list[Dict[str, Any]]) -> Dict[str, Any]:
    if not pages:
        return _error_result("Aucune page")
    if len(pages) == 1:
        return pages[0]

    best   = max(pages, key=lambda p: p.get("confiance", 0))
    merged = {
        "type_document": best["type_document"],
        "confiance":     best["confiance"],
        "texte_brut":    "\n\n--- PAGE SUIVANTE ---\n\n".join(
            p.get("texte_brut", "") for p in pages
        ),
        "champs":        {},
        "anomalies":     [],
        "qualite_scan":  best["qualite_scan"],
    }

    all_keys = set()
    for p in pages:
        all_keys.update(p.get("champs", {}).keys())
    for key in all_keys:
        merged["champs"][key] = next(
            (p["champs"][key] for p in pages if p.get("champs", {}).get(key) is not None),
            None,
        )

    seen = set()
    for p in pages:
        for a in p.get("anomalies", []):
            if a not in seen:
                merged["anomalies"].append(a)
                seen.add(a)

    return merged


def _error_result(error_msg: str) -> Dict[str, Any]:
    return {
        "type_document": "inconnu",
        "confiance":      0.0,
        "texte_brut":     "",
        "champs":         {},
        "anomalies":      [f"Erreur extraction : {error_msg}"],
        "qualite_scan":   "inconnue",
    }
