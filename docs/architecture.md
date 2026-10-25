# Architecture Diagram — SlothOps AI

```
┌─────────────────────────────────────────────────────────────────────┐
│                        SlothOps AI — app.py                         │
│                    Streamlit UI (dark navy/cyan)                     │
└──────────────┬──────────────────────────────────┬───────────────────┘
               │                                  │
               ▼                                  ▼
   ┌───────────────────┐               ┌───────────────────┐
   │   slothops/       │               │   .streamlit/     │
   │   ingest.py       │               │   config.toml     │
   │                   │               │   (theme config)  │
   │  • _safe_filename │               └───────────────────┘
   │  • ingest_bytes   │
   │  • strip_markdown │
   │  • encoding detect│
   └────────┬──────────┘
            │ IngestedFile
            ▼
   ┌───────────────────────────────────────────┐
   │          slothops/ai_engine.py            │
   │                                           │
   │  ollama_analyze()                         │
   │       │                                   │
   │       ├── Ollama available? ──YES──────►  │
   │       │                     Gemma model   │
   │       │                     JSON parse    │
   │       │                     _parse_llm_json│
   │       │                                   │
   │       └── NO ──► fallback_analyze()       │
   │                  _keyword_category()      │
   │                  _extract_actions_heur.() │
   │                  _safe_slug()             │
   │                                           │
   │  find_duplicates() — Jaccard bigrams      │
   │  content_hash()   — SHA-256               │
   └──────────────┬────────────────────────────┘
                  │ AnalysisResult
                  ▼
   ┌───────────────────────────────┐
   │    Review UI (Tab 2)          │
   │    User selects files         │
   │    Previews destination paths │
   └───────────┬───────────────────┘
               │ User clicks Apply
               ▼
   ┌───────────────────────────────────────┐
   │       slothops/file_ops.py            │
   │                                       │
   │  resolve_safe()  — path traversal ✗  │
   │  safe_destination() — collision ✗    │
   │  copy_organised() — never deletes    │
   │  rename_in_place()                   │
   │  OperationLog — undo stack           │
   └───────────────┬───────────────────────┘
                   │ (optional)
                   ▼
   ┌───────────────────────────────┐
   │    slothops/history.py        │
   │    SQLite (local only)        │
   │    save_session()             │
   │    mark_applied()             │
   │    get_all() / clear_history()│
   └───────────────────────────────┘
```

## Component Responsibilities

| Component | File | Key Responsibility |
|---|---|---|
| UI | `app.py` | Streamlit interface, session state, tab routing |
| Ingestion | `ingest.py` | Safe parsing, encoding, path-traversal protection |
| AI Engine | `ai_engine.py` | Ollama/Gemma + heuristic fallback, duplicate detection |
| File Ops | `file_ops.py` | Collision-safe copy/rename, undo stack |
| History | `history.py` | Optional local SQLite session persistence |

## Security Properties

| Threat | Mitigation |
|---|---|
| Path traversal in upload filenames | `_safe_filename()` — rejects any `/` or `\` or `..` segments |
| Path traversal in AI-proposed filenames | `resolve_safe()` — raises if outside base dir |
| File collision overwrite | `safe_destination()` — appends `_N` suffix |
| Accidental deletion | Only `copy` and `rename` ops; no `delete` anywhere in codebase |
| Data exfiltration | Ollama runs locally; no external API calls |
| Oversized uploads | 10 MB hard limit in `ingest_bytes()` |
| Malicious file types | Extension allowlist: `.txt`, `.md`, `.markdown` only |
