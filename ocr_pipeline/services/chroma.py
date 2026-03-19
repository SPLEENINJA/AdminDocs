"""
services/chroma.py — Stockage vectoriel et recherche en langage naturel via ChromaDB

Deux usages :
  1. store_document(result)  → appelé dans pipeline.py après save_curated()
  2. query_documents(question) → appelé depuis l'UI chat
"""
from __future__ import annotations

import json
import logging
import os
from typing import List, Dict, Any

logger = logging.getLogger("ocr_service.chroma")

# ── Init ChromaDB (persistent local OU serveur Docker) ───────────────────────
# En local dev  : CHROMA_HOST non défini → stockage dans ./storage/chroma/
# En Docker     : CHROMA_HOST=chroma (nom du service compose) → HTTP client

def _get_client():
    """Retourne un client ChromaDB (local persistent ou HTTP)."""
    import chromadb

    host = os.getenv("CHROMA_HOST", "")
    if host:
        return chromadb.HttpClient(host=host, port=int(os.getenv("CHROMA_PORT", 8000)))
    # Mode local : persiste dans storage/chroma/
    persist_dir = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "storage", "chroma"
    )
    os.makedirs(persist_dir, exist_ok=True)
    return chromadb.PersistentClient(path=persist_dir)


def _get_collection():
    client = _get_client()
    return client.get_or_create_collection(
        name="documents",
        metadata={"hnsw:space": "cosine"},
    )


# ── Stockage ──────────────────────────────────────────────────────────────────

def store_document(result: Dict[str, Any], texte_brut: str = "") -> bool:
    """
    Stocke un document extrait dans ChromaDB.
    Appelé juste après save_curated() dans pipeline.py.

    Le contenu indexé = texte_brut + résumé JSON des champs clés.
    """
    try:
        collection = _get_collection()

        doc_id  = result.get("document_id", "unknown")
        champs  = result.get("champs") or {}

        # Contenu à indexer : texte OCR + champs structurés
        content_parts = []
        if texte_brut:
            content_parts.append(texte_brut[:1500])   # limite tokens

        # Résumé des champs importants pour la recherche
        champs_summary = []
        field_labels = {
            "raison_sociale":  "Entreprise",
            "siret":           "SIRET",
            "emetteur":        "Émetteur",
            "destinataire":    "Destinataire",
            "montant_ttc":     "Montant TTC",
            "montant_ht":      "Montant HT",
            "tva_taux":        "TVA",
            "date_emission":   "Date d'émission",
            "date_expiration": "Date d'expiration",
            "numero_document": "Numéro",
            "iban":            "IBAN",
        }
        for key, label in field_labels.items():
            val = champs.get(key)
            if val is not None:
                champs_summary.append(f"{label} : {val}")

        if champs_summary:
            content_parts.append("Champs extraits — " + " | ".join(champs_summary))

        content = "\n".join(content_parts) or f"Document {result.get('type_document','inconnu')}"

        # Métadonnées filtrées (ChromaDB n'accepte que str/int/float/bool)
        metadata = {
            "fichier_source":  str(result.get("fichier_source", "")),
            "type_document":   str(result.get("type_document", "inconnu")),
            "confiance":       float(result.get("confiance", 0.0)),
            "qualite_scan":    str(result.get("qualite_scan", "")),
            "raison_sociale":  str(champs.get("raison_sociale") or ""),
            "siret":           str(champs.get("siret") or ""),
            "montant_ttc":     float(champs.get("montant_ttc") or 0),
            "date_emission":   str(champs.get("date_emission") or ""),
            "anomalies":       json.dumps(result.get("anomalies", []), ensure_ascii=False),
        }

        collection.upsert(
            ids=[doc_id],
            documents=[content],
            metadatas=[metadata],
        )
        logger.info(f"  ✓ ChromaDB : document '{doc_id}' indexé")
        return True

    except Exception as e:
        logger.warning(f"  ⚠ ChromaDB store échoué (non bloquant) : {e}")
        return False


# ── Recherche ─────────────────────────────────────────────────────────────────

def query_documents(question: str, n_results: int = 5) -> List[Dict[str, Any]]:
    """
    Recherche les documents les plus proches de la question.
    Retourne une liste de résultats avec contenu + métadonnées.
    """
    try:
        collection = _get_collection()
        count = collection.count()
        if count == 0:
            return []

        results = collection.query(
            query_texts=[question],
            n_results=min(n_results, count),
            include=["documents", "metadatas", "distances"],
        )

        hits = []
        docs      = results.get("documents", [[]])[0]
        metas     = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        for doc, meta, dist in zip(docs, metas, distances):
            hits.append({
                "content":      doc,
                "metadata":     meta,
                "similarity":   round(1 - dist, 3),   # cosine distance → similarity
            })
        return hits

    except Exception as e:
        logger.warning(f"  ⚠ ChromaDB query échoué : {e}")
        return []


def count_documents() -> int:
    """Nombre de documents indexés dans ChromaDB."""
    try:
        return _get_collection().count()
    except Exception:
        return 0
