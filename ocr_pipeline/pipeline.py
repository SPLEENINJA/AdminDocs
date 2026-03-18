"""
pipeline.py — Orchestrateur du pipeline complet pour un document
  1. Sauvegarde RAW
  2. Conversion en images
  3. OCR page par page via Gemini
  4. Fusion multi-pages
  5. Validation (champs + cohérence)
  6. Sauvegarde CLEAN + CURATED
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, Any, Optional

from config import PDF_DPI, LOGS_DIR
from utils.helpers import generate_document_id, file_sha256, is_supported_file
from utils.logger import get_logger
from services.pdf_converter import load_document_as_images, IMAGE_EXTENSIONS
from services.ocr import extract_from_image, merge_page_results
from services.validator import validate_single
from services.storage import save_raw, save_clean, save_curated

logger = get_logger("ocr_service.pipeline", LOGS_DIR)


def process_document(
    file_path: str,
    original_filename: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Pipeline complet pour un seul document.

    Args:
        file_path          : chemin vers le fichier (temp ou réel)
        original_filename  : vrai nom du fichier uploadé (ex: "facture_acme.pdf").
                             Si None, utilise path.name (peut être un nom tmp).
                             Toujours passer ce param depuis l'UI/API.
    Returns:
        dict complet sauvegardé en zone CURATED avec le bon nom.
    """
    path         = Path(file_path).resolve()
    # ← Vrai nom affiché dans l'historique
    display_name = original_filename.strip() if original_filename else path.name

    logger.info(f"\n{'═'*60}")
    logger.info(f"Traitement : {display_name}")

    if not path.exists():
        raise FileNotFoundError(f"Fichier introuvable : {path}")
    if not is_supported_file(str(path)):
        raise ValueError(f"Format non supporté : {path.suffix}")

    document_id = generate_document_id(str(path))
    sha256      = file_sha256(str(path))
    logger.info(f"  ID      : {document_id}")
    logger.info(f"  SHA-256 : {sha256[:16]}...")

    # ── Étape 1 : Sauvegarde RAW ───────────────────────────────────────────
    logger.info("[1/5] Sauvegarde zone RAW...")
    raw_path = save_raw(str(path), document_id)

    # ── Étape 2 : Chargement en images ────────────────────────────────────
    is_image = path.suffix.lower() in IMAGE_EXTENSIONS
    if is_image:
        logger.info("[2/5] Chargement image (pas de conversion — déjà une image)...")
    else:
        logger.info("[2/5] Conversion PDF → images...")
    pages, converted = load_document_as_images(str(path), dpi=PDF_DPI)
    logger.info(f"  → {len(pages)} page(s)" + (" [PDF converti]" if converted else " [image directe]"))

    # ── Étape 3 : OCR page par page ────────────────────────────────────────
    logger.info("[3/5] OCR + extraction via Gemini Vision...")
    page_results = []
    for i, page_img in enumerate(pages, start=1):
        logger.info(f"  Page {i}/{len(pages)}")
        result = extract_from_image(page_img, page_num=i)
        result["_page"] = i
        page_results.append(result)

    # ── Étape 4 : Fusion multi-pages ───────────────────────────────────────
    logger.info("[4/5] Fusion des pages...")
    merged = merge_page_results(page_results)

    # ── Étape 5 : Validation ───────────────────────────────────────────────
    logger.info("[5/5] Validation des champs...")
    validation_errors = validate_single(
        merged["type_document"],
        merged.get("champs", {}),
    )
    if validation_errors:
        for err in validation_errors:
            logger.warning(f"  ⚠ {err}")
    else:
        logger.info("  ✓ Aucune erreur de validation")

    # ── Assemblage du résultat final ───────────────────────────────────────
    final_result = {
        "document_id":       document_id,
        "fichier_source":    display_name,   # ← nom original, pas le nom tmp
        "sha256":            sha256,
        "nb_pages":          len(pages),
        "chemin_raw":        str(raw_path),
        "type_document":     merged["type_document"],
        "confiance":         merged["confiance"],
        "champs":            merged.get("champs", {}),
        "qualite_scan":      merged["qualite_scan"],
        "anomalies":         merged.get("anomalies", []),
        "validation_errors": validation_errors,
    }

    # ── Sauvegarde CLEAN + CURATED ────────────────────────────────────────
    save_clean(document_id, merged.get("texte_brut", ""))
    save_curated(document_id, final_result)

    status = "✓ OK" if not validation_errors else f"⚠ {len(validation_errors)} erreur(s)"
    logger.info(
        f"\nRésultat : [{final_result['type_document']}] "
        f"confiance={final_result['confiance']:.0%} | {status}"
    )
    return final_result


def process_batch(
    file_paths: list[str],
    original_filenames: Optional[list[str]] = None,
) -> list[Dict[str, Any]]:
    """
    Traite une liste de documents.

    Args:
        file_paths         : chemins des fichiers (temp ou réels)
        original_filenames : noms originaux correspondants (même ordre).
                             Si None, utilise les noms des paths.
    """
    results = []
    total   = len(file_paths)
    names   = original_filenames or [Path(p).name for p in file_paths]

    logger.info(f"\n{'═'*60}")
    logger.info(f"Batch : {total} document(s)")

    for i, (fp, name) in enumerate(zip(file_paths, names), start=1):
        logger.info(f"\n[{i}/{total}] {name}")
        try:
            result = process_document(fp, original_filename=name)
            results.append(result)
        except Exception as e:
            logger.error(f"  ✗ Erreur sur '{name}' : {e}")
            results.append({
                "fichier_source": name,
                "type_document":  "inconnu",
                "erreur":         str(e),
            })

    ok      = sum(1 for r in results if "erreur" not in r)
    erreurs = total - ok
    logger.info(f"\n{'═'*60}")
    logger.info(f"Batch terminé : {ok}/{total} OK, {erreurs} erreur(s)")
    return results
