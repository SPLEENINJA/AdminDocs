# =============================================================================
# Anomaly Detector Service – FastAPI  (v2.0 – Hackathon 2026)
#
# Endpoints :
#   POST /analyze          → analyse un seul document
#   POST /analyze-cross    → cohérence inter-documents (SIRET, raison sociale…)
#   GET  /health           → healthcheck Docker
#
# Règles implémentées (10) :
#   1.  IMAGE_QUALITY_LOW        – confiance OCR < 0.75 ou qualite_scan mauvaise
#   2.  DOC_TYPE_MISMATCH        – type déclaré ≠ type détecté par Gemini
#   3.  MISSING_REQUIRED_FIELD   – champ obligatoire absent selon le type
#   4.  INVALID_SIRET             – SIRET 14 chiffres invalide (Luhn)
#   5.  INVALID_SIREN             – SIREN 9 chiffres invalide (Luhn)
#   6.  TVA_NUMBER_MISMATCH      – N° TVA incohérent avec le SIRET
#   7.  TTC_INCONSISTENT         – HT + TVA ≠ TTC (tolérance 0.05 €)
#   8.  ATTESTATION_EXPIRED      – date d'expiration dépassée
#   9.  SIRET_MISMATCH           – SIRET différent entre documents (cross-doc)
#  10.  COMPANY_NAME_MISMATCH    – raison sociale différente (cross-doc)
#
# Score de risque : high=35 / medium=20 / low=10 — plafonné à 100
# =============================================================================

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import uuid
import re
from datetime import datetime

app = FastAPI(title="Anomaly Detector Service — AdminDocs", version="2.0.0")


RISK_WEIGHTS: Dict[str, int] = {"high": 35, "medium": 20, "low": 10}
MAX_RISK = 100

# Champs obligatoires par type de document
REQUIRED_FIELDS: Dict[str, List[str]] = {
    "facture":              ["raison_sociale", "siret", "montant_ttc", "date_emission"],
    "devis":                ["raison_sociale", "siret", "montant_ttc"],
    "attestation":          ["raison_sociale", "siret", "date_expiration"],
    "attestation_urssaf":   ["raison_sociale", "siret", "date_expiration"],
    "kbis":                 ["raison_sociale", "siren", "date_emission"],
    "rib":                  ["iban", "bic", "titulaire"],
    "cni":                  ["nom", "prenom", "date_naissance", "numero_document"],
    "passeport":            ["nom", "prenom", "date_naissance", "numero_document", "date_expiration"],
    "default":              [],
}

# Types pour lesquels la date_expiration doit être contrôlée
ATTESTATION_TYPES = {"attestation", "attestation_urssaf", "attestation_fiscale", "kbis"}


# Modèles

class AnomalyRequest(BaseModel):
    """Requête d'analyse d'un seul document."""
    document_key: str
    ocr_result: Dict[str, Any]          # {confidence, fields, qualite_scan, …}
    document_type: Optional[str] = "inconnu"
    declared_type: Optional[str] = None  # type déclaré par l'utilisateur au moment de l'upload


class CrossDocRequest(BaseModel):
    """Requête de vérification inter-documents (cohérence d'un dossier)."""
    documents: List[Dict[str, Any]]     # liste de {document_key, fields, document_type}


# Utilitaires de validation

def _clean_digits(value: Any) -> str:
    """Supprime tous les caractères non-numériques."""
    return re.sub(r"\D", "", str(value or ""))


def _luhn_ok(number: str) -> bool:
    """Vérifie un numéro par l'algorithme de Luhn (SIRET, SIREN)."""
    if not number.isdigit():
        return False
    total = 0
    for i, d in enumerate(reversed(number)):
        n = int(d)
        if i % 2 == 1:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total % 10 == 0


def validate_siret(raw: Any) -> bool:
    s = _clean_digits(raw)
    return len(s) == 14 and _luhn_ok(s)


