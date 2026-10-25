---
title: "SlothOps AI — Local File Organisation with Ollama & Streamlit"
published: false
description: "A privacy-first Hacktoberfest 2026 Week 3 project: AI-powered file organisation running 100% locally with Gemma, Ollama, Streamlit, and SQLite."
tags: hacktoberfest, python, ollama, streamlit
cover_image: ""
series: "Hacktoberfest 2026"
---

> ⚠️ **Draft** — Do not publish without author approval.

---

# 🦥 SlothOps AI: AI-Powered File Organisation That Never Leaves Your Machine

Every developer I know has a `Downloads` folder that looks like a digital junk drawer — cryptically named files, duplicates, things they've half-read and half-forgotten. For **Hacktoberfest 2026 Week 3**, I built **SlothOps AI**: a local-first file organisation assistant that uses open-weight AI to make sense of the chaos.

## The Core Idea

SlothOps AI reads your `.txt` and `.md` files and uses a locally-running Gemma model (via [Ollama](https://ollama.com)) to:

- Write a plain-English **summary** of each file
- Assign it a **semantic category** (Meeting Notes, Research, Project Plan, etc.)
- Propose a **clean filename** based on the content
- Extract **action items** (TODOs, checkboxes, ACTION: lines)
- Detect near-**duplicates** using Jaccard bigram similarity
- **Organise** files into a folder structure — with your explicit approval first

And when Ollama isn't running? A pure-Python **heuristic fallback** kicks in automatically.

## Privacy First (For Real)

I'm tired of tools that claim "local-first" but phone home. SlothOps AI is genuinely 100% offline:

- AI inference runs locally via Ollama (no API key, no cloud)
- Session history is stored in SQLite on your own machine
- No telemetry, no analytics, no network calls

The UI shows a permanent `🔒 100% Local · No data leaves your machine` badge as a constant reminder.

## Safety Features

I spent as much time on the safety guardrails as on the features:

- **Path-traversal protection**: filenames like `../../etc/passwd` are rejected before any file touch happens
- **Extension allowlist**: only `.txt`, `.md`, `.markdown` — nothing executable
- **Collision protection**: if a destination file exists, the app appends `_1`, `_2`, etc. — never overwrites
- **No auto-delete**: `DELETE` doesn't appear anywhere in the codebase. Files are always *copied*, never moved without undo support
- **Undo stack**: every copy/rename is recorded and reversible in-session

## Tech Stack

| Layer | Tech |
|---|---|
| UI | Streamlit (dark navy/cyan theme) |
| AI | Ollama + Gemma 2B (configurable) |
| Ingestion | chardet + custom safe parser |
| File ops | Python stdlib — pathlib, shutil |
| History | SQLite (stdlib) |
| Tests | pytest (89 tests, 100% pass) |

## The Heuristic Fallback

One design constraint I set for myself: the app must be usable without any AI at all. The `fallback_analyze()` function uses:

- **Keyword frequency** to classify documents into 10 categories
- **Top-N word extraction** (with stop-word filtering) to propose filenames
- **Regex patterns** to extract `- [ ] task`, `TODO: item`, and `ACTION: thing` lines
- **Jaccard bigram similarity** for duplicate detection (pure math, no model needed)

This means SlothOps AI works on air-gapped machines, CI environments, or when Ollama is just taking too long to start.

## Verified Test Results

I ran `pytest tests/ -v` and can confirm:

```
89 passed in 1.01s
```

Test coverage spans:
- ✅ Path-traversal rejection (both Unix and Windows paths)
- ✅ Encoding detection and CRLF normalisation
- ✅ Category classification
- ✅ Action-item extraction
- ✅ Duplicate detection accuracy
- ✅ Collision protection
- ✅ Undo behaviour
- ✅ SQLite round-trips
- ✅ LLM JSON parse + fallback on garbage response

## What I Learned

**Ollama's JSON output isn't always valid JSON.** Even with `"format": "json"` and a clear schema in the prompt, Gemma sometimes wraps the response in markdown code fences. The `_parse_llm_json()` function handles this by stripping fences, then falling back to regex extraction, then returning the heuristic result — three layers of degradation before giving up.

**Path traversal is more subtle than I thought.** On Windows, `pathlib.Path("../../evil").name` returns `"evil"` — the basename of the traversal target, not a rejection. You have to check the *raw input string* for separators before touching pathlib.

## Getting Started

```bash
git clone <repo-url>
cd slothops-ai
pip install -r requirements.txt
ollama pull gemma:2b
streamlit run app.py
```

Drop some `.txt` or `.md` files in, click **Analyse**, review the results, and let SlothOps do the filing.

---

*Built for Hacktoberfest 2026 · Week 3 · MIT License*

*SlothOps AI is a personal project and not affiliated with Google, Ollama, or Streamlit.*
