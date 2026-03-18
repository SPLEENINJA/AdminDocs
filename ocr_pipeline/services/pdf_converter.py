"""Installation recommandée (aucun outil système requis) :
  pip install pymupdf img2pdf
"""
from __future__ import annotations

import io
from pathlib import Path
from typing import List, Tuple

from PIL import Image

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".webp"}


# ── Lecture PDF ───────────────────────────────────────────────────────────────

def _pdf_via_pymupdf(pdf_path: str, dpi: int = 200) -> List[Image.Image]:
    """PyMuPDF — pur Python, pas de poppler requis."""
    import fitz  # pip install pymupdf
    doc    = fitz.open(pdf_path)
    matrix = fitz.Matrix(dpi / 72, dpi / 72)   # 72 dpi natif → scale
    pages  = []
    for page in doc:
        pix = page.get_pixmap(matrix=matrix, colorspace=fitz.csRGB)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        pages.append(img)
    doc.close()
    return pages


def _pdf_via_pdf2image(pdf_path: str, dpi: int = 200) -> List[Image.Image]:
    """pdf2image/poppler — fallback."""
    from pdf2image import convert_from_path
    return convert_from_path(pdf_path, dpi=dpi, fmt="jpeg", thread_count=2)


def _pdf_via_pil(pdf_path: str) -> List[Image.Image]:
    """PIL direct — dernier recours pour PDFs image simples."""
    img   = Image.open(pdf_path)
    pages = []
    try:
        while True:
            pages.append(img.copy().convert("RGB"))
            img.seek(img.tell() + 1)
    except EOFError:
        pass
    return pages if pages else None


def pdf_to_pil_images(pdf_path: str, dpi: int = 200) -> List[Image.Image]:
    """
    Convertit un PDF en liste d'images PIL.
    Essaie PyMuPDF → pdf2image → PIL, dans cet ordre.
    """
    # ── 1. PyMuPDF (recommandé, pur Python) ──────────────────────────────
    try:
        pages = _pdf_via_pymupdf(pdf_path, dpi=dpi)
        if pages:
            return pages
    except ImportError:
        pass   # PyMuPDF absent → fallback
    except Exception as e:
        if "password" in str(e).lower():
            raise RuntimeError(f"PDF protégé par mot de passe : {pdf_path}") from e
        # autre erreur PyMuPDF → essayer pdf2image

    # ── 2. pdf2image / poppler ────────────────────────────────────────────
    try:
        pages = _pdf_via_pdf2image(pdf_path, dpi=dpi)
        if pages:
            return pages
    except ImportError:
        pass
    except Exception as e:
        if any(k in str(e).lower() for k in ("poppler", "pdfinfo", "page count")):
            pass  # poppler absent → PIL fallback
        else:
            raise

    # ── 3. PIL direct (PDFs image simples) ───────────────────────────────
    try:
        pages = _pdf_via_pil(pdf_path)
        if pages:
            return pages
    except Exception:
        pass

    raise RuntimeError(
        f"Impossible de lire le PDF : {Path(pdf_path).name}\n"
        f"Installe PyMuPDF (recommandé, aucun outil système) :\n"
        f"  pip install pymupdf"
    )


# ── Lecture image ─────────────────────────────────────────────────────────────

def image_to_pil(image_path: str) -> List[Image.Image]:
    return [Image.open(image_path).convert("RGB")]


def load_document_as_images(
    file_path: str, dpi: int = 200
) -> Tuple[List[Image.Image], bool]:
    """
    Charge un document en liste de pages PIL.
    Returns: (pages, converted) — converted=True si PDF converti.
    """
    suffix = Path(file_path).suffix.lower()
    if suffix == ".pdf":
        return pdf_to_pil_images(file_path, dpi=dpi), True
    elif suffix in IMAGE_EXTENSIONS:
        return image_to_pil(file_path), False
    else:
        raise ValueError(f"Format non supporté : '{suffix}'")


def pil_to_bytes(image: Image.Image, fmt: str = "JPEG") -> bytes:
    buf = io.BytesIO()
    image.save(buf, format=fmt)
    return buf.getvalue()
