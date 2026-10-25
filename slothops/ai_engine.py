"""
slothops/ai_engine.py
AI analysis: summary, category, filename proposal, action items.
Wraps Ollama (Gemma) with a deterministic fallback when Ollama is unavailable.
"""

from __future__ import annotations

import hashlib
import json
import re
import textwrap
from dataclasses import dataclass, field
from typing import Optional

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

CATEGORIES = [
    "Meeting Notes",
    "Project Plan",
    "Technical Documentation",
    "Research / Reference",
    "Action Items / TODO",
    "Personal Journal",
    "Report / Analysis",
    "Creative Writing",
    "Email / Communication",
    "Miscellaneous",
]


@dataclass
class AnalysisResult:
    summary: str
    category: str
    proposed_filename: str
    action_items: list[str]
    model_used: str
    fallback: bool = False
    raw_response: str = ""


# ---------------------------------------------------------------------------
# Deterministic fallback (no Ollama required)
# ---------------------------------------------------------------------------

_STOP_WORDS = frozenset(
    "a an the and or but in on at to for of with is are was were be been "
    "has have had do does did will would could should may might shall can "
    "not it its this that these those my your his her our their i we you "
    "he she they what which who whom when where why how".split()
)

_CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "Meeting Notes": ["meeting", "agenda", "attendees", "minutes", "discussed", "action items", "follow-up"],
    "Project Plan": ["milestone", "deadline", "sprint", "roadmap", "deliverable", "timeline", "scope"],
    "Technical Documentation": ["api", "function", "class", "module", "install", "configuration", "usage", "example"],
    "Research / Reference": ["study", "research", "analysis", "hypothesis", "conclusion", "references", "literature"],
    "Action Items / TODO": ["todo", "task", "action", "[ ]", "- [ ]", "pending", "assigned to", "due"],
    "Personal Journal": ["today", "feeling", "diary", "journal", "i feel", "i am", "yesterday"],
    "Report / Analysis": ["report", "findings", "metrics", "kpi", "performance", "results", "dashboard"],
    "Creative Writing": ["story", "chapter", "character", "once upon", "poem", "verse", "narrative"],
    "Email / Communication": ["dear", "regards", "sincerely", "subject:", "from:", "to:", "cc:"],
}


def _keyword_category(text_lower: str) -> str:
    scores: dict[str, int] = {}
    for cat, keywords in _CATEGORY_KEYWORDS.items():
        scores[cat] = sum(text_lower.count(kw) for kw in keywords)
    best = max(scores, key=lambda k: scores[k])
    return best if scores[best] > 0 else "Miscellaneous"


def _top_words(text: str, n: int = 5) -> list[str]:
    words = re.findall(r"[a-zA-Z]{4,}", text.lower())
    freq: dict[str, int] = {}
    for w in words:
        if w not in _STOP_WORDS:
            freq[w] = freq.get(w, 0) + 1
    return [w for w, _ in sorted(freq.items(), key=lambda x: -x[1])[:n]]


def _extract_actions_heuristic(text: str) -> list[str]:
    """Pull lines that look like action items."""
    actions: list[str] = []
    patterns = [
        r"^\s*[-*]\s*\[[ x]\]\s*(.+)",     # Markdown checkbox
        r"^\s*TODO[:\s]+(.+)",              # TODO:
        r"^\s*ACTION[:\s]+(.+)",            # ACTION:
        r"^\s*\d+\.\s+(.*(?:must|should|need to|will|assign|follow up).+)",
    ]
    for line in text.splitlines():
        for pat in patterns:
            m = re.match(pat, line, re.IGNORECASE)
            if m:
                item = m.group(1).strip()
                if item and len(item) > 5:
                    actions.append(item)
                break
    return actions[:10]


def _safe_slug(text: str, max_words: int = 5) -> str:
    """Convert text to a safe filename slug."""
    words = re.sub(r"[^a-zA-Z0-9\s]", "", text).split()
    slug = "_".join(w.lower() for w in words[:max_words] if w)
    return slug or "document"


def fallback_analyze(text: str, original_name: str) -> AnalysisResult:
    """
    Pure-Python deterministic analysis — no network, no ML models.
    Used when Ollama is unavailable.
    """
    text_lower = text.lower()

    # Summary: first 3 non-empty lines, then word count
    first_lines = [ln.strip() for ln in text.splitlines() if ln.strip()][:3]
    snippet = " | ".join(first_lines) if first_lines else "(empty document)"
    summary = (
        f"{textwrap.shorten(snippet, width=200, placeholder='…')} "
        f"[{len(text.split())} words, heuristic analysis]"
    )

    category = _keyword_category(text_lower)
    top = _top_words(text)
    base = _safe_slug(" ".join(top)) if top else _safe_slug(original_name.rsplit(".", 1)[0])
    proposed_filename = f"{base}.md" if original_name.endswith(".md") else f"{base}.txt"
    action_items = _extract_actions_heuristic(text)

    return AnalysisResult(
        summary=summary,
        category=category,
        proposed_filename=proposed_filename,
        action_items=action_items,
        model_used="heuristic-fallback",
        fallback=True,
    )


