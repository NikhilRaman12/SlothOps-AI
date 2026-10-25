"""
slothops/adapters/fixtures.py
Offline demo fixtures — clearly labeled SYNTHETIC.
These records are used when all three live APIs are unavailable or
when the user selects "Demo / Offline mode".

IMPORTANT: All records here are FABRICATED for demonstration purposes.
They do NOT represent real issues, PRs, papers, or models.
"""

from __future__ import annotations

from datetime import datetime, timezone

from .normaliser import normalise
from .models import NormalisedRecord, SOURCE_SYNTHETIC


def _dt(s: str) -> datetime:
    return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# GitHub fixtures (SYNTHETIC)
# ---------------------------------------------------------------------------

GITHUB_FIXTURES: list[NormalisedRecord] = [
    normalise(
        source=SOURCE_SYNTHETIC,
        record_type="github_issue",
        raw_id="synthetic-gh-001",
        title="[SYNTHETIC] Add rate-limit retry logic to REST client",
        body=(
            "When the API returns HTTP 429, the client should back off exponentially "
            "and retry up to 3 times before surfacing an error to the user.\n\n"
            "Acceptance criteria:\n- [ ] Implement exponential backoff (1s, 2s, 4s)\n"
            "- [ ] Respect Retry-After header when present\n"
            "- [ ] Add unit tests for retry behaviour"
        ),
        url="https://github.com/example/slothops-demo/issues/1",
        created_at="2026-10-01T09:00:00Z",
        updated_at="2026-10-20T14:30:00Z",
        tags=["enhancement", "api", "reliability"],
        author="demo-user-alice",
        extra={"state": "open", "comments": 4, "repo": "example/slothops-demo"},
        synthetic=True,
    ),
    normalise(
        source=SOURCE_SYNTHETIC,
        record_type="github_issue",
        raw_id="synthetic-gh-002",
        title="[SYNTHETIC] Improve SQLite cache eviction for large corpora",
        body=(
            "The cache currently retains all records indefinitely. We need a "
            "configurable max-rows limit and a FIFO eviction strategy to prevent "
            "unbounded growth on long-running instances.\n\n"
            "TODO: Profile cache reads when >10k records are present."
        ),
        url="https://github.com/example/slothops-demo/issues/2",
        created_at="2026-10-10T11:00:00Z",
        updated_at="2026-10-22T08:00:00Z",
        tags=["bug", "performance", "sqlite"],
        author="demo-user-bob",
        extra={"state": "open", "comments": 2, "repo": "example/slothops-demo"},
        synthetic=True,
    ),
    normalise(
        source=SOURCE_SYNTHETIC,
        record_type="github_pr",
        raw_id="synthetic-gh-pr-001",
        title="[SYNTHETIC] feat: Add OpenAlex adapter with pagination support",
        body=(
            "Implements the OpenAlex scholarly-work adapter. Handles cursor-based "
            "pagination, respects the polite-pool mailto requirement, and normalises "
            "all fields into NormalisedRecord schema.\n\n"
            "- [x] Cursor pagination\n- [x] Mailto polite pool\n"
            "- [ ] Tests for >200 result pages\n"
            "ACTION: Request code review from @carol"
        ),
        url="https://github.com/example/slothops-demo/pull/15",
        created_at="2026-10-23T15:00:00Z",
        updated_at="2026-10-24T09:00:00Z",
        tags=["feature", "openalex", "adapters"],
        author="demo-user-carol",
        extra={"state": "open", "draft": False, "repo": "example/slothops-demo"},
        synthetic=True,
    ),
]

# ---------------------------------------------------------------------------
# Hugging Face fixtures (SYNTHETIC)
# ---------------------------------------------------------------------------

