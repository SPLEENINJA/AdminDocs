FROM python:3.11-slim

# ── Poppler (pour pdf2image) ──────────────────────────────────────────────────
RUN apt-get update && apt-get install -y \
    poppler-utils \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ── Dépendances Python ────────────────────────────────────────────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Code source ───────────────────────────────────────────────────────────────
COPY . .

# ── Dossiers de stockage ──────────────────────────────────────────────────────
RUN mkdir -p storage/raw storage/clean storage/curated logs input_docs

# ── Variables d'environnement ─────────────────────────────────────────────────
ENV PYTHONUNBUFFERED=1
ENV GEMINI_MODEL=gemini-2.0-flash
ENV PDF_DPI=200

# ── Port API ──────────────────────────────────────────────────────────────────
EXPOSE 8000

CMD ["uvicorn", "api.app:app", "--host", "0.0.0.0", "--port", "8000"]
