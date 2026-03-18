"""
models/document.py — Schémas Pydantic pour la validation des données extraites
"""
from __future__ import annotations
from datetime import date
from typing import Optional, List
from pydantic import BaseModel, field_validator
import re


class DocumentChamps(BaseModel):
    """Champs extraits du document."""
    siret:            Optional[str]  = None
    siren:            Optional[str]  = None
    raison_sociale:   Optional[str]  = None
    date_emission:    Optional[str]  = None   # ISO 8601 : YYYY-MM-DD
    date_expiration:  Optional[str]  = None
    montant_ht:       Optional[float] = None
    montant_ttc:      Optional[float] = None
    montant_acompte:  Optional[float] = None   # montant d'acompte déjà versé (valeur positive)
    tva_taux:         Optional[float] = None   # taux en % ex: 20.0
    tva_numero:       Optional[str]  = None   # numéro intracomm ex: "FR70253355702"
    numero_document:  Optional[str]  = None
    iban:             Optional[str]  = None
    bic:              Optional[str]  = None
    emetteur:         Optional[str]  = None
    destinataire:     Optional[str]  = None
    adresse_emetteur: Optional[str]  = None
    adresse_destinataire: Optional[str] = None

    @field_validator("siret")
    @classmethod
    def validate_siret(cls, v):
        if v is None:
            return v
        cleaned = re.sub(r"\s", "", v)
        if not re.fullmatch(r"\d{14}", cleaned):
            raise ValueError(f"SIRET invalide : '{v}' (doit contenir 14 chiffres)")
        return cleaned

    @field_validator("iban")
    @classmethod
    def validate_iban(cls, v):
        if v is None:
            return v
        cleaned = re.sub(r"\s", "", v).upper()
        if not re.fullmatch(r"[A-Z]{2}\d{2}[A-Z0-9]{1,30}", cleaned):
            raise ValueError(f"IBAN invalide : '{v}'")
        return cleaned


class DocumentResult(BaseModel):
    """Résultat complet d'un traitement OCR + classification."""
    # Métadonnées
    document_id:      str
    fichier_source:   str
    page:             int  = 1

    # Classification
    type_document:    str
    confiance:        float  # 0.0 → 1.0

    # Contenu extrait
    texte_brut:       str                  = ""   # texte OCR brut (zone Clean)
    champs:           DocumentChamps       = DocumentChamps()

    # Qualité & anomalies
    qualite_scan:     str                  = "inconnue"  # bonne / moyenne / mauvaise
    anomalies:        List[str]            = []

    # Validation post-extraction
    validation_errors: List[str]           = []

    class Config:
        use_enum_values = True
