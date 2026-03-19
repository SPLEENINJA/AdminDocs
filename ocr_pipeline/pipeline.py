"""
app_ui.py — Interface Streamlit complète pour tester le pipeline OCR

Onglets :
  1. 🔍 Analyser un document   → Upload + OCR + résultats détaillés
  2. 📦 Batch                  → Traitement multi-documents
  3. 🧪 Générer dataset        → Générateur Faker intégré
  4. 📋 Historique             → Documents déjà traités (zone Curated)
  5. 🔗 Cohérence inter-docs   → Cross-validation SIRET / TVA / dates

Lancement :
    streamlit run app_ui.py
"""
from __future__ import annotations

import io
import json
import sys
import tempfile
from pathlib import Path
from datetime import datetime

import streamlit as st
from PIL import Image

# ── Ajout du répertoire racine au path ────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))

# ── Config page ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="OCR Service — Hackathon 2026",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS custom ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .main { background-color: #f8f9fc; }
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] {
        padding: 8px 20px;
        border-radius: 8px 8px 0 0;
        font-weight: 600;
    }
    .doc-card {
        background: white;
        border-radius: 12px;
        padding: 20px;
        border-left: 5px solid #3B6FE4;
        margin-bottom: 12px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.07);
    }
    .doc-card.ok   { border-left-color: #2ecc71; }
    .doc-card.warn { border-left-color: #f39c12; }
    .doc-card.err  { border-left-color: #e74c3c; }
    .badge {
        display: inline-block;
        padding: 3px 12px;
        border-radius: 20px;
        font-size: 0.78em;
        font-weight: 700;
        margin-right: 6px;
    }
    .badge-blue   { background:#e8f0fe; color:#1a56d6; }
    .badge-green  { background:#e6f9ef; color:#1a7f4b; }
    .badge-orange { background:#fff3e0; color:#b45309; }
    .badge-red    { background:#fde8e8; color:#c0392b; }
    .champ-table  { width:100%; border-collapse:collapse; font-size:0.9em; }
    .champ-table th { background:#f0f4ff; padding:6px 10px; text-align:left;
                      border-bottom: 2px solid #dee2f0; }
    .champ-table td { padding:5px 10px; border-bottom:1px solid #eef0f6; }
    .champ-table tr:hover td { background:#f8f9ff; }
    .metric-box {
        background: white;
        border-radius: 10px;
        padding: 16px 20px;
        text-align: center;
        box-shadow: 0 1px 4px rgba(0,0,0,0.08);
    }
    .metric-val { font-size: 2em; font-weight: 800; color: #1a56d6; }
    .metric-lbl { font-size: 0.82em; color: #666; margin-top: 2px; }
    .section-title {
        font-size: 1.05em; font-weight: 700;
        color: #1a56d6; margin: 14px 0 6px 0;
        border-bottom: 2px solid #e8f0fe; padding-bottom: 4px;
    }
    .anomaly-item {
        background: #fff3cd; border-left: 4px solid #f39c12;
        border-radius: 4px; padding: 6px 12px; margin: 4px 0;
        font-size: 0.88em;
    }
    .error-item {
        background: #fde8e8; border-left: 4px solid #e74c3c;
        border-radius: 4px; padding: 6px 12px; margin: 4px 0;
        font-size: 0.88em;
    }
    .ok-item {
        background: #e6f9ef; border-left: 4px solid #2ecc71;
        border-radius: 4px; padding: 6px 12px; margin: 4px 0;
        font-size: 0.88em;
    }
</style>
""", unsafe_allow_html=True)


# ── Chargement paresseux des dépendances lourdes ─────────────────────────────
@st.cache_resource
def load_pipeline():
    """Charge le pipeline une seule fois (Gemini client, etc.)."""
    try:
        from config import validate_config
        validate_config()
        from pipeline import process_document, process_batch
        from services.storage import list_curated, storage_summary
        from services.chroma import query_documents, count_documents, store_document
        from services.validator import validate_cross
        from dataset_generator.generate import generate_dataset, SCENARIOS, NOISE_LEVELS, OUTPUT_FORMATS
        return {
            "process_document": process_document,
            "process_batch":    process_batch,
            "list_curated":     list_curated,
            "storage_summary":  storage_summary,
            "validate_cross":   validate_cross,
            "generate_dataset": generate_dataset,
            "SCENARIOS":        SCENARIOS,
            "NOISE_LEVELS":     NOISE_LEVELS,
            "OUTPUT_FORMATS":   OUTPUT_FORMATS,
            "query_documents":  query_documents,
            "count_documents":  count_documents,
            "ok": True,
        }
    except EnvironmentError as e:
        return {"ok": False, "error": str(e)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ── Helpers d'affichage ───────────────────────────────────────────────────────

TYPE_COLORS = {
    "facture":              "badge-blue",
    "facture_falsifiee":    "badge-red",
    "devis":                "badge-blue",
    "attestation_urssaf":   "badge-green",
    "attestation_urssaf_expiree": "badge-red",
    "rib":                  "badge-blue",
    "extrait_kbis":         "badge-blue",
    "inconnu":              "badge-orange",
}

TYPE_LABELS = {
    "facture":            "🧾 Facture",
    "devis":              "📝 Devis",
    "attestation_urssaf": "🏛 Attestation URSSAF",
    "extrait_kbis":       "📋 Extrait Kbis",
    "rib":                "🏦 RIB",
    "contrat":            "📜 Contrat",
    "inconnu":            "❓ Inconnu",
}

CHAMP_LABELS = {
    "siret":           "SIRET",
    "siren":           "SIREN",
    "raison_sociale":  "Raison sociale",
    "date_emission":   "Date d'émission",
    "date_expiration": "Date d'expiration",
    "montant_ht":      "Montant HT",
    "montant_ttc":     "Montant TTC",
    "tva_taux":        "Taux TVA",
    "numero_document": "N° Document",
    "iban":            "IBAN",
    "bic":             "BIC/SWIFT",
    "emetteur":        "Émetteur",
    "destinataire":    "Destinataire",
}


def badge(text: str, cls: str = "badge-blue") -> str:
    return f'<span class="badge {cls}">{text}</span>'


def confiance_color(c: float) -> str:
    if c >= 0.85: return "#2ecc71"
    if c >= 0.60: return "#f39c12"
    return "#e74c3c"


def render_result_card(result: dict):
    """Affiche un document traité dans un beau bloc HTML + widgets Streamlit."""
    doc_type  = result.get("type_document", "inconnu")
    confiance = result.get("confiance", 0.0)
    champs    = result.get("champs", {})
    anomalies = result.get("anomalies", [])
    errors    = result.get("validation_errors", [])
    qualite   = result.get("qualite_scan", "?")
    fichier   = result.get("fichier_source", "?")
    doc_id    = result.get("document_id", "?")

    status_cls = "ok" if not errors and not anomalies else ("err" if errors else "warn")
    type_label = TYPE_LABELS.get(doc_type, f"📄 {doc_type}")
    type_badge = TYPE_COLORS.get(doc_type, "badge-blue")

    # ── Header card ──────────────────────────────────────────────────────────
    st.markdown(f"""
    <div class="doc-card {status_cls}">
        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;">
            <div>
                <span style="font-size:1.15em; font-weight:700;">{type_label}</span>
                <span style="color:#888; font-size:0.85em; margin-left:10px;">📁 {fichier}</span>
            </div>
            <div>
                {badge(f'Confiance : {confiance:.0%}', 'badge-green' if confiance >= 0.8 else 'badge-orange')}
                {badge(f'Qualité : {qualite}', 'badge-blue')}
                {badge(f'{len(errors)} erreur(s)', 'badge-red') if errors else badge('✓ Valide', 'badge-green')}
                {badge(f'{len(anomalies)} anomalie(s)', 'badge-orange') if anomalies else ''}
            </div>
        </div>
        <div style="font-size:0.78em; color:#aaa; margin-top:6px;">ID : {doc_id}</div>
    </div>
    """, unsafe_allow_html=True)

    # ── Colonnes : champs extraits + alertes ──────────────────────────────────
    col_champs, col_alerts = st.columns([3, 2])

    with col_champs:
        st.markdown('<div class="section-title">📊 Champs extraits</div>', unsafe_allow_html=True)
        rows_html = ""
        for k, lbl in CHAMP_LABELS.items():
            val = champs.get(k)
            if val is not None:
                # Formatage spécial
                if k in ("montant_ht", "montant_ttc") and isinstance(val, (int, float)):
                    val_str = f"{val:,.2f} €".replace(",", " ")
                else:
                    val_str = str(val)
                rows_html += f"<tr><td style='color:#555;'>{lbl}</td><td><b>{val_str}</b></td></tr>"
        if rows_html:
            st.markdown(
                f'<table class="champ-table"><thead><tr><th>Champ</th><th>Valeur</th></tr></thead>'
                f'<tbody>{rows_html}</tbody></table>',
                unsafe_allow_html=True,
            )
        else:
            st.info("Aucun champ extrait.")

    with col_alerts:
        st.markdown('<div class="section-title">⚠️ Alertes & Validation</div>', unsafe_allow_html=True)

        if not errors and not anomalies:
            st.markdown('<div class="ok-item">✅ Document valide — aucune anomalie détectée</div>',
                        unsafe_allow_html=True)
        else:
            for e in errors:
                st.markdown(f'<div class="error-item">❌ {e}</div>', unsafe_allow_html=True)
            for a in anomalies:
                st.markdown(f'<div class="anomaly-item">⚠️ {a}</div>', unsafe_allow_html=True)

        # Barre de confiance
        st.markdown('<div class="section-title">📈 Confiance</div>', unsafe_allow_html=True)
        st.progress(confiance, text=f"{confiance:.0%}")

    # ── JSON brut (expander) ─────────────────────────────────────────────────
    with st.expander("🔧 JSON complet (zone Curated)"):
        st.json(result)


def save_upload_to_temp(uploaded_file) -> str:
    """Sauvegarde un fichier Streamlit uploadé dans un fichier temporaire."""
    suffix = Path(uploaded_file.name).suffix.lower()
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(uploaded_file.getbuffer())
        return tmp.name


# ── Sidebar ───────────────────────────────────────────────────────────────────
def render_sidebar(pl):
    st.sidebar.image(
        "https://img.icons8.com/fluency/96/document.png",
        width=60,
    )
    st.sidebar.title("OCR Service")
    st.sidebar.caption("Hackathon 2026 — Powered by Gemini 2.0 Flash")
    st.sidebar.divider()

    if pl["ok"]:
        stats = pl["storage_summary"]()
        st.sidebar.markdown("### 📦 Stockage local")
        c1, c2, c3 = st.sidebar.columns(3)
        c1.metric("Raw",     stats["raw"])
        c2.metric("Clean",   stats["clean"])
        c3.metric("Curated", stats["curated"])
        st.sidebar.divider()
        chroma_n = pl.get("count_documents", lambda: 0)()
        st.sidebar.metric("💬 Docs indexés (ChromaDB)", chroma_n)
        st.sidebar.success("✅ Gemini API connectée")
    else:
        st.sidebar.error(f"⚠️ Erreur config :\n{pl.get('error','')}")
        st.sidebar.info("Configure `.env` avec ta clé `GEMINI_API_KEY`")

    st.sidebar.markdown("---")
    st.sidebar.caption("**Types supportés**")
    for t, l in TYPE_LABELS.items():
        st.sidebar.caption(f"• {l}")


# ── Onglet 1 : Analyser un document ──────────────────────────────────────────
def tab_analyser(pl):
    st.header("🔍 Analyser un document")
    st.caption("Upload un PDF ou une image — le pipeline OCR + classification s'exécute en temps réel.")

    uploaded = st.file_uploader(
        "Dépose ton document ici",
        type=["pdf", "png", "jpg", "jpeg", "tiff", "bmp", "webp"],
        help="Formats : PDF, PNG, JPG, TIFF, BMP, WEBP",
    )

    if not uploaded:
        st.info("👆 Dépose un fichier pour commencer.")
        # Exemple visuel
        st.markdown("---")
        st.markdown("**Ce que fait le pipeline :**")
        steps = [
            ("1️⃣", "Sauvegarde en zone **RAW**", "Copie du fichier original"),
            ("2️⃣", "Conversion en images",       "PDF → pages PIL"),
            ("3️⃣", "OCR via **Gemini Vision**",  "Extraction JSON structuré page par page"),
            ("4️⃣", "Fusion multi-pages",          "Merge des résultats"),
            ("5️⃣", "Validation",                  "SIRET, IBAN, montants, dates expirées"),
            ("6️⃣", "Sauvegarde **CLEAN** + **CURATED**", "Texte brut + JSON final"),
        ]
        for icon, titre, detail in steps:
            st.markdown(f"{icon} **{titre}** — *{detail}*")
        return

    # Aperçu
    col_preview, col_info = st.columns([1, 2])
    with col_preview:
        st.markdown("**Aperçu**")
        if uploaded.type == "application/pdf":
            st.info(f"📄 PDF : `{uploaded.name}` ({uploaded.size / 1024:.1f} Ko)")
        else:
            img = Image.open(uploaded)
            st.image(img, caption=uploaded.name)

    with col_info:
        st.markdown("**Informations fichier**")
        st.markdown(f"- **Nom** : `{uploaded.name}`")
        st.markdown(f"- **Taille** : {uploaded.size / 1024:.1f} Ko")
        st.markdown(f"- **Type MIME** : `{uploaded.type}`")
        st.markdown("")
        launch = st.button("▶️ Lancer l'analyse OCR", type="primary", width="stretch")

    if launch:
        tmp_path = save_upload_to_temp(uploaded)
        try:
            with st.spinner("⏳ Analyse en cours via Gemini Vision..."):
                progress = st.progress(0, text="Sauvegarde RAW...")
                progress.progress(15, text="Conversion en images...")
                result = pl["process_document"](tmp_path, original_filename=uploaded.name)
                progress.progress(100, text="✅ Terminé !")

            st.success(f"✅ Document analysé : **{TYPE_LABELS.get(result['type_document'], result['type_document'])}** "
                       f"(confiance {result['confiance']:.0%})")
            st.divider()
            render_result_card(result)

            # Téléchargement JSON
            st.download_button(
                label="⬇️ Télécharger le JSON (zone Curated)",
                data=json.dumps(result, ensure_ascii=False, indent=2, default=str),
                file_name=f"{result['document_id']}.json",
                mime="application/json",
            )

        except Exception as e:
            err = str(e)
            if "pymupdf" in err.lower() or "impossible de lire" in err.lower() or "page count" in err.lower():
                st.error("❌ **PDF illisible**")
                st.warning("Lance `pip install pymupdf img2pdf` puis redémarre Streamlit.")
            else:
                st.error(f"❌ Erreur pipeline : {e}")
        finally:
            Path(tmp_path).unlink(missing_ok=True)


# ── Onglet 2 : Batch ─────────────────────────────────────────────────────────
def tab_batch(pl):
    st.header("📦 Traitement en batch")
    st.caption("Traite plusieurs documents en une seule fois.")

    uploaded_files = st.file_uploader(
        "Dépose plusieurs fichiers",
        type=["pdf", "png", "jpg", "jpeg", "tiff", "bmp", "webp"],
        accept_multiple_files=True,
    )

    if not uploaded_files:
        st.info("👆 Dépose plusieurs fichiers pour activer le batch.")
        return

    st.markdown(f"**{len(uploaded_files)} fichier(s) sélectionné(s) :**")
    for f in uploaded_files:
        st.markdown(f"  • `{f.name}` ({f.size/1024:.1f} Ko)")

    if st.button("▶️ Lancer le batch", type="primary"):
        tmp_paths = []
        try:
            for f in uploaded_files:
                tmp_paths.append((save_upload_to_temp(f), f.name))

            total   = len(tmp_paths)
            results = []
            progress_bar = st.progress(0, text="Démarrage...")
            status_box   = st.empty()

            for i, (tmp_path, orig_name) in enumerate(tmp_paths):
                status_box.info(f"⏳ Traitement {i+1}/{total} : `{orig_name}`...")
                try:
                    r = pl["process_document"](tmp_path, original_filename=orig_name)
                    results.append(r)
                except Exception as e:
                    results.append({"fichier_source": orig_name, "type_document": "inconnu", "erreur": str(e)})

            # Show pymupdf tip if any PDF failed
            pdf_errors = [r for r in results if "erreur" in r and ".pdf" in r.get("fichier_source","").lower()]
            if pdf_errors:
                st.warning(
                    "⚠️ **Certains PDFs n'ont pas pu être lus.**\n\n"
                    "Solution (aucun outil système requis) :\n"
                    "```\npip install pymupdf img2pdf\n```\n"
                    "Puis redémarre Streamlit."
                )
                progress_bar.progress((i + 1) / total, text=f"{i+1}/{total} traités")

            status_box.success(f"✅ Batch terminé : {len(results)} documents traités.")

            # Résumé
            ok     = sum(1 for r in results if "erreur" not in r)
            errors = total - ok
            c1, c2, c3 = st.columns(3)
            c1.metric("Total",    total)
            c2.metric("✅ OK",    ok)
            c3.metric("❌ Erreurs", errors)

            st.divider()

            # Résultats individuels
            for r in results:
                if "erreur" in r:
                    st.error(f"❌ `{r['fichier_source']}` : {r['erreur']}")
                else:
                    render_result_card(r)
                st.divider()

            # Téléchargement global
            st.download_button(
                label="⬇️ Télécharger tous les résultats (JSON)",
                data=json.dumps(results, ensure_ascii=False, indent=2, default=str),
                file_name=f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json",
            )

        finally:
            for tmp_path, _ in tmp_paths:
                Path(tmp_path).unlink(missing_ok=True)


# ── Onglet 3 : Générer dataset ───────────────────────────────────────────────
def tab_generate(pl):
    st.header("🧪 Générer un dataset de test")
    st.caption("Crée des documents administratifs réalistes (A4, multi-sections) avec simulation de bruit.")

    SCENARIOS   = pl["SCENARIOS"]
    NOISE_LEVELS = pl["NOISE_LEVELS"]

    SCENARIOS    = pl["SCENARIOS"]
    NOISE_LEVELS = pl["NOISE_LEVELS"]
    OUTPUT_FORMATS = pl.get("OUTPUT_FORMATS", ["jpg", "pdf", "both", "random"])

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        scenario = st.selectbox(
            "Type de document",
            ["all"] + SCENARIOS,
            format_func=lambda x: "🎲 Tous (aléatoire)" if x == "all" else TYPE_LABELS.get(x, x),
        )
    with col2:
        noise = st.selectbox(
            "Niveau de dégradation",
            ["random"] + NOISE_LEVELS,
            format_func=lambda x: {
                "random": "🎲 Aléatoire",
                "none":   "✨ Parfait (aucun bruit)",
                "light":  "🌫 Léger (scan propre)",
                "medium": "📷 Moyen (scan + rotation)",
                "heavy":  "🌀 Fort (scan dégradé)",
                "smartphone": "📱 Smartphone (photo floue)",
            }.get(x, x),
        )
    with col3:
        fmt = st.selectbox(
            "Format de sortie",
            OUTPUT_FORMATS,
            format_func=lambda x: {
                "jpg":    "🖼 JPEG uniquement",
                "pdf":    "📄 PDF uniquement",
                "both":   "📦 JPG + PDF (les deux)",
                "random": "🎲 Aléatoire",
            }.get(x, x),
        )
    with col4:
        count = st.slider("Nombre de documents", min_value=1, max_value=30, value=5)

    output_dir = st.text_input("Dossier de sortie", value="input_docs")

    # Prévisualisation
    st.markdown("**Scénarios inclus dans ce batch :**")
    if scenario == "all":
        cols = st.columns(4)
        for i, s in enumerate(SCENARIOS):
            cols[i % 4].markdown(f"• {TYPE_LABELS.get(s, s)}")
    else:
        st.markdown(f"• {TYPE_LABELS.get(scenario, scenario)}")

    st.divider()

    if st.button(f"🚀 Générer {count} document(s)", type="primary"):
        with st.spinner(f"Génération de {count} documents..."):
            progress_bar = st.progress(0)
            log_box      = st.empty()
            generated    = []

            from dataset_generator.generate import generate_dataset as _gen_ds
            import random

            out_path = Path(output_dir)
            out_path.mkdir(parents=True, exist_ok=True)

            # Génération via la fonction principale (supporte jpg + pdf)
            log_box.info(f"⏳ Génération de {count} documents (format={fmt})...")
            generated = _gen_ds(output_dir, count, scenario, noise, fmt)
            progress_bar.progress(1.0)
            log_box.success(f"✅ {len(generated)} fichier(s) générés dans `{output_dir}/`")

        # Galerie de préview (JPG seulement pour l'aperçu, les PDF s'affichent en icône)
        st.markdown(f"### 📸 Aperçu ({min(count, 6)} premiers fichiers)")
        all_files = sorted(out_path.glob("*.jpg"))[:6] + sorted(out_path.glob("*.pdf"))[:3]
        preview_files = sorted(set(all_files), key=lambda p: p.name)[:6]
        cols = st.columns(3)
        for i, fp in enumerate(preview_files):
            with cols[i % 3]:
                if fp.suffix.lower() == ".jpg":
                    img = Image.open(fp)
                    img.thumbnail((400, 600))
                    st.image(img, caption=fp.name)
                else:
                    size_kb = fp.stat().st_size // 1024
                    st.markdown(f"📄 **{fp.name}** — {size_kb} Ko (PDF)")
                    st.info("Aperçu PDF non disponible dans l'UI.")

        # Résumé stats
        st.markdown("### 📊 Distribution des scénarios")
        from collections import Counter
        counts = Counter(r["scenario"] for r in generated)
        for sc_name, cnt in counts.most_common():
            st.markdown(f"- **{TYPE_LABELS.get(sc_name, sc_name)}** : {cnt} document(s)")

        st.info(f"💡 Tu peux maintenant aller dans l'onglet **Analyser** ou **Batch** pour tester ces fichiers.")


# ── Onglet 4 : Historique ─────────────────────────────────────────────────────
def tab_historique(pl):
    st.header("📋 Historique des documents traités")
    st.caption("Documents disponibles dans la zone Curated (stockage local).")

    limit = st.slider("Nombre de documents à afficher", 5, 50, 20)
    docs  = pl["list_curated"](limit=limit)

    if not docs:
        st.info("Aucun document traité pour l'instant. Lance une analyse dans l'onglet **Analyser**.")
        return

    # Métriques globales
    total    = len(docs)
    ok       = sum(1 for d in docs if not d.get("validation_errors"))
    anomalies_count = sum(len(d.get("anomalies", [])) for d in docs)
    types    = {}
    for d in docs:
        t = d.get("type_document", "inconnu")
        types[t] = types.get(t, 0) + 1

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total traités",  total)
    c2.metric("✅ Valides",     ok)
    c3.metric("❌ Avec erreurs", total - ok)
    c4.metric("⚠️ Anomalies",   anomalies_count)

    st.divider()

    # Filtre par type
    type_filter = st.multiselect(
        "Filtrer par type",
        options=list(set(d.get("type_document","?") for d in docs)),
        default=[],
        format_func=lambda x: TYPE_LABELS.get(x, x),
    )

    filtered = docs if not type_filter else [d for d in docs if d.get("type_document") in type_filter]

    # Tableau récap
    st.markdown(f"**{len(filtered)} document(s) affiché(s)**")

    table_rows = []
    for d in filtered:
        table_rows.append({
            "Fichier":       d.get("fichier_source", "?"),
            "Type":          TYPE_LABELS.get(d.get("type_document","?"), d.get("type_document","?")),
            "Confiance":     f"{d.get('confiance', 0):.0%}",
            "Qualité":       d.get("qualite_scan", "?"),
            "Anomalies":     len(d.get("anomalies", [])),
            "Erreurs valid.":len(d.get("validation_errors", [])),
        })

    import pandas as pd
    st.dataframe(
        pd.DataFrame(table_rows),
        width="stretch",
        hide_index=True,
    )

    # Détail par document
    st.divider()
    st.markdown("### Détail par document")
    for doc in filtered[:10]:  # Limite l'affichage
        with st.expander(f"📄 {doc.get('fichier_source','?')} — {TYPE_LABELS.get(doc.get('type_document','?'), '?')}"):
            render_result_card(doc)


# ── Onglet 5 : Cohérence inter-documents ─────────────────────────────────────
def tab_cross_validate(pl):
    st.header("🔗 Vérification croisée inter-documents")
    st.caption("Détecte les incohérences entre documents d'un même dossier (SIRET différents, TVA incohérente, attestations expirées…)")

    docs = pl["list_curated"](limit=50)

    if len(docs) < 2:
        st.warning("Il faut au moins 2 documents traités pour effectuer une vérification croisée.")
        return

    # Sélection des documents à comparer
    st.markdown(f"**{len(docs)} document(s) disponibles dans le Curated store**")
    options = {
        f"{d.get('fichier_source','?')} — {TYPE_LABELS.get(d.get('type_document','?'),'?')} ({d.get('document_id','?')[:12]}...)": d
        for d in docs
    }
    selected_labels = st.multiselect(
        "Sélectionne les documents à comparer (ou laisse vide pour tout analyser)",
        options=list(options.keys()),
    )
    selected_docs = [options[l] for l in selected_labels] if selected_labels else docs

    st.markdown(f"**{len(selected_docs)} document(s) à analyser**")

    if st.button("🔍 Lancer la vérification croisée", type="primary"):
        warnings = pl["validate_cross"](selected_docs)

        st.divider()

        if not warnings:
            st.success("✅ Aucune incohérence détectée entre les documents sélectionnés.")
        else:
            st.error(f"⚠️ {len(warnings)} incohérence(s) détectée(s) !")
            for w in warnings:
                st.markdown(f'<div class="error-item">❌ {w}</div>', unsafe_allow_html=True)

        st.divider()

        # Tableau des SIRET trouvés
        st.markdown("### SIRET par document")
        siret_data = []
        for d in selected_docs:
            siret_val = (d.get("champs") or {}).get("siret") or d.get("siret_emetteur", "—")
            siret_data.append({
                "Fichier":  d.get("fichier_source", "?"),
                "Type":     TYPE_LABELS.get(d.get("type_document","?"), "?"),
                "SIRET":    siret_val or "—",
                "Valide":   "✅" if siret_val and len(str(siret_val).replace(" ","")) == 14 else "❌",
            })
        import pandas as pd
        st.dataframe(pd.DataFrame(siret_data), width="stretch", hide_index=True)




# ── Onglet 6 : Chat avec les documents ───────────────────────────────────────
def tab_chat(pl):
    st.header("💬 Chat avec vos documents")
    st.caption(
        "Posez une question en langage naturel — le système recherche dans tous "
        "vos documents analysés et génère une réponse basée sur leur contenu."
    )

    n_docs = pl.get("count_documents", lambda: 0)()
    if n_docs == 0:
        st.info(
            "Aucun document indexé pour l'instant. "
            "Analysez d'abord des documents dans l'onglet **🔍 Analyser** ou **📦 Batch**."
        )
        return

    st.markdown(f"**{n_docs} document(s) disponibles** pour la recherche")

    # ── Historique de conversation ────────────────────────────────────────────
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    # Affichage des messages précédents
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # ── Exemples de questions ─────────────────────────────────────────────────
    if not st.session_state.chat_history:
        st.markdown("**Questions exemples :**")
        exemples = [
            "Quelles factures ont un montant supérieur à 5000 € ?",
            "Y a-t-il des attestations URSSAF expirées ?",
            "Quel est le SIRET de l'entreprise ACME ?",
            "Liste tous les RIB et leurs IBAN",
        ]
        cols = st.columns(2)
        for i, ex in enumerate(exemples):
            if cols[i % 2].button(ex, key=f"ex_{i}", use_container_width=True):
                st.session_state.chat_prefill = ex
                st.rerun()

    # ── Input utilisateur ─────────────────────────────────────────────────────
    prefill = st.session_state.pop("chat_prefill", "")
    question = st.chat_input("Posez votre question sur vos documents…")
    if prefill and not question:
        question = prefill

    if not question:
        return

    # Affiche la question
    with st.chat_message("user"):
        st.markdown(question)
    st.session_state.chat_history.append({"role": "user", "content": question})

    # ── Recherche ChromaDB ────────────────────────────────────────────────────
    with st.chat_message("assistant"):
        with st.spinner("Recherche dans vos documents…"):
            hits = pl["query_documents"](question, n_results=5)

        if not hits:
            answer = "Je n'ai trouvé aucun document correspondant à votre question."
            st.markdown(answer)
            st.session_state.chat_history.append({"role": "assistant", "content": answer})
            return

        # Contexte injecté dans Gemini
        context_parts = []
        for i, hit in enumerate(hits, 1):
            meta = hit.get("metadata", {})
            context_parts.append(
                f"--- Document {i} ---\n"
                f"Fichier : {meta.get('fichier_source', '?')}\n"
                f"Type : {meta.get('type_document', '?')}\n"
                f"Contenu : {hit['content'][:800]}"
            )
        context = "\n\n".join(context_parts)

        # ── Appel Gemini pour la réponse ──────────────────────────────────────
        try:
            import sys, os
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            from config import GEMINI_API_KEY, GEMINI_MODEL

            prompt = f"""Tu es un assistant expert en documents administratifs français.
Réponds à la question de l'utilisateur en te basant UNIQUEMENT sur les documents fournis.
Sois précis, cite les noms de fichiers et les valeurs exactes quand tu y réponds.
Si la réponse n'est pas dans les documents, dis-le clairement.

DOCUMENTS DISPONIBLES :
{context}

QUESTION : {question}

RÉPONSE (en français) :"""

            try:
                from google import genai
                from google.genai import types as genai_types
                client = genai.Client(api_key=GEMINI_API_KEY)
                response = client.models.generate_content(
                    model=GEMINI_MODEL,
                    contents=[genai_types.Part.from_text(text=prompt)],
                    config=genai_types.GenerateContentConfig(temperature=0.3, max_output_tokens=1024),
                )
                answer = response.text
            except ImportError:
                import google.generativeai as genai_legacy
                genai_legacy.configure(api_key=GEMINI_API_KEY)
                m = genai_legacy.GenerativeModel(GEMINI_MODEL)
                answer = m.generate_content(prompt).text

        except Exception as e:
            answer = f"Erreur lors de la génération de la réponse : {e}"

        st.markdown(answer)
        st.session_state.chat_history.append({"role": "assistant", "content": answer})

        # Sources utilisées
        with st.expander(f"📂 Sources consultées ({len(hits)} document(s))"):
            for hit in hits:
                meta = hit.get("metadata", {})
                st.markdown(
                    f"**{meta.get('fichier_source', '?')}** — "
                    f"{TYPE_LABELS.get(meta.get('type_document','?'), meta.get('type_document','?'))} — "
                    f"similarité : {hit['similarity']:.0%}"
                )

    # Bouton reset
    if st.session_state.chat_history:
        if st.button("🗑 Effacer la conversation", key="clear_chat"):
            st.session_state.chat_history = []
            st.rerun()

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    # Chargement
    pl = load_pipeline()

    # Sidebar
    render_sidebar(pl)

    # Titre principal
    st.title("📄 OCR Service — Hackathon 2026")
    st.caption("Pipeline complet d'extraction et de classification de documents administratifs via Gemini Vision")

    if not pl["ok"]:
        st.error(f"⚠️ Impossible de démarrer le pipeline : **{pl.get('error', '')}**")
        st.info("1. Copie `.env.example` en `.env`\n2. Renseigne ta clé `GEMINI_API_KEY`\n3. Recharge la page")
        return

    # Onglets
    tabs = st.tabs([
        "🔍 Analyser un document",
        "📦 Batch",
        "🧪 Générer dataset",
        "📋 Historique",
        "🔗 Cohérence inter-docs",
        "💬 Chat avec vos documents",
    ])

    with tabs[0]: tab_analyser(pl)
    with tabs[1]: tab_batch(pl)
    with tabs[2]: tab_generate(pl)
    with tabs[3]: tab_historique(pl)
    with tabs[4]: tab_cross_validate(pl)
    with tabs[5]: tab_chat(pl)


if __name__ == "__main__":
    main()