def validate_siren(raw: Any) -> bool:
    s = _clean_digits(raw)
    return len(s) == 9 and _luhn_ok(s)


def parse_date(raw: Any) -> Optional[datetime]:
    """Parse une date dans plusieurs formats courants."""
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(str(raw).strip(), fmt)
        except ValueError:
            continue
    return None


def parse_amount(raw: Any) -> Optional[float]:
    """Convertit une valeur monétaire en float (gère espaces, virgules, €)."""
    if raw is None:
        return None
    try:
        cleaned = re.sub(r"[^\d,\.]", "", str(raw)).replace(",", ".")
        return float(cleaned)
    except ValueError:
        return None


def _empty(v: Any) -> bool:
    return not v or str(v).strip().lower() in ("", "n/a", "null", "none", "inconnu")


def compute_risk_score(anomalies: List[Dict]) -> int:
    total = sum(RISK_WEIGHTS.get(a.get("severity", "low"), 10) for a in anomalies)
    return min(total, MAX_RISK)


# Moteur d'analyse — toutes les règles sur un document

def _run_rules(
    document_key: str,
    confidence: float,
    fields: Dict[str, Any],
    qualite_scan: str,
    document_type: str,
    declared_type: Optional[str],
) -> List[Dict]:
    """Exécute les 8 règles mono-document et retourne la liste des anomalies."""
    anomalies: List[Dict] = []
    doc_type = (document_type or "inconnu").lower().strip()

    # ── 1. IMAGE_QUALITY_LOW ─────────────────────────────────────────────────
    BAD_QUALITY = {"mauvaise", "très_mauvaise", "tres_mauvaise", "mauvais", "bad", "low"}
    if qualite_scan and qualite_scan.lower().replace(" ", "_") in BAD_QUALITY:
        anomalies.append({
            "type": "IMAGE_QUALITY_LOW",
            "severity": "high",
            "message": "Document trop flou ou de mauvaise qualité, merci de redéposer une pièce plus nette.",
            "suggestion": "Scanner ou photographier à la lumière du jour, sans flou, en haute résolution.",
            "details": {"qualite_scan": qualite_scan},
        })
    elif confidence < 0.50:
        anomalies.append({
            "type": "IMAGE_QUALITY_LOW",
            "severity": "high",
            "message": f"Confiance OCR trop faible ({confidence:.0%}) — document illisible.",
            "suggestion": "Document trop flou ou de mauvaise qualité, merci de redéposer une pièce plus nette.",
            "details": {"confidence": round(confidence, 3)},
        })
    elif confidence < 0.75:
        anomalies.append({
            "type": "IMAGE_QUALITY_LOW",
            "severity": "medium",
            "message": f"Qualité d'image insuffisante (confiance OCR : {confidence:.0%}).",
            "suggestion": "Document trop flou ou de mauvaise qualité, merci de redéposer une pièce plus nette.",
            "details": {"confidence": round(confidence, 3)},
        })

    # ── 2. DOC_TYPE_MISMATCH ─────────────────────────────────────────────────
    if declared_type and doc_type not in ("inconnu", "unknown", "", "other"):
        if declared_type.lower().strip() != doc_type:
            anomalies.append({
                "type": "DOC_TYPE_MISMATCH",
                "severity": "high",
                "message": (
                    f"Type déclaré '{declared_type}' ≠ type détecté '{doc_type}' par le modèle."
                ),
                "suggestion": "Vérifier que le bon document a été uploadé.",
                "details": {"declared": declared_type, "detected": doc_type},
            })

    # ── 3. MISSING_REQUIRED_FIELD ─────────────────────────────────────────────
    required = REQUIRED_FIELDS.get(doc_type, REQUIRED_FIELDS["default"])
    for field in required:
        if _empty(fields.get(field)):
            anomalies.append({
                "type": "MISSING_REQUIRED_FIELD",
                "severity": "high",
                "message": f"Champ obligatoire absent pour un «{doc_type}» : '{field}'.",
                "suggestion": f"S'assurer que '{field}' est bien visible et lisible sur le document.",
                "details": {"field": field, "document_type": doc_type},
            })

    # ── 4. INVALID_SIRET ─────────────────────────────────────────────────────
    siret_raw = fields.get("siret") or fields.get("numero_siret")
    if siret_raw and not _empty(siret_raw):
        if not validate_siret(siret_raw):
            anomalies.append({
                "type": "INVALID_SIRET",
                "severity": "high",
                "message": f"SIRET invalide : '{siret_raw}' (14 chiffres + clé Luhn incorrecte).",
                "suggestion": "Vérifier le numéro SIRET sur le document.",
                "details": {"siret": siret_raw},
            })

    # ── 5. INVALID_SIREN ─────────────────────────────────────────────────────
    siren_raw = fields.get("siren") or fields.get("numero_siren")
    if siren_raw and not _empty(siren_raw):
        if not validate_siren(siren_raw):
            anomalies.append({
                "type": "INVALID_SIREN",
                "severity": "medium",
                "message": f"SIREN invalide : '{siren_raw}' (9 chiffres + clé Luhn incorrecte).",
                "suggestion": "Vérifier le SIREN (9 premiers chiffres du SIRET).",
                "details": {"siren": siren_raw},
            })
    elif siret_raw and validate_siret(siret_raw):
        # Dériver le SIREN depuis le SIRET et vérifier
        siren_derived = _clean_digits(siret_raw)[:9]
        if not validate_siren(siren_derived):
            anomalies.append({
                "type": "INVALID_SIREN",
                "severity": "medium",
                "message": f"SIREN dérivé du SIRET invalide : '{siren_derived}'.",
                "suggestion": "Vérifier la cohérence SIREN/SIRET.",
                "details": {"siren_derived": siren_derived},
            })

    # ── 6. TVA_NUMBER_MISMATCH ────────────────────────────────────────────────
    tva_raw = fields.get("numero_tva") or fields.get("tva_intracommunautaire")
    if tva_raw and siret_raw and not _empty(tva_raw):
        tva_clean = re.sub(r"\s", "", str(tva_raw)).upper()
        siret_clean = _clean_digits(str(siret_raw))
        # Format TVA FR : FR + 2 chars clé + 9 chiffres SIREN
        if tva_clean.startswith("FR") and len(tva_clean) == 13:
            tva_siren = tva_clean[4:]
            if siret_clean[:9] != tva_siren:
                anomalies.append({
                    "type": "TVA_NUMBER_MISMATCH",
                    "severity": "medium",
                    "message": (
                        f"N° TVA '{tva_raw}' incohérent avec le SIRET '{siret_raw}' "
                        f"(SIREN extrait du TVA : {tva_siren} ≠ {siret_clean[:9]})."
                    ),
                    "suggestion": "Vérifier la correspondance entre le SIREN du SIRET et le N° TVA.",
                    "details": {"numero_tva": tva_raw, "siret": siret_raw},
                })

    # ── 7. TTC_INCONSISTENT ──────────────────────────────────────────────────
    ht  = parse_amount(fields.get("montant_ht"))
    tva = parse_amount(fields.get("montant_tva"))
    ttc = parse_amount(fields.get("montant_ttc"))
    if ht is not None and tva is not None and ttc is not None and ttc > 0:
        expected = round(ht + tva, 2)
        if abs(expected - ttc) > 0.05:
            anomalies.append({
                "type": "TTC_INCONSISTENT",
                "severity": "high",
                "message": (
                    f"Incohérence montants : HT ({ht}€) + TVA ({tva}€) = {expected}€ ≠ TTC ({ttc}€). "
                    f"Écart : {abs(expected - ttc):.2f}€."
                ),
                "suggestion": "Vérifier les montants sur la facture — possible erreur d'OCR sur un chiffre.",
                "details": {
                    "montant_ht": ht, "montant_tva": tva,
                    "montant_ttc": ttc, "expected_ttc": expected,
                },
            })

    # ── 8. ATTESTATION_EXPIRED ───────────────────────────────────────────────
    if doc_type in ATTESTATION_TYPES:
        date_exp_raw = fields.get("date_expiration") or fields.get("date_validite")
        if date_exp_raw and not _empty(date_exp_raw):
            parsed = parse_date(date_exp_raw)
            if parsed:
                delta = (parsed - datetime.utcnow()).days
                if delta < 0:
                    anomalies.append({
                        "type": "ATTESTATION_EXPIRED",
                        "severity": "high",
                        "message": (
                            f"Attestation expirée depuis {abs(delta)} jour(s) "
                            f"(expiration : {date_exp_raw})."
                        ),
                        "suggestion": "Demander un document à jour auprès de l'organisme compétent.",
                        "details": {"date_expiration": date_exp_raw, "jours_expires": abs(delta)},
                    })
                elif delta < 30:
                    anomalies.append({
                        "type": "ATTESTATION_EXPIRED",
                        "severity": "low",
                        "message": (
                            f"Attestation expire dans {delta} jour(s) ({date_exp_raw}). "
                            f"Prévoir le renouvellement."
                        ),
                        "suggestion": "Anticiper le renouvellement du document.",
                        "details": {"date_expiration": date_exp_raw, "jours_restants": delta},
                    })
            else:
                anomalies.append({
                    "type": "ATTESTATION_EXPIRED",
                    "severity": "low",
                    "message": f"Format de date d'expiration non reconnu : '{date_exp_raw}'.",
                    "suggestion": "Format attendu : JJ/MM/AAAA ou AAAA-MM-JJ.",
                    "details": {"date_expiration": date_exp_raw},
                })

    return anomalies


