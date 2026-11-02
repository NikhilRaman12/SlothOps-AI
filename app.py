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
    AnalysisResult,
)
from slothops.file_ops import OperationLog, copy_organised
from slothops import history as hist_db

# ── Custom CSS ──────────────────────────────────────────────────────────────
CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

:root {
  --bg-0: #07151d;
  --bg-1: #0b1a27;
  --bg-2: #0f2234;
  --panel: rgba(12, 22, 32, 0.88);
  --panel-strong: rgba(16, 27, 39, 0.96);
  --line: rgba(129, 149, 170, 0.18);
  --text: #edf4fb;
  --muted: #9bb0c5;
  --primary: #58d0ff;
  --primary-strong: #83b2ff;
  --success: #6ce3b0;
  --warning: #f5c47a;
  --danger: #ff7d7d;
  --shadow: rgba(0, 0, 0, 0.28);
}

* { font-family: 'Inter', sans-serif !important; }

html, body, [data-testid="stAppViewContainer"] {
    background: linear-gradient(180deg, var(--bg-0) 0%, var(--bg-1) 42%, var(--bg-2) 100%);
}

.stApp {
    background: transparent;
    color: var(--text);
}

[data-testid="stSidebar"] {
    background: linear-gradient(180deg, rgba(10, 17, 26, 0.98), rgba(9, 15, 24, 0.92));
    border-right: 1px solid var(--line);
}

.stSidebar .block-container {
    padding-top: 1.1rem;
}

.main .block-container {
    max-width: 1200px;
    padding-top: 1.5rem;
}

.app-shell {
    max-width: 1240px;
    margin: 0 auto;
    padding-bottom: 2rem;
}

.hero-panel {
    background: rgba(10, 19, 30, 0.82);
    border: 1px solid var(--line);
    border-radius: 22px;
    padding: 1.5rem 1.6rem 1.2rem;
    box-shadow: 0 18px 44px var(--shadow);
}

.product-mark {
    display: flex;
    align-items: center;
    gap: 0.8rem;
    margin-bottom: 0.8rem;
}

.logo-badge {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 48px;
    height: 48px;
    border-radius: 14px;
    background: rgba(88, 208, 255, 0.14);
    border: 1px solid rgba(88, 208, 255, 0.35);
    color: var(--primary);
    font-size: 1.7rem;
}

.product-title {
    font-size: 2.4rem;
    font-weight: 800;
    letter-spacing: -0.05em;
    margin: 0;
    background: linear-gradient(90deg, var(--primary), var(--primary-strong));
    -webkit-background-clip: text;
    background-clip: text;
    color: transparent;
}

.hero-subtitle {
    color: var(--muted);
    font-size: 1.2rem;
    line-height: 1.5;
    margin: 0.2rem 0 1.3rem;
    letter-spacing: 0.02em;
}

.top-nav {
    display: flex;
    flex-wrap: wrap;
    gap: 0.7rem;
    padding: 0.5rem 0 0.7rem;
    border-bottom: 1px solid var(--line);
    margin-bottom: 1.3rem;
}

.nav-pill {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.58rem 0.85rem;
    border-radius: 10px;
    background: rgba(255,255,255,0.02);
    border: 1px solid transparent;
    color: var(--text);
    font-weight: 700;
}

.nav-pill.active {
    background: rgba(88, 208, 255, 0.09);
    border-color: rgba(88, 208, 255, 0.24);
    color: var(--primary);
}

.panel-card {
    background: rgba(14, 22, 32, 0.9);
    border: 1px solid var(--line);
    border-radius: 16px;
    padding: 1.2rem;
}

.upload-layout {
    display: grid;
    grid-template-columns: minmax(0, 3fr) minmax(220px, 1fr);
    gap: 1rem;
    align-items: start;
    margin-top: 0.8rem;
}

.info-box {
    border-radius: 14px;
    background: rgba(16, 27, 38, 0.78);
    border: 1px solid rgba(88, 208, 255, 0.22);
    padding: 1.1rem 1rem;
}

