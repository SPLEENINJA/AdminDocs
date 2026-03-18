"""
main.py — Point d'entrée CLI

Usages :
    # Traiter un seul fichier
    python main.py document.pdf

    # Traiter plusieurs fichiers
    python main.py facture1.pdf devis.png rib.jpg

    # Traiter un dossier entier
    python main.py --dir ./input_docs

    # Lister les documents traités
    python main.py --list

    # Stats du stockage
    python main.py --stats
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from config import validate_config, LOGS_DIR
from utils.logger import get_logger, console
from pipeline import process_document, process_batch
from services.storage import list_curated, storage_summary
from services.validator import validate_cross
from rich.table import Table
from rich.panel import Panel
from rich import print as rprint

logger = get_logger("ocr_service.main", LOGS_DIR)


# ── CLI ───────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="ocr_service",
        description="OCR + Classification de documents via Gemini Vision",
    )
    p.add_argument(
        "files", nargs="*",
        help="Fichiers à traiter (PDF, PNG, JPG…)"
    )
    p.add_argument(
        "--dir", "-d",
        help="Dossier à traiter (tous les fichiers supportés)",
        default=None,
    )
    p.add_argument(
        "--list", "-l",
        action="store_true",
        help="Lister les derniers documents traités",
    )
    p.add_argument(
        "--stats", "-s",
        action="store_true",
        help="Afficher les statistiques de stockage",
    )
    p.add_argument(
        "--cross-validate", "-x",
        action="store_true",
        help="Vérification croisée des N derniers documents",
    )
    p.add_argument(
        "--output", "-o",
        help="Fichier JSON de sortie pour le résultat (optionnel)",
        default=None,
    )
    return p


# ── Affichage résultats ───────────────────────────────────────────────────────

def print_result(result: dict) -> None:
    """Affiche le résultat d'un document dans la console."""
    status_color = "green" if not result.get("validation_errors") else "yellow"

    panel = Panel(
        f"[bold]Type :[/bold]      {result.get('type_document', '?')}\n"
        f"[bold]Confiance :[/bold] {result.get('confiance', 0):.0%}\n"
        f"[bold]Qualité :[/bold]   {result.get('qualite_scan', '?')}\n"
        f"[bold]Anomalies :[/bold] {len(result.get('anomalies', []))}\n"
        f"[bold]Erreurs :[/bold]   {len(result.get('validation_errors', []))}",
        title=f"[{status_color}]{result.get('fichier_source', 'Document')}[/{status_color}]",
        border_style=status_color,
    )
    console.print(panel)

    champs = result.get("champs", {})
    if any(v is not None for v in champs.values()):
        table = Table(title="Champs extraits", show_header=True)
        table.add_column("Champ",   style="cyan",  no_wrap=True)
        table.add_column("Valeur",  style="white")
        for k, v in champs.items():
            if v is not None:
                table.add_row(k, str(v))
        console.print(table)

    if result.get("anomalies"):
        rprint(f"\n[yellow]⚠ Anomalies :[/yellow]")
        for a in result["anomalies"]:
            rprint(f"  • {a}")

    if result.get("validation_errors"):
        rprint(f"\n[red]✗ Erreurs de validation :[/red]")
        for e in result["validation_errors"]:
            rprint(f"  • {e}")


def print_list(documents: list[dict]) -> None:
    table = Table(title=f"Documents traités ({len(documents)})", show_header=True)
    table.add_column("ID",           style="dim",    no_wrap=True, max_width=30)
    table.add_column("Fichier",      style="cyan")
    table.add_column("Type",         style="green")
    table.add_column("Confiance",    style="yellow")
    table.add_column("Erreurs",      style="red")
    for doc in documents:
        table.add_row(
            doc.get("document_id", "?")[:25] + "…",
            doc.get("fichier_source", "?"),
            doc.get("type_document", "?"),
            f"{doc.get('confiance', 0):.0%}",
            str(len(doc.get("validation_errors", []))),
        )
    console.print(table)


def print_stats(stats: dict) -> None:
    table = Table(title="Stockage local", show_header=True)
    table.add_column("Zone",      style="cyan")
    table.add_column("Fichiers",  style="white", justify="right")
    table.add_row("Raw (originaux)",     str(stats["raw"]))
    table.add_row("Clean (texte OCR)",   str(stats["clean"]))
    table.add_row("Curated (JSON)",      str(stats["curated"]))
    console.print(table)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = build_parser()
    args   = parser.parse_args()

    # Validation config (clé API, etc.)
    try:
        validate_config()
    except EnvironmentError as e:
        rprint(f"[red]Erreur de configuration :[/red] {e}")
        sys.exit(1)

    # ── --stats ────────────────────────────────────────────────────────────
    if args.stats:
        print_stats(storage_summary())
        return

    # ── --list ─────────────────────────────────────────────────────────────
    if args.list:
        docs = list_curated(limit=20)
        print_list(docs)
        return

    # ── --cross-validate ───────────────────────────────────────────────────
    if args.cross_validate:
        docs = list_curated(limit=50)
        warnings = validate_cross(docs)
        if warnings:
            rprint("\n[yellow]Vérification croisée :[/yellow]")
            for w in warnings:
                rprint(f"  {w}")
        else:
            rprint("[green]✓ Aucune incohérence inter-documents détectée[/green]")
        return

    # ── Collecte des fichiers à traiter ────────────────────────────────────
    files: list[str] = list(args.files)

    if args.dir:
        dir_path = Path(args.dir)
        if not dir_path.is_dir():
            rprint(f"[red]Dossier introuvable : {args.dir}[/red]")
            sys.exit(1)
        supported_exts = {".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".webp"}
        files += [
            str(f) for f in sorted(dir_path.iterdir())
            if f.suffix.lower() in supported_exts
        ]

    if not files:
        parser.print_help()
        sys.exit(0)

    # ── Traitement ─────────────────────────────────────────────────────────
    if len(files) == 1:
        result  = process_document(files[0])
        results = [result]
        print_result(result)
    else:
        results = process_batch(files)
        for r in results:
            print_result(r)

    # ── Sortie JSON optionnelle ────────────────────────────────────────────
    if args.output:
        out = Path(args.output)
        out.write_text(
            json.dumps(results if len(results) > 1 else results[0],
                       ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        rprint(f"\n[green]Résultats sauvegardés → {out}[/green]")


if __name__ == "__main__":
    main()