# Endpoints

@app.get("/health")
def health():
    """Healthcheck Docker."""
    return {"status": "ok", "service": "anomaly-service", "version": "2.0.0"}


@app.post("/analyze")
async def analyze(request: AnomalyRequest):
    """
    Analyse un document unique.
    Retourne les anomalies détectées + score de risque.
    Compatible avec le DAG Airflow existant.
    """
    ocr = request.ocr_result
    fields      = ocr.get("fields", ocr.get("champs", {}))
    confidence  = float(ocr.get("confidence", ocr.get("confiance", 1.0)))
    qualite_scan = str(ocr.get("qualite_scan", ""))
    doc_type    = str(request.document_type or "inconnu")
    declared    = request.declared_type

    anomalies = _run_rules(
        request.document_key,
        confidence,
        fields,
        qualite_scan,
        doc_type,
        declared,
    )

    risk_score = compute_risk_score(anomalies)
    is_valid   = len(anomalies) == 0

    result = {
        "analysis_id":    str(uuid.uuid4()),
        "document_key":   request.document_key,
        "analyzed_at":    datetime.utcnow().isoformat(),
        "document_type":  doc_type,
        "is_valid":       is_valid,
        "is_anomalous":   not is_valid,
        "risk_score":     risk_score,
        "anomaly_count":  len(anomalies),
        "anomalies":      anomalies,
        "message":        (
            "✓ Document valide — aucune anomalie détectée."
            if is_valid
            else f"⚠ {len(anomalies)} anomalie(s) détectée(s) — score de risque : {risk_score}/100."
        ),
        "recommendation": (
            "Document conforme, traitement automatique possible."
            if is_valid
            else "Vérification manuelle recommandée avant traitement."
        ),
    }
    return JSONResponse(content=result, status_code=200)