# ---------------------------------------------------------------------------
# Ollama integration
# ---------------------------------------------------------------------------

_PROMPT_TEMPLATE = """\
You are SlothOps AI, a file-organisation assistant. Analyse the document below and reply ONLY with valid JSON matching this schema (no markdown, no extra text):

{{
  "summary": "<2-3 sentence plain-English summary>",
  "category": "<one of: {categories}>",
  "proposed_filename": "<slug_name.ext — no spaces, safe for all OS, keep original extension>",
  "action_items": ["<item>", ...]
}}

Original filename: {filename}

--- DOCUMENT START ---
{content}
--- DOCUMENT END ---
""".strip()


def _build_prompt(text: str, filename: str, max_chars: int = 6000) -> str:
    truncated = text[:max_chars]
    if len(text) > max_chars:
        truncated += "\n[... truncated for analysis ...]"
    return _PROMPT_TEMPLATE.format(
        categories=", ".join(CATEGORIES),
        filename=filename,
        content=truncated,
    )


def _parse_llm_json(raw: str, fallback: AnalysisResult, original_name: str) -> AnalysisResult:
    """Attempt to parse LLM JSON; fall back gracefully on failure."""
    # Strip markdown code fences if present
    cleaned = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        # Try extracting JSON object from the response
        m = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if m:
            try:
                data = json.loads(m.group(0))
            except json.JSONDecodeError:
                return fallback
        else:
            return fallback

    summary = str(data.get("summary", fallback.summary))
    raw_cat = str(data.get("category", fallback.category))
    category = raw_cat if raw_cat in CATEGORIES else fallback.category
    raw_fn = str(data.get("proposed_filename", fallback.proposed_filename))
    # Sanitise proposed filename: basename only, safe chars
    safe_fn = re.sub(r"[^\w.\-]", "_", pathlib.Path(raw_fn).name) if raw_fn else fallback.proposed_filename
    action_items = [str(a) for a in data.get("action_items", fallback.action_items) if a]

    return AnalysisResult(
        summary=summary,
        category=category,
        proposed_filename=safe_fn,
        action_items=action_items[:10],
        model_used=fallback.model_used,  # will be overwritten by caller
        raw_response=raw,
    )


# We import pathlib here since it's used in _parse_llm_json
import pathlib  # noqa: E402


def ollama_analyze(
    text: str,
    original_name: str,
    model: str = "gemma:2b",
    timeout: int = 120,
) -> AnalysisResult:
    """
    Call Ollama with the configured model.
    Falls back to heuristic on any error.
    """
    fallback_result = fallback_analyze(text, original_name)

    try:
        import ollama  # type: ignore

        prompt = _build_prompt(text, original_name)
        response = ollama.chat(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0.2, "num_predict": 512},
        )
        raw_content: str = response["message"]["content"]
        result = _parse_llm_json(raw_content, fallback_result, original_name)
        result.model_used = model
        result.fallback = False
        result.raw_response = raw_content
        return result

    except ImportError:
        fallback_result.raw_response = "ollama package not installed"
        return fallback_result
    except Exception as exc:  # noqa: BLE001
        fallback_result.raw_response = f"Ollama error: {exc}"
        return fallback_result


# ---------------------------------------------------------------------------
# Duplicate detection
# ---------------------------------------------------------------------------

def content_hash(text: str) -> str:
    """SHA-256 of normalised content (lower-case, collapsed whitespace)."""
    normalised = re.sub(r"\s+", " ", text.lower().strip())
    return hashlib.sha256(normalised.encode()).hexdigest()


def similarity_score(a: str, b: str) -> float:
    """
    Fast Jaccard similarity on word bigrams.
    Returns a float in [0.0, 1.0].
    """
    def bigrams(text: str) -> set[tuple[str, str]]:
        words = re.findall(r"[a-zA-Z0-9]+", text.lower())
        return set(zip(words, words[1:])) if len(words) > 1 else set()

    bg_a, bg_b = bigrams(a), bigrams(b)
    if not bg_a and not bg_b:
        return 1.0
    if not bg_a or not bg_b:
        return 0.0
    inter = len(bg_a & bg_b)
    union = len(bg_a | bg_b)
    return inter / union


DUPLICATE_THRESHOLD = 0.85  # Jaccard ≥ this → near-duplicate


def find_duplicates(
    target: str, corpus: dict[str, str]
) -> list[tuple[str, float]]:
    """
    Compare target text against a corpus {name: text}.
    Returns list of (name, score) where score ≥ DUPLICATE_THRESHOLD.
    """
    results: list[tuple[str, float]] = []
    for name, text in corpus.items():
        score = similarity_score(target, text)
        if score >= DUPLICATE_THRESHOLD:
            results.append((name, score))
    return sorted(results, key=lambda x: -x[1])
