# 🦥 SlothOps AI

> **Hacktoberfest 2026 · Week 3 Project**  
> Local-first file organisation assistant powered by Ollama + Gemma open-weight models.

[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python)](https://python.org)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.35+-FF4B4B?logo=streamlit)](https://streamlit.io)
[![Ollama](https://img.shields.io/badge/Ollama-local_AI-black)](https://ollama.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-green)](LICENSE)

---

## What is SlothOps AI?

SlothOps AI is a **local-first** file organisation assistant that analyses `.txt` and `.md` files using open-weight AI models through [Ollama](https://ollama.com). The privacy properties depend on where you run it: when using a hosted Streamlit demo, uploaded files are sent to and processed by the demo server. For sensitive documents, deploy the app locally on a machine you control and review any external services you configure.

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
git clone https://github.com/NikhilRaman12/SlothOps-AI.git
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

## Privacy & Data Handling

SlothOps AI is designed for local-first use, but **hosted and local deployments have different privacy properties**.

### Hosted Streamlit demo

- Files selected through the uploader are sent to the server hosting the Streamlit app.
- The server receives the uploaded file content for ingestion and analysis; files may also be written to the configured output directory when the user applies organisation.
- Do not upload confidential, personal, regulated, or otherwise sensitive documents to a public hosted demo.
- Treat the hosted demo environment as a server you do not control.

### Local deployment

- When you run Streamlit and Ollama on a trusted local machine, file handling and model inference can remain on that machine.
- Confirm that Ollama is running locally and that no remote model endpoint or external integration is configured.
- If you configure external AI/API services, data sent to those services is subject to their own privacy and retention policies.
- SQLite history and organised output are stored in the environment where the app is running.
- Files are never automatically deleted by the organisation workflow.

**Recommendation:** Use the hosted demo only with non-sensitive sample files. For sensitive documents, run SlothOps AI locally on a trusted machine and verify your model/API configuration before uploading.

---

## Contributing

1. Fork the repo
2. Create a feature branch (`git checkout -b feat/my-feature`)
3. Run tests and ensure they pass (`pytest tests/ -v`)
4. Submit a pull request

---

## License

MIT © 2026 SlothOps AI Contributors
