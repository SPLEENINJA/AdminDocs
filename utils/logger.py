# =============================================================================
# Utilitaire Logger – Journalisation simple du pipeline
# Fournit un logger configuré pour chaque étape de traitement.
# =============================================================================

import logging
import sys
from datetime import datetime


def get_logger(name: str = "pipeline", level: int = logging.INFO) -> logging.Logger:
    """
    Crée un logger formaté pour le pipeline de traitement.
    
    Args:
        name: Nom du logger (apparaît dans les logs)
        level: Niveau de log (DEBUG, INFO, WARNING, ERROR)
    
    Returns:
        Logger configuré
    
    Exemple d'utilisation :
        logger = get_logger("ocr_step")
        logger.info("Début du traitement OCR")
    """
    logger = logging.getLogger(name)

    # Éviter de doubler les handlers si déjà configuré
    if logger.handlers:
        return logger

    logger.setLevel(level)

    # Format lisible : [2026-03-16 10:30:00] [INFO] [pipeline] Message
    formatter = logging.Formatter(
        fmt="[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Handler console (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger


def log_step(logger: logging.Logger, step_name: str, status: str, details: str = ""):
    """
    Log structuré pour une étape du pipeline.
    
    Args:
        logger: Instance du logger
        step_name: Nom de l'étape (ex: "OCR", "ANOMALY", "CRM")
        status: Statut (START, SUCCESS, ERROR, SKIP)
        details: Détails supplémentaires
    """
    message = f"[STEP: {step_name}] [{status}]"
    if details:
        message += f" {details}"

    if status == "ERROR":
        logger.error(message)
    elif status == "SKIP":
        logger.warning(message)
    else:
        logger.info(message)


def log_pipeline_start(logger: logging.Logger, document_key: str):
    """Log le début du pipeline pour un document."""
    logger.info("=" * 60)
    logger.info(f"PIPELINE START – Document : {document_key}")
    logger.info(f"Timestamp : {datetime.utcnow().isoformat()}")
    logger.info("=" * 60)


def log_pipeline_end(logger: logging.Logger, document_key: str, success: bool = True):
    """Log la fin du pipeline pour un document."""
    status = "SUCCESS" if success else "FAILED"
    logger.info("=" * 60)
    logger.info(f"PIPELINE END – Document : {document_key} – Statut : {status}")
    logger.info(f"Timestamp : {datetime.utcnow().isoformat()}")
    logger.info("=" * 60)