HUGGINGFACE_FIXTURES: list[NormalisedRecord] = [
    normalise(
        source=SOURCE_SYNTHETIC,
        record_type="hf_model",
        raw_id="synthetic-hf-model-001",
        title="[SYNTHETIC] demo-org/efficient-ner-multilingual",
        body=(
            "A lightweight Named Entity Recognition model fine-tuned on 12 languages. "
            "Achieves 87.3 F1 on CoNLL-2003 (EN). Model size: 120M params. "
            "Suitable for CPU inference.\n\n"
            "License: Apache 2.0. Intended for research and commercial use."
        ),
        url="https://huggingface.co/demo-org/efficient-ner-multilingual",
        created_at="2026-09-01T00:00:00Z",
        updated_at="2026-10-15T12:00:00Z",
        tags=["ner", "multilingual", "token-classification", "transformers"],
        author="demo-org",
        extra={
            "downloads_last_month": 12400,
            "likes": 87,
            "pipeline_tag": "token-classification",
            "library_name": "transformers",
        },
        synthetic=True,
    ),
    normalise(
        source=SOURCE_SYNTHETIC,
        record_type="hf_dataset",
        raw_id="synthetic-hf-dataset-001",
        title="[SYNTHETIC] demo-org/local-document-classification-v2",
        body=(
            "A synthetic dataset of 50,000 labelled documents across 10 categories "
            "matching SlothOps AI's classification schema. Balanced classes, "
            "CC-BY-4.0 licensed. Suitable for fine-tuning lightweight classifiers."
        ),
        url="https://huggingface.co/datasets/demo-org/local-document-classification-v2",
        created_at="2026-08-15T00:00:00Z",
        updated_at="2026-10-01T00:00:00Z",
        tags=["text-classification", "document-understanding", "synthetic"],
        author="demo-org",
        extra={
            "downloads_last_month": 3200,
            "likes": 44,
            "size_categories": "10K<n<100K",
            "task_categories": ["text-classification"],
        },
        synthetic=True,
    ),
]

# ---------------------------------------------------------------------------
# OpenAlex fixtures (SYNTHETIC)
# ---------------------------------------------------------------------------

OPENALEX_FIXTURES: list[NormalisedRecord] = [
    normalise(
        source=SOURCE_SYNTHETIC,
        record_type="openalex_work",
        raw_id="synthetic-oa-W001",
        title="[SYNTHETIC] Efficient Local Inference of Open-Weight Language Models on Consumer Hardware",
        body=(
            "We present a systematic evaluation of seven open-weight language models "
            "(1B–7B parameters) on consumer-grade CPUs and GPUs. Our results show that "
            "4-bit quantisation achieves <3% quality degradation on standard benchmarks "
            "while reducing memory footprint by 65%. We release benchmark harnesses and "
            "reproducibility scripts under MIT licence."
        ),
        url="https://openalex.org/W001synthetic",
        created_at="2026-07-01T00:00:00Z",
        updated_at="2026-10-10T00:00:00Z",
        tags=["local-llm", "quantisation", "inference", "open-weight"],
        author="Demo A. Author; Demo B. Coauthor",
        extra={
            "doi": "10.0000/synthetic.2026.001",
            "cited_by_count": 42,
            "open_access": True,
            "publication_year": 2026,
            "type": "article",
        },
        synthetic=True,
    ),
    normalise(
        source=SOURCE_SYNTHETIC,
        record_type="openalex_work",
        raw_id="synthetic-oa-W002",
        title="[SYNTHETIC] Privacy-Preserving Document Classification Without Cloud APIs",
        body=(
            "We demonstrate that heuristic keyword scoring combined with lightweight "
            "open-weight models can achieve 91.2% accuracy on a 10-class document "
            "classification benchmark, matching cloud-API baselines at zero marginal cost "
            "and with complete data privacy. Code and datasets available on request."
        ),
        url="https://openalex.org/W002synthetic",
        created_at="2026-09-15T00:00:00Z",
        updated_at="2026-10-20T00:00:00Z",
        tags=["privacy", "document-classification", "local-ml", "no-cloud"],
        author="Demo C. Researcher",
        extra={
            "doi": "10.0000/synthetic.2026.002",
            "cited_by_count": 7,
            "open_access": True,
            "publication_year": 2026,
            "type": "preprint",
        },
        synthetic=True,
    ),
]

# ---------------------------------------------------------------------------
# Combined
# ---------------------------------------------------------------------------

ALL_FIXTURES: list[NormalisedRecord] = (
    GITHUB_FIXTURES + HUGGINGFACE_FIXTURES + OPENALEX_FIXTURES
)


def load_all_fixtures() -> list[NormalisedRecord]:
    """Return all synthetic fixtures. Every record has synthetic=True."""
    return list(ALL_FIXTURES)
