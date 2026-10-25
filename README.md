# 🦥 SlothOps AI

> **Hacktoberfest 2026 · Week 3 Project**  
> Local-first file organisation assistant powered by Ollama + Gemma open-weight models.

[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python)](https://python.org)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.35+-FF4B4B?logo=streamlit)](https://streamlit.io)
[![Ollama](https://img.shields.io/badge/Ollama-local_AI-black)](https://ollama.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-green)](LICENSE)

---

## What is SlothOps AI?

SlothOps AI is a **privacy-first, fully local** file organisation assistant that intelligently analyses your `.txt` and `.md` files using open-weight AI models running on your machine via [Ollama](https://ollama.com). It never sends your data to the cloud.

### Key Features

| Feature | Details |
|---|---|
| 🔒 **Safe Ingestion** | Path-traversal protection, extension allowlist, 10 MB limit, charset auto-detection |
| 🤖 **AI Analysis** | Summaries, semantic categories, proposed filenames via Gemma/Ollama |
| ⚡ **Deterministic Fallback** | Works offline — heuristic analysis when Ollama is unavailable |
| 🗂️ **Smart Categories** | 10 semantic categories (Meeting Notes, Project Plan, Research, etc.) |
| ✅ **Action-Item Extraction** | Detects TODO/checkbox/ACTION patterns |
| 🔍 **Duplicate Detection** | Jaccard-similarity bigram analysis |
| 👁️ **Review Before Apply** | Never organises files without your explicit approval |
| 💥 **Collision Protection** | Auto-numbered suffixes (file_1.txt, file_2.txt, …) |
| ↩️ **Undo Support** | Full in-session undo for all file operations |
| 📜 **Local History** | Optional SQLite session history (100% on your machine) |

---

## Screenshots

> 📸 *See `docs/screenshots_checklist.md` for the screenshots checklist.*

---

## Architecture

```
slothops-ai/
├── app.py                    # Streamlit UI entry point
├── slothops/
│   ├── __init__.py
│   ├── ingest.py             # Safe file ingestion
│   ├── ai_engine.py          # Ollama/Gemma + heuristic fallback
│   ├── file_ops.py           # Collision-safe, undoable file operations
│   └── history.py            # Optional SQLite session history
├── tests/
│   ├── conftest.py
│   ├── test_ingest.py
│   ├── test_ai_engine.py
│   ├── test_file_ops.py
│   └── test_history.py
├── sample_data/              # Example .txt and .md files
├── docs/                     # Architecture diagrams, screenshots checklist
├── .streamlit/config.toml    # Dark navy/cyan theme
├── requirements.txt
├── .gitignore
└── README.md
```

### Data Flow

```
Upload (.txt/.md)
      │
      ▼
 [ingest.py]──────── Path-traversal check
      │               Extension allowlist
      │               Size limit (10 MB)
      │               Encoding detection
      │
      ▼
[ai_engine.py]──────── Ollama available? ──YES──► Gemma model
      │                                             JSON response
      │                                             Category + Summary
      │                      NO
      │                       └──► Heuristic fallback (pure Python)
      │
      ▼
  Analysis Result
  {summary, category, proposed_filename, action_items}
      │
      ▼
 [Review UI]─────── User reviews + selects files
      │
      ▼
 [file_ops.py]────── Collision check → safe_destination()
      │               Copy to output_dir/Category/filename
      │               Record in OperationLog (undo stack)
      │
      ▼
 [history.py]────── Optional SQLite record
```

---

## Setup

### Prerequisites

| Requirement | Version | Install |
|---|---|---|
| Python | 3.11+ | [python.org](https://python.org) |
| Ollama | Latest | [ollama.com](https://ollama.com) |
| Gemma model | Any | `ollama pull gemma:2b` |

### 1. Clone / Download

```bash
git clone <your-repo-url>
cd slothops-ai
```

### 2. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 3. Start Ollama and pull a model

```bash
# Start Ollama (runs as background service)
ollama serve

# Pull Gemma 2B (1.7 GB) — recommended for most machines
ollama pull gemma:2b

# Or for better quality (requires ~5 GB VRAM / 8 GB RAM):
ollama pull gemma:7b
```

### 4. Run the app

```bash
streamlit run app.py
```

Open your browser at **http://localhost:8501**

---

## Running Tests

```bash
# Run all tests with coverage
pytest tests/ -v --tb=short

# With coverage report
pytest tests/ -v --cov=slothops --cov-report=term-missing
```

---

## Usage

1. **Upload** `.txt` or `.md` files in Tab 1
2. **Analyse** — click the "Analyse" button (uses Gemma via Ollama, or heuristic fallback)
3. **Review** the AI-generated summaries, categories, proposed filenames, and action items
4. **Check for duplicates** — flagged automatically if Jaccard similarity ≥ 85%
5. **Switch to Tab 2** — tick the files you want to organise
6. **Apply** — files are **copied** (never deleted) to your output directory
7. **Undo** any operation if needed
8. **View history** in Tab 3 (SQLite, local only)

---

## Configuration

| Setting | Location | Description |
|---|---|---|
| Ollama model | Sidebar → Model selector | Default: `gemma:2b` |
| Output directory | Sidebar | Where organised files are copied |
| History | Sidebar → Toggle | Enable/disable SQLite history |
| UI theme | `.streamlit/config.toml` | Dark navy + cyan |
| Max upload size | `.streamlit/config.toml` | 10 MB |

---

## Privacy

- ✅ All AI inference is **local** via Ollama
- ✅ SQLite history is stored **only on your machine**
- ✅ No API keys required
- ✅ No telemetry or cloud sync
- ✅ Files are **never automatically deleted**
- ✅ Works fully offline (heuristic fallback mode)

---

## Contributing

1. Fork the repo
2. Create a feature branch (`git checkout -b feat/my-feature`)
3. Run tests and ensure they pass (`pytest tests/ -v`)
4. Submit a pull request

---

## License

MIT © 2026 SlothOps AI Contributors