@app.post("/analyze-cross")
async def analyze_cross(request: CrossDocRequest):
    """
    Vérifie la cohérence inter-documents d'un même dossier.
    Détecte :
      - SIRET_MISMATCH         : SIRET différents entre documents
      - COMPANY_NAME_MISMATCH  : raisons sociales différentes
      - TVA_NUMBER_MISMATCH    : numéros TVA différents
    """
    cross_anomalies: List[Dict] = []

    # Collecter les valeurs par document
    sirets:    Dict[str, str] = {}
    names:     Dict[str, str] = {}
    tva_nums:  Dict[str, str] = {}

    for doc in request.documents:
        key    = doc.get("document_key", "?")
        fields = doc.get("fields", {})

        siret = _clean_digits(str(fields.get("siret", "") or ""))
        if siret:
            sirets[key] = siret

        name = str(fields.get("raison_sociale", "") or "").strip().upper()
        if name and not _empty(name):
            names[key] = name

        tva = re.sub(r"\s", "", str(fields.get("numero_tva", "") or "")).upper()
        if tva and not _empty(tva):
            tva_nums[key] = tva

    # ── SIRET_MISMATCH ────────────────────────────────────────────────────────
    unique_sirets = set(sirets.values())
    if len(unique_sirets) > 1:
        cross_anomalies.append({
            "type": "SIRET_MISMATCH",
            "severity": "high",
            "message": (
                f"SIRET différents entre les documents du dossier : {unique_sirets}. "
                "Les documents ne semblent pas appartenir à la même entreprise."
            ),
            "suggestion": "Vérifier que tous les documents concernent la même entité.",
            "details": {"sirets_par_document": sirets},
        })

    # ── COMPANY_NAME_MISMATCH ─────────────────────────────────────────────────
    unique_names = set(names.values())
    if len(unique_names) > 1:
        # Tolérance : un nom contenu dans l'autre (ex. "SARL DUPONT" vs "DUPONT")
        names_list = list(unique_names)
        is_mismatch = True
        if len(names_list) == 2:
            a, b = names_list
            if a in b or b in a:
                is_mismatch = False
        if is_mismatch:
            cross_anomalies.append({
                "type": "COMPANY_NAME_MISMATCH",
                "severity": "medium",
                "message": "Raisons sociales différentes détectées entre les documents.",
                "suggestion": "Vérifier la cohérence des noms d'entreprise sur l'ensemble du dossier.",
                "details": {"noms_par_document": names},
            })

    # ── TVA_NUMBER_MISMATCH (inter-docs) ──────────────────────────────────────
    unique_tva = set(tva_nums.values())
    if len(unique_tva) > 1:
        cross_anomalies.append({
            "type": "TVA_NUMBER_MISMATCH",
            "severity": "medium",
            "message": "Numéros TVA intracommunautaires différents entre les documents.",
            "suggestion": "Vérifier la cohérence des N° TVA dans le dossier.",
            "details": {"tva_par_document": tva_nums},
        })

    risk_score = compute_risk_score(cross_anomalies)

    return JSONResponse(content={
        "analysis_id":          str(uuid.uuid4()),
        "analyzed_at":          datetime.utcnow().isoformat(),
        "documents_analyzed":   len(request.documents),
        "is_coherent":          len(cross_anomalies) == 0,
        "is_anomalous":         len(cross_anomalies) > 0,
        "risk_score":           risk_score,
        "cross_anomaly_count":  len(cross_anomalies),
        "cross_anomalies":      cross_anomalies,
        "message": (
            f"✓ Dossier cohérent — {len(request.documents)} document(s) analysé(s), aucune incohérence."
            if not cross_anomalies
            else f"⚠ {len(cross_anomalies)} incohérence(s) inter-documents — score risque : {risk_score}/100."
        ),
    }, status_code=200)


@app.get("/results")
async def list_results():
    """Endpoint de démo — retourne des exemples de résultats."""
    return {
        "info": "Appelez POST /analyze pour analyser un document.",
        "exemple_valide": "Voir scripts/demo_scenarios.py",
        "endpoints": ["/health", "/analyze", "/analyze-cross", "/results"],
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
