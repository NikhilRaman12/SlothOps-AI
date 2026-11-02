from __future__ import annotations

import json
import re
import textwrap
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from slothops.domain import VALID_CATEGORIES


class ProviderError(RuntimeError):
    """Raised when a provider cannot process a document safely."""


def _sanitize_filename(value: str, *, default: str = "document") -> str:
    candidate = Path(value).name
    if not candidate or candidate in {".", ".."}:
        candidate = default
    candidate = re.sub(r"[^A-Za-z0-9._-]+", "_", candidate).strip("._")
    if not candidate:
        candidate = default
    return candidate


class AnalysisResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    summary: str = Field(..., min_length=1, max_length=4000)
    category: str
    proposed_filename: str
    action_items: list[str] = Field(default_factory=list)
    provider: str = "heuristic"
    fallback: bool = False
    raw_response: str = ""

    @field_validator("category")
    @classmethod
    def validate_category(cls, value: str) -> str:
        if value not in VALID_CATEGORIES:
            raise ValueError(f"Unsupported category: {value!r}")
        return value

    @field_validator("proposed_filename")
    @classmethod
    def validate_filename(cls, value: str) -> str:
        safe_name = _sanitize_filename(value)
        if "/" in value or "\\" in value or ".." in value:
            raise ValueError("unsafe filename")
        return safe_name

    @field_validator("action_items")
    @classmethod
    def validate_action_items(cls, value: list[str]) -> list[str]:
        cleaned: list[str] = []
        for item in value:
            text = str(item).strip()
            if text:
                cleaned.append(text[:300])
        return cleaned[:10]