.accepted-tag, .metric-chip {
    display: inline-block;
    background: rgba(88, 208, 255, 0.08);
    color: var(--primary);
    border: 1px solid rgba(88, 208, 255, 0.24);
    border-radius: 999px;
    padding: 0.25rem 0.7rem;
    margin: 0.22rem 0.26rem 0 0;
    font-size: 0.73rem;
    font-weight: 600;
}

.status-pill {
    display: inline-flex;
    align-items: center;
    gap: 0.45rem;
    border-radius: 999px;
    padding: 0.36rem 0.75rem;
    border: 1px solid rgba(108, 227, 176, 0.22);
    background: rgba(108, 227, 176, 0.08);
    color: var(--success);
    font-size: 0.76rem;
    font-weight: 700;
}

.status-pill.warning {
    border-color: rgba(245, 196, 122, 0.25);
    background: rgba(245, 196, 122, 0.08);
    color: var(--warning);
}

.status-pill.danger {
    border-color: rgba(255, 125, 125, 0.25);
    background: rgba(255, 125, 125, 0.08);
    color: var(--danger);
}

.file-uploader-box {
    background: rgba(11, 20, 29, 0.72);
    border: 1px solid rgba(88, 208, 255, 0.22);
    border-radius: 14px;
    padding: 0.9rem 1rem;
}

.stButton > button {
    background: linear-gradient(180deg, rgba(88,208,255,0.16), rgba(88,208,255,0.08));
    color: var(--text);
    border: 1px solid rgba(88,208,255,0.32);
    border-radius: 12px;
    font-weight: 700;
    min-height: 2.9rem;
}

.stButton > button:hover {
    border-color: rgba(88,208,255,0.56);
    transform: translateY(-1px);
}

.dupe-box {
    background: rgba(255, 125, 125, 0.08);
    border: 1px solid rgba(255, 125, 125, 0.24);
    border-radius: 12px;
    color: #ffd9d9;
    padding: 0.85rem 1rem;
}

.stAlert { border-radius: 12px; }

[data-testid="stMetricValue"] { color: var(--primary); }

[aria-label="File Uploader"] {
    border: 1px dashed rgba(88, 208, 255, 0.33);
    background: rgba(88,208,255,0.02);
    border-radius: 12px;
}

div[data-testid="stExpander"] {
    border: 1px solid var(--line);
    border-radius: 14px;
    overflow: hidden;
}

@media (max-width: 900px) {
    .upload-layout { grid-template-columns: 1fr; }
    .product-title { font-size: 2rem; }
    .hero-panel { padding: 1rem; }
}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


