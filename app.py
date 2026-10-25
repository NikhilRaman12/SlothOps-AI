"""
app.py — SlothOps AI · Hacktoberfest 2026
A local-first file-organisation assistant.
"""

from __future__ import annotations

import pathlib
import time
from typing import Optional

import streamlit as st

# ── Page config (must be first Streamlit call) ────────────────────────────────
st.set_page_config(
    page_title="SlothOps AI",
    page_icon="🦥",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Internal modules ──────────────────────────────────────────────────────────
from slothops.ingest import ingest_streamlit_file, strip_markdown, IngestedFile
from slothops.ai_engine import (
    ollama_analyze,
    fallback_analyze,
    find_duplicates,
    content_hash,
    AnalysisResult,
    CATEGORIES,
)
from slothops.file_ops import OperationLog, copy_organised, rename_in_place
from slothops import history as hist_db

# ── Custom CSS ────────────────────────────────────────────────────────────────
CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

* { font-family: 'Inter', sans-serif !important; }

/* ── Background gradient ── */
.stApp {
    background: linear-gradient(135deg, #0D1117 0%, #0F1923 50%, #071520 100%);
    min-height: 100vh;
}

/* ── Sidebar ── */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0D1A2B 0%, #0A1520 100%);
    border-right: 1px solid #1E3A5F;
}

/* ── Cards ── */
.sloth-card {
    background: rgba(22, 27, 34, 0.85);
    border: 1px solid #1E3A5F;
    border-radius: 12px;
    padding: 1.25rem 1.5rem;
    margin-bottom: 1rem;
    backdrop-filter: blur(8px);
    transition: border-color 0.2s;
}
.sloth-card:hover { border-color: #00D4FF; }

/* ── Metric chips ── */
.metric-chip {
    display: inline-block;
    background: rgba(0, 212, 255, 0.12);
    border: 1px solid rgba(0, 212, 255, 0.3);
    border-radius: 20px;
    padding: 0.2rem 0.75rem;
    font-size: 0.78rem;
    color: #00D4FF;
    margin: 0.2rem;
}

/* ── Category badge ── */
.cat-badge {
    background: linear-gradient(90deg, #00D4FF22, #0066FF22);
    border: 1px solid #00D4FF55;
    border-radius: 8px;
    padding: 0.3rem 1rem;
    color: #00D4FF;
    font-weight: 600;
    font-size: 0.9rem;
}

/* ── Privacy indicator ── */
.privacy-pill {
    background: rgba(0, 200, 100, 0.15);
    border: 1px solid rgba(0, 200, 100, 0.4);
    border-radius: 20px;
    padding: 0.25rem 0.85rem;
    color: #00C864;
    font-size: 0.78rem;
    font-weight: 600;
}

/* ── Action item list ── */
.action-item {
    background: rgba(255, 165, 0, 0.08);
    border-left: 3px solid #FFA500;
    border-radius: 0 8px 8px 0;
    padding: 0.4rem 0.75rem;
    margin: 0.3rem 0;
    color: #E6EDF3;
    font-size: 0.88rem;
}

/* ── Duplicate warning ── */
.dup-warning {
    background: rgba(255, 80, 80, 0.1);
    border: 1px solid rgba(255, 80, 80, 0.4);
    border-radius: 10px;
    padding: 0.75rem 1rem;
    color: #FF6B6B;
}

/* ── Hero header ── */
.hero-title {
    font-size: 2.6rem;
    font-weight: 700;
    background: linear-gradient(90deg, #00D4FF, #0066FF);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    margin: 0;
    line-height: 1.2;
}
.hero-subtitle {
    color: #8B949E;
    font-size: 1.05rem;
    margin-top: 0.4rem;
}

/* ── Status indicators ── */
.status-online { color: #00C864; font-weight: 600; }
.status-offline { color: #FF6B6B; font-weight: 600; }
.status-fallback { color: #FFA500; font-weight: 600; }

/* ── Streamlit overrides ── */
.stButton > button {
    border-radius: 8px;
    font-weight: 600;
    transition: all 0.2s;
}
.stButton > button:hover { transform: translateY(-1px); }

[data-testid="stMetricValue"] { color: #00D4FF; }

div[data-testid="stExpander"] {
    border: 1px solid #1E3A5F;
    border-radius: 10px;
}

.stAlert { border-radius: 10px; }

/* ── Progress bar colour ── */
.stProgress > div > div { background: linear-gradient(90deg, #00D4FF, #0066FF); }
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


# ── Session state init ────────────────────────────────────────────────────────
def _init_state() -> None:
    defaults = {
        "ingested_files": [],        # list[IngestedFile]
        "analyses": {},              # filename → AnalysisResult
        "op_log": OperationLog(),
        "output_dir": None,          # pathlib.Path | None
        "history_enabled": True,
        "model": "gemma:2b",
        "use_ollama": True,
        "corpus": {},                # filename → text (for dup detection)
        "session_ids": {},           # filename → history row id
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


_init_state()


# ── Ollama connectivity check ─────────────────────────────────────────────────
@st.cache_data(ttl=30, show_spinner=False)
def check_ollama() -> tuple[bool, list[str]]:
    """Returns (available, model_list)."""
    try:
        import ollama  # type: ignore
        models_resp = ollama.list()
        names = [m.get("name", m.get("model", "")) for m in models_resp.get("models", [])]
        return True, [n for n in names if n]
    except Exception:
        return False, []


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(
        """
        <div style='text-align:center; padding: 1rem 0 0.5rem;'>
          <span style='font-size:3rem;'>🦥</span>
          <h2 style='color:#00D4FF; margin:0.2rem 0 0;'>SlothOps AI</h2>
          <p style='color:#8B949E; font-size:0.82rem; margin:0;'>Hacktoberfest 2026 · Week 3</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.divider()

    # Privacy indicator
    st.markdown(
        "<div class='privacy-pill'>🔒 100% Local · No data leaves your machine</div>",
        unsafe_allow_html=True,
    )
    st.markdown("<br>", unsafe_allow_html=True)

    # Ollama status
    ollama_ok, available_models = check_ollama()
    if ollama_ok:
        st.markdown("<span class='status-online'>● Ollama Online</span>", unsafe_allow_html=True)
        model_options = available_models if available_models else ["gemma:2b"]
        # Prefer gemma models; put them first
        gemma_models = [m for m in model_options if "gemma" in m.lower()]
        other_models = [m for m in model_options if "gemma" not in m.lower()]
        ordered = gemma_models + other_models
        st.session_state.model = st.selectbox(
            "🤖 Model",
            ordered,
            index=0,
            help="Select the Ollama model to use for analysis.",
        )
        st.session_state.use_ollama = st.toggle("Use AI (Ollama)", value=True)
    else:
        st.markdown(
            "<span class='status-offline'>● Ollama Offline</span>",
            unsafe_allow_html=True,
        )
        st.caption("Running heuristic fallback. Start Ollama to enable AI.")
        st.session_state.use_ollama = False

    st.divider()

    # Output directory
    st.subheader("📁 Output Directory")
    output_path_str = st.text_input(
        "Organised files go here",
        value=str(pathlib.Path.home() / "SlothOps_Organised"),
        help="Folder where organised copies will be placed. Created if it doesn't exist.",
    )
    try:
        st.session_state.output_dir = pathlib.Path(output_path_str).resolve()
    except Exception:
        st.error("Invalid path")
        st.session_state.output_dir = None

    st.divider()

    # History toggle
    st.subheader("🗂️ History")
    st.session_state.history_enabled = st.toggle(
        "Save session history (SQLite)",
        value=st.session_state.history_enabled,
    )

    st.divider()
    st.caption("v1.0.0 · MIT License")


# ── Main layout ───────────────────────────────────────────────────────────────
st.markdown(
    """
    <div class='hero-title'>🦥 SlothOps AI</div>
    <div class='hero-subtitle'>
        Local-first file organisation · AI summaries · Duplicate detection · Undo support
    </div>
    """,
    unsafe_allow_html=True,
)
st.markdown("<br>", unsafe_allow_html=True)

tabs = st.tabs(["📤 Upload & Analyse", "✅ Review & Apply", "📜 History", "ℹ️ About"])


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — UPLOAD & ANALYSE
# ══════════════════════════════════════════════════════════════════════════════
with tabs[0]:
    col_upload, col_info = st.columns([3, 1], gap="large")

    with col_upload:
        st.subheader("Upload Files")
        uploaded = st.file_uploader(
            "Drop .txt or .md files here",
            type=["txt", "md", "markdown"],
            accept_multiple_files=True,
            label_visibility="collapsed",
        )

    with col_info:
        st.markdown(
            """
            <div class='sloth-card'>
              <b style='color:#00D4FF;'>Accepted formats</b><br>
              <span class='metric-chip'>.txt</span>
              <span class='metric-chip'>.md</span>
              <span class='metric-chip'>.markdown</span><br><br>
              <b style='color:#00D4FF;'>Safety</b><br>
              <small style='color:#8B949E;'>
                ✔ Path-traversal blocked<br>
                ✔ Max 10 MB per file<br>
                ✔ Encoding auto-detected<br>
                ✔ Never auto-deletes
              </small>
            </div>
            """,
            unsafe_allow_html=True,
        )

    if uploaded:
        ingested: list[IngestedFile] = []
        for uf in uploaded:
            inf = ingest_streamlit_file(uf)
            ingested.append(inf)

        st.session_state.ingested_files = ingested

        # Quick stats row
        ok_count = sum(1 for f in ingested if f.ok)
        err_count = len(ingested) - ok_count
        c1, c2, c3 = st.columns(3)
        c1.metric("Files Uploaded", len(ingested))
        c2.metric("Valid", ok_count, delta=None)
        c3.metric("Errors", err_count, delta=None)

        st.divider()

        # Analyse button
        if ok_count > 0:
            run_ai = st.button(
                f"🚀 Analyse {ok_count} file(s)" ,
                type="primary",
                use_container_width=True,
            )
        else:
            run_ai = False
            st.warning("No valid files to analyse.")

        if run_ai:
            analyses: dict[str, AnalysisResult] = {}
            corpus: dict[str, str] = {}
            progress = st.progress(0, text="Analysing…")

            valid_files = [f for f in ingested if f.ok]
            for idx, inf in enumerate(valid_files):
                progress.progress(
                    (idx) / len(valid_files),
                    text=f"Analysing {inf.original_name} …",
                )

                plain_text = (
                    strip_markdown(inf.content)
                    if inf.extension in (".md", ".markdown")
                    else inf.content
                )

                if st.session_state.use_ollama:
                    result = ollama_analyze(
                        plain_text,
                        inf.original_name,
                        model=st.session_state.model,
                    )
                else:
                    result = fallback_analyze(plain_text, inf.original_name)

                analyses[inf.original_name] = result
                corpus[inf.original_name] = plain_text

                # Save to history DB
                if st.session_state.history_enabled:
                    try:
                        row_id = hist_db.save_session(
                            filename=inf.original_name,
                            category=result.category,
                            summary=result.summary,
                            proposed_fn=result.proposed_filename,
                            action_items=result.action_items,
                            model_used=result.model_used,
                        )
                        st.session_state.session_ids[inf.original_name] = row_id
                    except Exception:
                        pass  # history is optional

            progress.progress(1.0, text="Done!")
            time.sleep(0.4)
            progress.empty()

            st.session_state.analyses = analyses
            st.session_state.corpus = corpus
            st.success(f"✅ Analysed {len(analyses)} file(s).")

        # ── Display results ──────────────────────────────────────────────────
        if st.session_state.analyses:
            st.subheader("Analysis Results")
            for inf in [f for f in st.session_state.ingested_files if f.ok]:
                result = st.session_state.analyses.get(inf.original_name)
                if not result:
                    continue

                with st.expander(
                    f"📄 {inf.original_name}  →  📂 {result.category}",
                    expanded=True,
                ):
                    col_l, col_r = st.columns([2, 1])

                    with col_l:
                        st.markdown(
                            f"<div class='cat-badge'>📂 {result.category}</div>",
                            unsafe_allow_html=True,
                        )
                        st.markdown(f"**Summary:** {result.summary}")

                        if result.action_items:
                            st.markdown("**Action Items:**")
                            for item in result.action_items:
                                st.markdown(
                                    f"<div class='action-item'>☑ {item}</div>",
                                    unsafe_allow_html=True,
                                )
                        else:
                            st.caption("No action items detected.")

                    with col_r:
                        st.markdown("**Proposed filename:**")
                        st.code(result.proposed_filename, language=None)
                        st.markdown(
                            f"<span class='metric-chip'>Words: {inf.word_count}</span>"
                            f"<span class='metric-chip'>Lines: {inf.line_count}</span>"
                            f"<span class='metric-chip'>{inf.encoding}</span>",
                            unsafe_allow_html=True,
                        )
                        if result.fallback:
                            st.markdown(
                                "<span class='status-fallback'>⚡ Heuristic mode</span>",
                                unsafe_allow_html=True,
                            )
                        else:
                            st.markdown(
                                f"<span class='status-online'>✓ {result.model_used}</span>",
                                unsafe_allow_html=True,
                            )

                    # Duplicate detection
                    others = {
                        k: v
                        for k, v in st.session_state.corpus.items()
                        if k != inf.original_name
                    }
                    if others:
                        dups = find_duplicates(
                            st.session_state.corpus.get(inf.original_name, inf.content),
                            others,
                        )
                        if dups:
                            st.markdown(
                                "<div class='dup-warning'>"
                                "⚠️ <b>Possible duplicate(s) detected</b><br>"
                                + "<br>".join(
                                    f"&nbsp;&nbsp;• {name} &nbsp; <code>{score:.0%}</code> similarity"
                                    for name, score in dups
                                )
                                + "</div>",
                                unsafe_allow_html=True,
                            )

        # Error files
        errors = [f for f in st.session_state.ingested_files if not f.ok]
        if errors:
            with st.expander("❌ Ingestion Errors", expanded=False):
                for ef in errors:
                    st.error(f"**{ef.original_name}**: {ef.error}")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — REVIEW & APPLY
# ══════════════════════════════════════════════════════════════════════════════
with tabs[1]:
    if not st.session_state.analyses:
        st.info("Upload and analyse files first (Tab 1).")
    else:
        st.subheader("Review Before Applying")
        st.markdown(
            "> ⚠️ **Review carefully.** SlothOps AI **copies** files — it never deletes originals.",
            unsafe_allow_html=False,
        )

        output_dir: Optional[pathlib.Path] = st.session_state.output_dir
        if output_dir is None:
            st.error("Set a valid output directory in the sidebar.")
        else:
            st.markdown(
                f"<div class='sloth-card'>"
                f"📁 <b>Output root:</b> <code>{output_dir}</code>"
                f"</div>",
                unsafe_allow_html=True,
            )

            # Build review table
            pending = []
            for inf in [f for f in st.session_state.ingested_files if f.ok]:
                result = st.session_state.analyses.get(inf.original_name)
                if result:
                    pending.append((inf, result))

            selected: list[tuple[IngestedFile, AnalysisResult]] = []
            with st.form("review_form"):
                st.markdown("**Select files to organise:**")
                for inf, result in pending:
                    dst_preview = (
                        output_dir / result.category / result.proposed_filename
                    )
                    col_cb, col_det = st.columns([1, 5])
                    with col_cb:
                        checked = st.checkbox(
                            inf.original_name,
                            value=True,
                            key=f"cb_{inf.original_name}",
                        )
                    with col_det:
                        st.markdown(
                            f"<small>"
                            f"<b>{inf.original_name}</b> → "
                            f"<code>{result.category}/{result.proposed_filename}</code>"
                            f"</small>",
                            unsafe_allow_html=True,
                        )
                    if checked:
                        selected.append((inf, result))

                apply_btn = st.form_submit_button(
                    "✅ Apply Organisation (Copy)",
                    type="primary",
                    use_container_width=True,
                )

            if apply_btn:
                if not selected:
                    st.warning("No files selected.")
                else:
                    output_dir.mkdir(parents=True, exist_ok=True)
                    op_log: OperationLog = st.session_state.op_log
                    results_msg = []
                    for inf, result in selected:
                        # We only have bytes from the uploader, re-encode content
                        # Write to a temp staging path first
                        staging = output_dir / ".staging"
                        staging.mkdir(exist_ok=True)
                        stage_file = staging / inf.original_name
                        stage_file.write_text(inf.content, encoding="utf-8")

                        ok, msg, dst = copy_organised(
                            src=stage_file,
                            base_output=output_dir,
                            category=result.category,
                            proposed_name=result.proposed_filename,
                            log=op_log,
                        )
                        results_msg.append((inf.original_name, ok, msg))

                        if ok and st.session_state.history_enabled:
                            row_id = st.session_state.session_ids.get(inf.original_name)
                            if row_id:
                                try:
                                    hist_db.mark_applied(row_id)
                                except Exception:
                                    pass

                        # Clean up staging
                        try:
                            stage_file.unlink(missing_ok=True)
                        except Exception:
                            pass

                    for fname, ok, msg in results_msg:
                        if ok:
                            st.success(f"✅ {fname}: {msg}")
                        else:
                            st.error(f"❌ {fname}: {msg}")

            # Undo
            st.divider()
            col_undo, col_hist = st.columns(2)
            with col_undo:
                if st.button("↩️ Undo Last Operation", use_container_width=True):
                    msg = st.session_state.op_log.undo_last()
                    if msg:
                        st.info(msg)
                    else:
                        st.warning("Nothing to undo.")

            with col_hist:
                with st.expander("📋 Operation History"):
                    ops = st.session_state.op_log.history()
                    if ops:
                        for op in ops:
                            icon = "✅" if not op.undone else "↩️"
                            st.markdown(
                                f"<small>{icon} {op.description} &nbsp; "
                                f"{'<s>undone</s>' if op.undone else ''}</small>",
                                unsafe_allow_html=True,
                            )
                    else:
                        st.caption("No operations recorded yet.")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — HISTORY
# ══════════════════════════════════════════════════════════════════════════════
with tabs[2]:
    st.subheader("Session History")
    st.markdown(
        "<div class='privacy-pill'>🔒 Stored locally in SQLite · Never synced externally</div>",
        unsafe_allow_html=True,
    )
    st.markdown("<br>", unsafe_allow_html=True)

    if not st.session_state.history_enabled:
        st.info("History is disabled. Enable it in the sidebar.")
    else:
        try:
            entries = hist_db.get_all()
        except Exception as exc:
            entries = []
            st.warning(f"Could not read history: {exc}")

        if not entries:
            st.caption("No history yet. Analyse some files first.")
        else:
            col_cl, _ = st.columns([1, 3])
            with col_cl:
                if st.button("🗑️ Clear All History", type="secondary"):
                    try:
                        deleted = hist_db.clear_history()
                        st.success(f"Cleared {deleted} records.")
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Failed: {exc}")

            for entry in entries:
                applied_tag = "✅ Applied" if entry.applied else "⏳ Pending"
                with st.expander(
                    f"{entry.ts_human} · {entry.filename} · {applied_tag}",
                    expanded=False,
                ):
                    st.markdown(f"**Category:** `{entry.category}`")
                    st.markdown(f"**Proposed filename:** `{entry.proposed_fn}`")
                    st.markdown(f"**Summary:** {entry.summary}")
                    st.markdown(f"**Model:** `{entry.model_used}`")
                    if entry.action_items:
                        st.markdown("**Action items:**")
                        for item in entry.action_items:
                            st.markdown(f"- {item}")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 — ABOUT
# ══════════════════════════════════════════════════════════════════════════════
with tabs[3]:
    st.subheader("About SlothOps AI")

    c1, c2 = st.columns(2)
    with c1:
        st.markdown(
            """
            <div class='sloth-card'>
            <h4 style='color:#00D4FF; margin-top:0;'>🦥 What is SlothOps AI?</h4>
            <p>SlothOps AI is a local-first file organisation assistant that uses Ollama
            (Gemma open-weight models) to intelligently categorise, summarise, and propose
            organised filenames for your TXT and Markdown documents.</p>
            <p>Built for <strong>Hacktoberfest 2026 · Week 3</strong>.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown(
            """
            <div class='sloth-card'>
            <h4 style='color:#00D4FF; margin-top:0;'>🔒 Privacy</h4>
            <ul>
              <li>All AI inference runs <strong>locally</strong> via Ollama</li>
              <li>SQLite history lives on your machine only</li>
              <li>No telemetry, no cloud sync, no API keys required</li>
              <li>Files are never automatically deleted</li>
            </ul>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with c2:
        st.markdown(
            """
            <div class='sloth-card'>
            <h4 style='color:#00D4FF; margin-top:0;'>⚙️ Features</h4>
            <ul>
              <li>Safe TXT &amp; Markdown ingestion (path-traversal protection)</li>
              <li>AI-generated summaries via Gemma / Ollama</li>
              <li>Semantic category classification (10 categories)</li>
              <li>Proposed safe filenames</li>
              <li>Action-item extraction</li>
              <li>Jaccard-similarity duplicate detection</li>
              <li>Review-before-apply workflow</li>
              <li>Collision protection (auto-numbered suffixes)</li>
              <li>Undoable file operations</li>
              <li>Deterministic heuristic fallback</li>
              <li>Optional SQLite session history</li>
            </ul>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown(
            """
            <div class='sloth-card'>
            <h4 style='color:#00D4FF; margin-top:0;'>📦 Stack</h4>
            <span class='metric-chip'>Python 3.11+</span>
            <span class='metric-chip'>Streamlit</span>
            <span class='metric-chip'>Ollama</span>
            <span class='metric-chip'>Gemma 2B</span>
            <span class='metric-chip'>SQLite</span>
            <span class='metric-chip'>chardet</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