class BaseAIProvider(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def analyze(self, text: str, original_name: str) -> AnalysisResponse:
        raise NotImplementedError


class HeuristicProvider(BaseAIProvider):
    """Deterministic fallback provider that never calls external services."""

    @property
    def name(self) -> str:
        return "heuristic-fallback"

    def analyze(self, text: str, original_name: str) -> AnalysisResponse:
        content = text.strip()
        if not content:
            summary = "Empty document; no substantive content detected."
            category = "Miscellaneous"
            keywords: list[str] = []
        else:
            text_lower = content.lower()
            keywords = re.findall(r"[a-zA-Z]{4,}", text_lower)
            ranked = []
            stop = {
                "this", "that", "with", "from", "into", "have", "will", "they", "your",
                "about", "after", "before", "could", "would", "there", "their", "which",
                "where", "when", "what", "these", "those", "some", "more", "here", "been",
            }
            freq: dict[str, int] = {}
            for word in keywords:
                if len(word) >= 4 and word not in stop:
                    freq[word] = freq.get(word, 0) + 1
            ranked = [word for word, _ in sorted(freq.items(), key=lambda item: (-item[1], item[0]))[:5]]
            category = self._categorize(text_lower)
            summary = textwrap.shorten(
                text[:300].replace("\n", " "),
                width=220,
                placeholder="…",
            )
            if ranked:
                summary = f"{summary} Key themes: {', '.join(ranked)}."

        base_name = Path(original_name).stem or "document"
        slug = _sanitize_filename(base_name, default="document")
        proposed_filename = f"{slug}.txt" if ".md" not in original_name.lower() else f"{slug}.md"
        action_items = self._extract_action_items(text)
        return AnalysisResponse(
            summary=summary,
            category=category,
            proposed_filename=proposed_filename,
            action_items=action_items,
            provider=self.name,
            fallback=True,
            raw_response="deterministic heuristic analysis",
        )

    def _categorize(self, text_lower: str) -> str:
        mapping = {
            "Meeting Notes": ["meeting", "agenda", "minutes", "attendees", "discussion", "follow-up"],
            "Project Plan": ["milestone", "roadmap", "sprint", "deadline", "timeline", "deliverable"],
            "Technical Documentation": ["api", "function", "class", "module", "install", "configuration", "usage"],
            "Research / Reference": ["research", "study", "analysis", "reference", "literature", "finding"],
            "Action Items / TODO": ["todo", "task", "action", "next step", "pending", "follow up"],
            "Personal Journal": ["today", "journal", "feeling", "reflection", "yesterday"],
            "Report / Analysis": ["report", "findings", "kpi", "metrics", "performance", "results"],
            "Creative Writing": ["story", "chapter", "poem", "narrative", "character"],
            "Email / Communication": ["dear", "regards", "subject", "from", "to", "cc"],
        }
        for category, terms in mapping.items():
            if any(term in text_lower for term in terms):
                return category
        return "Miscellaneous"

    def _extract_action_items(self, text: str) -> list[str]:
        items: list[str] = []
        patterns = [
            r"^\s*[-*]\s*\[[ xX]\]\s*(.+)",
            r"^\s*TODO\s*[:\-]?\s*(.+)",
            r"^\s*ACTION\s*[:\-]?\s*(.+)",
        ]
        for line in text.splitlines():
            for pattern in patterns:
                match = re.match(pattern, line, flags=re.IGNORECASE)
                if match:
                    item = match.group(1).strip()
                    if item:
                        items.append(item)
                    break
        return items[:10]


class OllamaProvider(BaseAIProvider):
    def __init__(self, *, model: str = "gemma:2b", timeout_seconds: int = 120, allow_external: bool = False):
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.allow_external = allow_external

    @property
    def name(self) -> str:
        return self.model

    def analyze(self, text: str, original_name: str) -> AnalysisResponse:
        if not self.allow_external:
            raise ProviderError("External AI providers are disabled unless explicitly configured.")
        try:
            import ollama  # type: ignore
        except ImportError as exc:
            raise ProviderError("Ollama package is not installed.") from exc

        prompt = self._build_prompt(text, original_name)
        try:
            response = ollama.chat(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                options={"temperature": 0.2, "num_predict": 512},
                stream=False,
            )
        except Exception as exc:  # pragma: no cover - network errors vary by runtime
            raise ProviderError(f"Ollama request failed: {exc}") from exc

        payload = response.get("message", {}).get("content", "") if isinstance(response, dict) else str(response)
        return self._parse_response(payload, original_name)

    def _build_prompt(self, text: str, filename: str) -> str:
        preview = text[:6000]
        if len(text) > 6000:
            preview += "\n[truncated for analysis]"
        categories = ", ".join(VALID_CATEGORIES)
        return (
            "You are SlothOps AI. Return only a JSON object with keys: "
            "summary, category, proposed_filename, action_items. "
            f"Allowed categories: {categories}. "
            "The proposed filename must be safe, with no folders or path traversal and must keep the original extension. "
            "Action items must be a list of strings. "
            f"Original filename: {filename}\n\n---DOCUMENT START---\n{preview}\n---DOCUMENT END---"
        )

    def _parse_response(self, raw_response: str, original_name: str) -> AnalysisResponse:
        cleaned = raw_response.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r"\s*```$", "", cleaned)
        try:
            payload = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise ProviderError(f"Invalid JSON from Ollama: {exc}") from exc

        if not isinstance(payload, dict):
            raise ProviderError("AI response must be a JSON object.")

        model_payload = {
            "summary": payload.get("summary", "Document analyzed."),
            "category": payload.get("category", "Miscellaneous"),
            "proposed_filename": payload.get("proposed_filename", original_name),
            "action_items": payload.get("action_items", []),
            "provider": self.model,
            "fallback": False,
            "raw_response": raw_response,
        }
        return AnalysisResponse.model_validate(model_payload)


def parse_analysis_payload(raw_response: str, *, default_provider: str = "heuristic") -> AnalysisResponse:
    text = raw_response.strip()
    if not text:
        raise ProviderError("Empty AI response")
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ProviderError(f"Invalid JSON from AI provider: {exc}") from exc
    if not isinstance(payload, dict):
        raise ProviderError("AI payload must be an object.")
    normalized = {
        "summary": payload.get("summary", "Document analyzed."),
        "category": payload.get("category", "Miscellaneous"),
        "proposed_filename": payload.get("proposed_filename", "document.txt"),
        "action_items": payload.get("action_items", []),
        "provider": default_provider,
        "fallback": False,
        "raw_response": raw_response,
    }
    return AnalysisResponse.model_validate(normalized)


__all__ = [
    "AnalysisResponse",
    "BaseAIProvider",
    "HeuristicProvider",
    "OllamaProvider",
    "ProviderError",
    "parse_analysis_payload",
]
