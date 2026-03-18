"""
services/validator.py — Vérification de cohérence et validation des champs extraits
Gère les valeurs float retournées par Gemini (ex: SIRET=12345678901234.0)
"""
from __future__ import annotations

import re
import logging
from datetime import date, datetime
from typing import List, Dict, Any, Optional

logger = logging.getLogger("ocr_service.validator")


# ── Helper : normalisation des valeurs Gemini ─────────────────────────────────

def _to_str(v: Any) -> str:
    """
    Convertit n'importe quelle valeur en string propre.
    Gère notamment le cas Gemini où SIRET/SIREN arrive en float :
      12345678901234.0  →  "12345678901234"
    """
    if v is None:
        return ""
    if isinstance(v, float):
        # 12345678901234.0 → "12345678901234"
        return str(int(v)) if v == int(v) else str(v)
    return str(v).strip()


def _coerce_champs(champs: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalise tous les champs string du dict en str propres.
    Modifie le dict en place ET le retourne.
    """
    str_fields = {"siret", "siren", "iban", "bic", "numero_document",
                  "raison_sociale", "emetteur", "destinataire",
                  "date_emission", "date_expiration", "tva_taux"}
    for k in str_fields:
        v = champs.get(k)
        if v is not None:
            champs[k] = _to_str(v)
    return champs


# ── Validation d'un document unique ──────────────────────────────────────────

def validate_single(doc_type: str, champs: Dict[str, Any]) -> List[str]:
    """
    Valide les champs d'un seul document.
    Retourne une liste d'erreurs (vide = OK).
    """
    # Normalise d'abord pour éviter les erreurs de type float
    _coerce_champs(champs)
    errors: List[str] = []

    # SIRET : 14 chiffres
    siret = champs.get("siret")
    if siret:
        cleaned = re.sub(r"\s", "", siret)
        if not re.fullmatch(r"\d{14}", cleaned):
            errors.append(f"SIRET invalide : '{siret}' (doit être 14 chiffres)")
        else:
            champs["siret"] = cleaned  # normalise sans espaces

    # SIREN : 9 chiffres
    siren = champs.get("siren")
    if siren:
        cleaned = re.sub(r"\s", "", siren)
        if not re.fullmatch(r"\d{9}", cleaned):
            errors.append(f"SIREN invalide : '{siren}' (doit être 9 chiffres)")
        else:
            champs["siren"] = cleaned

    # Cohérence SIREN ↔ SIRET
    siret_v = champs.get("siret", "")
    siren_v = champs.get("siren", "")
    if siret_v and siren_v:
        s1 = re.sub(r"\s", "", siret_v)
        s2 = re.sub(r"\s", "", siren_v)
        if s1 and s2 and not s1.startswith(s2):
            errors.append(
                f"Incohérence SIRET/SIREN : SIRET '{s1}' ne commence pas par SIREN '{s2}'"
            )

    # Date expiration (attestation)
    date_exp = champs.get("date_expiration")
    if date_exp:
        parsed = _parse_date(date_exp)
        if parsed and parsed < date.today():
            errors.append(
                f"Document expiré : date_expiration '{date_exp}' est dans le passé"
            )

    # Cohérence montants facture
    if doc_type == "facture":
        ht  = champs.get("montant_ht")
        ttc = champs.get("montant_ttc")
        tva = champs.get("tva_taux")

        if ht is not None and ttc is not None:
            try:
                ht_f  = float(ht)
                ttc_f = float(ttc)
                if ttc_f < ht_f:
                    errors.append(f"Incohérence montants : TTC ({ttc_f}) < HT ({ht_f})")
                if tva:
                    taux = _parse_taux_tva(str(tva))
                    if taux:
                        ttc_calc = round(ht_f * (1 + taux), 2)
                        if abs(ttc_calc - ttc_f) > 1.0:
                            errors.append(
                                f"TVA incohérente : HT={ht_f}, TVA={tva} "
                                f"→ TTC attendu≈{ttc_calc}, reçu={ttc_f}"
                            )
            except (ValueError, TypeError):
                pass  # valeurs non numériques → ignorer

    # IBAN
    iban = champs.get("iban")
    if iban:
        cleaned = re.sub(r"\s", "", iban).upper()
        if not re.fullmatch(r"[A-Z]{2}\d{2}[A-Z0-9]{1,30}", cleaned):
            errors.append(f"IBAN invalide : '{iban}'")
        else:
            champs["iban"] = cleaned

    return errors


# ── Validation croisée inter-documents ───────────────────────────────────────

def validate_cross(documents: List[Dict[str, Any]]) -> List[str]:
    """
    Vérifie la cohérence entre plusieurs documents d'un même dossier.
    """
    warnings: List[str] = []
    sirets: Dict[str, str] = {}

    for doc in documents:
        t = doc.get("type_document", "inconnu")
        champs = doc.get("champs") or {}
        raw = champs.get("siret") or doc.get("siret_emetteur")
        if raw:
            sirets[t] = re.sub(r"\s", "", _to_str(raw))

    if len(sirets) > 1:
        unique_sirets = set(sirets.values())
        if len(unique_sirets) > 1:
            detail = ", ".join(f"{t}={s}" for t, s in sirets.items())
            warnings.append(f"⚠ SIRET différents entre documents : {detail}")

    return warnings


# ── Helpers privés ────────────────────────────────────────────────────────────

def _parse_date(value: Any) -> Optional[date]:
    if not value:
        return None
    s = _to_str(value)
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _parse_taux_tva(tva_str: str) -> Optional[float]:
    match = re.search(r"(\d+(?:[.,]\d+)?)", tva_str)
    if match:
        return float(match.group(1).replace(",", ".")) / 100
    return None