# ── Session state init ───────────────────────────────────────────────────────
def _init_state() -> None:
    defaults = {
        "ingested_files": [],
        "analyses": {},
        "op_log": OperationLog(),
        "output_dir": None,
        "history_enabled": True,
        "model": "gemma:2b",
        "use_ollama": True,
        "corpus": {},
        "session_ids": {},
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


_init_state()


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


with st.sidebar:
    st.markdown(
        """
        <div style='text-align:center; padding: 0.5rem 0 1rem;'>
            <div class='logo-badge' style='width:58px;height:58px;border-radius:16px;margin:0 auto 0.8rem;font-size:2rem;'>🦥</div>
            <div style='font-size:1.6rem; font-weight:800; color:#58d0ff;'>SlothOps AI</div>
            <div style='color:#9bb0c5; font-size:0.8rem; margin-top:0.35rem;'>Privacy-first document workspace</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.divider()

    st.markdown("<div class='nav-pill active'>Overview</div>", unsafe_allow_html=True)
    st.markdown("<div class='nav-pill'>Library</div>", unsafe_allow_html=True)
    st.markdown("<div class='nav-pill'>Analyze</div>", unsafe_allow_html=True)
    st.markdown("<div class='nav-pill'>Review & Organize</div>", unsafe_allow_html=True)
    st.markdown("<div class='nav-pill'>Activity</div>", unsafe_allow_html=True)
    st.markdown("<div class='nav-pill'>Settings</div>", unsafe_allow_html=True)

    st.divider()
    st.warning(
        "Privacy: uploaded files are processed by the server running this Streamlit app. "
        "Use only non-sensitive files in hosted deployments."
    )

    ollama_ok, available_models = check_ollama()
    if ollama_ok:
        st.markdown("<div class='status-pill'>● Ollama online</div>", unsafe_allow_html=True)
        model_options = available_models if available_models else ["gemma:2b"]
        gemma_models = [m for m in model_options if "gemma" in m.lower()]
        other_models = [m for m in model_options if "gemma" not in m.lower()]
        ordered = gemma_models + other_models
        st.session_state.model = st.selectbox(
            "Model",
            ordered,
            index=0,
            help="Select the local Ollama model to use for analysis.",
        )
        st.session_state.use_ollama = st.toggle("Use AI (Ollama)", value=True)
    else:
        st.markdown("<div class='status-pill warning'>● Ollama offline</div>", unsafe_allow_html=True)
        st.caption("Falling back to local heuristics.")
        st.session_state.use_ollama = False

    st.divider()
    st.subheader("Output directory")
    output_path_str = st.text_input(
        "Organised files go here",
        value=str(pathlib.Path.home() / "SlothOps_Organised"),
        help="Folder where organised copies will be placed.",
    )
    try:
        st.session_state.output_dir = pathlib.Path(output_path_str).resolve()
    except Exception:
        st.error("Invalid path")
        st.session_state.output_dir = None

    st.divider()
    st.subheader("History")
    st.session_state.history_enabled = st.toggle(
        "Save local SQLite history",
        value=st.session_state.history_enabled,
    )

    st.caption("v1.0.0 · MIT License")


st.markdown(
    """
    <div class='app-shell'>
      <div class='hero-panel'>
        <div class='product-mark'>
          <div class='logo-badge'>🦥</div>
          <div class='product-title'>SlothOps AI</div>
        </div>
        <div class='hero-subtitle'>Local-first file organization • AI summaries • Duplicate detection • Undo support</div>
        <div class='top-nav'>
          <div class='nav-pill active'>Upload & Analyse</div>
          <div class='nav-pill'>Review & Apply</div>
          <div class='nav-pill'>History</div>
          <div class='nav-pill'>About</div>
        </div>
    """,
    unsafe_allow_html=True,
)

# ── Main content continues with original tabs below. ──────────────────────────
# Keep the existing app behavior and just update the shell styling around it.
tabs = st.tabs(["📤 Upload & Analyse", "✅ Review & Apply", "📜 History", "ℹ️ About"])

# █████████████████████████████████████████████████████████████████████████████
# TAB 1 — UPLOAD & ANALYSE
# █████████████████████████████████████████████████████████████████████████████
with tabs[0]:
    st.markdown("<div class='panel-card'>", unsafe_allow_html=True)
    col_upload, col_info = st.columns([3, 1], gap="large")

    with col_upload:
        st.subheader("Upload Files")
        st.info(
            "**Where are my files processed?** Files selected here are uploaded to the "
            "server hosting this Streamlit app. In the public hosted demo, that means "
            "the demo server receives them. Use only non-sensitive sample files in the "
            "hosted demo. For confidential documents, deploy SlothOps AI locally on a "
            "machine you control."
        )
        st.markdown("<div class='file-uploader-box'>", unsafe_allow_html=True)
        uploaded = st.file_uploader(
            "Drop .txt or .md files here",
            type=["txt", "md", "markdown"],
            accept_multiple_files=True,
            label_visibility="collapsed",
        )
        st.markdown("</div>", unsafe_allow_html=True)

    with col_info:
        st.markdown(
            """
            <div class='panel-card'>
              <div style='font-weight:800; color:#58d0ff; margin-bottom:0.55rem;'>Accepted formats</div>
              <span class='accepted-tag'>.txt</span>
              <span class='accepted-tag'>.md</span>
              <span class='accepted-tag'>.markdown</span>
              <div style='margin-top:1rem; font-weight:800; color:#58d0ff;'>Safety</div>
              <div style='color:#9bb0c5; line-height:1.8; margin-top:0.35rem;'>
                ✓ Path traversal blocked<br>
                ✓ Max 10 MB per file<br>
                ✓ Encoding auto-detected<br>
                ✓ Never auto-deletes
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("</div>", unsafe_allow_html=True)

    if uploaded:
        ingested: list[IngestedFile] = []
        for uf in uploaded:
            inf = ingest_streamlit_file(uf)
            ingested.append(inf)

        st.session_state.ingested_files = ingested

        ok_count = sum(1 for f in ingested if f.ok)
        err_count = len(ingested) - ok_count
        c1, c2, c3 = st.columns(3)
        c1.metric("Files Uploaded", len(ingested))
        c2.metric("Valid", ok_count)
        c3.metric("Errors", err_count)

        st.divider()

        if ok_count > 0:
            run_ai = st.button(f"Analyse {ok_count} file(s)", type="primary", use_container_width=True)
        else:
            run_ai = False
            st.warning("No valid files to analyse.")

        if run_ai:
            analyses: dict[str, AnalysisResult] = {}
            corpus: dict[str, str] = {}
            progress = st.progress(0, text="Analysing…")

            valid_files = [f for f in ingested if f.ok]
            for idx, inf in enumerate(valid_files):
                progress.progress((idx) / len(valid_files), text=f"Analysing {inf.original_name} …")
                plain_text = strip_markdown(inf.content) if inf.extension in (".md", ".markdown") else inf.content

                if st.session_state.use_ollama:
                    result = ollama_analyze(plain_text, inf.original_name, model=st.session_state.model)
                else:
                    result = fallback_analyze(plain_text, inf.original_name)

                analyses[inf.original_name] = result
                corpus[inf.original_name] = plain_text

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
                        pass

            progress.progress(1.0, text="Done!")
            time.sleep(0.4)
            progress.empty()

            st.session_state.analyses = analyses
            st.session_state.corpus = corpus
            st.success(f"Analysed {len(analyses)} file(s).")

        if st.session_state.analyses:
            st.subheader("Analysis Results")
            for inf in [f for f in st.session_state.ingested_files if f.ok]:
                result = st.session_state.analyses.get(inf.original_name)
                if not result:
                    continue

                with st.expander(f"📄 {inf.original_name} → {result.category}", expanded=True):
                    col_l, col_r = st.columns([2, 1])

                    with col_l:
                        st.markdown(f"<div class='status-pill'>📂 {result.category}</div>", unsafe_allow_html=True)
                        st.markdown(f"**Summary:** {result.summary}")

                        if result.action_items:
                            st.markdown("**Action Items:**")
                            for item in result.action_items:
                                st.markdown(f"- {item}")
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
                            st.markdown("<div class='status-pill warning'>⚡ Heuristic mode</div>", unsafe_allow_html=True)
                        else:
                            st.markdown(f"<div class='status-pill'>✓ {result.model_used}</div>", unsafe_allow_html=True)

                    others = {k: v for k, v in st.session_state.corpus.items() if k != inf.original_name}
                    if others:
                        dups = find_duplicates(st.session_state.corpus.get(inf.original_name, inf.content), others)
                        if dups:
                            st.markdown(
                                "<div class='dupe-box'>⚠️ Possible duplicate(s) detected<br>" +
                                "<br>".join(f"• {name} <code>{score:.0%}</code> similarity" for name, score in dups) +
                                "</div>",
                                unsafe_allow_html=True,
                            )

        errors = [f for f in st.session_state.ingested_files if not f.ok]
        if errors:
            with st.expander("❌ Ingestion Errors", expanded=False):
                for ef in errors:
                    st.error(f"**{ef.original_name}**: {ef.error}")

# TAB 2 — REVIEW & APPLY
with tabs[1]:
    if not st.session_state.analyses:
        st.info("Upload and analyse files first (Tab 1).")
    else:
        st.subheader("Review Before Applying")
        st.markdown(
            "> **Review carefully.** SlothOps AI **copies** files — it never deletes originals.",
            unsafe_allow_html=False,
        )

        output_dir: Optional[pathlib.Path] = st.session_state.output_dir
        if output_dir is None:
            st.error("Set a valid output directory in the sidebar.")
        else:
            st.markdown(
                f"<div class='panel-card'>📁 <b>Output root:</b> <code>{output_dir}</code></div>",
                unsafe_allow_html=True,
            )

            pending = []
            for inf in [f for f in st.session_state.ingested_files if f.ok]:
                result = st.session_state.analyses.get(inf.original_name)
                if result:
                    pending.append((inf, result))

            selected: list[tuple[IngestedFile, AnalysisResult]] = []
            with st.form("review_form"):
                st.markdown("**Select files to organise:**")
                for inf, result in pending:
                    col_cb, col_det = st.columns([1, 5])
                    with col_cb:
                        checked = st.checkbox(inf.original_name, value=True, key=f"cb_{inf.original_name}")
                    with col_det:
                        st.markdown(f"<small><b>{inf.original_name}</b> → <code>{result.category}/{result.proposed_filename}</code></small>", unsafe_allow_html=True)
                    if checked:
                        selected.append((inf, result))

                apply_btn = st.form_submit_button("Apply Organisation (Copy)", type="primary", use_container_width=True)

            if apply_btn:
                if not selected:
                    st.warning("No files selected.")
                else:
                    output_dir.mkdir(parents=True, exist_ok=True)
                    op_log: OperationLog = st.session_state.op_log
                    results_msg = []
                    for inf, result in selected:
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

                        try:
                            stage_file.unlink(missing_ok=True)
                        except Exception:
                            pass

                    for fname, ok, msg in results_msg:
                        if ok:
                            st.success(f"{fname}: {msg}")
                        else:
                            st.error(f"{fname}: {msg}")

            st.divider()
            col_undo, col_hist = st.columns(2)
            with col_undo:
                if st.button("Undo Last Operation", use_container_width=True):
                    msg = st.session_state.op_log.undo_last()
                    if msg:
                        st.info(msg)
                    else:
                        st.warning("Nothing to undo.")

            with col_hist:
                with st.expander("Operation History"):
                    ops = st.session_state.op_log.history()
                    if ops:
                        for op in ops:
                            icon = "✅" if not op.undone else "↩️"
                            st.markdown(f"<small>{icon} {op.description} {'<s>undone</s>' if op.undone else ''}</small>", unsafe_allow_html=True)
                    else:
                        st.caption("No operations recorded yet.")

# TAB 3 — HISTORY
with tabs[2]:
    st.subheader("Session History")
    st.markdown("<div class='status-pill'>🔒 Stored locally in SQLite</div>", unsafe_allow_html=True)
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
            for entry in entries:
                applied_tag = "✅ Applied" if entry.applied else "⏳ Pending"
                with st.expander(f"{entry.ts_human} · {entry.filename} · {applied_tag}", expanded=False):
                    st.markdown(f"**Category:** `{entry.category}`")
                    st.markdown(f"**Proposed filename:** `{entry.proposed_fn}`")
                    st.markdown(f"**Summary:** {entry.summary}")
                    st.markdown(f"**Model:** `{entry.model_used}`")
                    if entry.action_items:
                        st.markdown("**Action items:**")
                        for item in entry.action_items:
                            st.markdown(f"- {item}")

# TAB 4 — ABOUT
with tabs[3]:
    st.subheader("About SlothOps AI")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(
            """
            <div class='panel-card'>
              <h4 style='color:#58d0ff; margin-top:0;'>What is SlothOps AI?</h4>
              <p>SlothOps AI is a local-first file organization assistant that uses Ollama (Gemma open-weight models) to summarize, categorize, and propose organized filenames for TXT and Markdown documents.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown(
            """
            <div class='panel-card'>
              <h4 style='color:#58d0ff; margin-top:0;'>Privacy & Data Handling</h4>
              <ul>
                <li>Uploads are processed by the server running the app.</li>
                <li>Hosted demo servers receive files; do not upload confidential documents.</li>
                <li>Local deployment keeps file handling on the machine you control.</li>
                <li>Files are never auto-deleted.</li>
              </ul>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with c2:
        st.markdown(
            """
            <div class='panel-card'>
              <h4 style='color:#58d0ff; margin-top:0;'>Features</h4>
              <ul>
                <li>Safe TXT & Markdown ingestion</li>
                <li>AI summaries via Ollama/Gemma</li>
                <li>Category classification</li>
                <li>Proposed safe filenames</li>
                <li>Action-item extraction</li>
                <li>Duplicate detection</li>
                <li>Review-before-apply workflow</li>
                <li>Collision protection</li>
                <li>Undoable operations</li>
              </ul>
            </div>
            """,
            unsafe_allow_html=True,
        )

st.markdown("</div>", unsafe_allow_html=True)
