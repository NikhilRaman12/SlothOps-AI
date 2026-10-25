"""
slothops/adapters/huggingface_adapter.py
Fetches public model and dataset metadata from the Hugging Face Hub API.

Security
--------
* API responses are UNTRUSTED — all fields normalised before use.
* HF_TOKEN is optional and read from env only. Never hardcoded.
* Model card content (README) is fetched only on demand and treated as untrusted text.
* Private documents on disk are never sent to HF APIs.
* All network calls have explicit timeouts.
"""

from __future__ import annotations

import os
import time
from typing import Iterator, Optional

from .models import (
    NormalisedRecord,
    ProvenanceEntry,
    SOURCE_HUGGINGFACE,
    TTL_HUGGINGFACE,
)
from .normaliser import normalise
from .cache import cache_get, cache_put, cache_get_by_source, provenance_put

try:
    import requests  # type: ignore
    _REQUESTS_OK = True
except ImportError:
    _REQUESTS_OK = False

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

HF_API_BASE = "https://huggingface.co/api"
DEFAULT_TIMEOUT = 15
DEFAULT_LIMIT = 20
MAX_PAGES = 5
RATE_LIMIT_SLEEP = 30


def _get_token() -> Optional[str]:
    return os.environ.get("HF_TOKEN") or None


def _headers() -> dict[str, str]:
    h = {"User-Agent": "SlothOps-AI/1.0"}
    token = _get_token()
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


# ---------------------------------------------------------------------------
# Pagination (HF uses offset-based pagination)
# ---------------------------------------------------------------------------


def _paginate_hf(
    url: str,
    params: dict,
    timeout: int = DEFAULT_TIMEOUT,
    max_pages: int = MAX_PAGES,
) -> Iterator[tuple[list[dict], int]]:
    """Yield (items, page_number) for each offset page."""
    if not _REQUESTS_OK:
        raise RuntimeError("requests library not installed")

    for page in range(max_pages):
        params["offset"] = page * DEFAULT_LIMIT
        params["limit"] = DEFAULT_LIMIT
        try:
            resp = requests.get(url, headers=_headers(), params=params, timeout=timeout)
        except requests.exceptions.Timeout:
            raise TimeoutError(f"HF API timeout on page {page + 1}")
        except requests.exceptions.RequestException as exc:
            raise RuntimeError(f"HF API request error: {exc}") from exc

        if resp.status_code == 429:
            time.sleep(RATE_LIMIT_SLEEP)
            resp = requests.get(url, headers=_headers(), params=params, timeout=timeout)

        resp.raise_for_status()
        items = resp.json()
        if not isinstance(items, list) or not items:
            break
        yield items, page + 1
        if len(items) < DEFAULT_LIMIT:
            break


# ---------------------------------------------------------------------------
# Normalisation helpers
# ---------------------------------------------------------------------------


def _normalise_model(raw: dict) -> NormalisedRecord:
    model_id = raw.get("modelId") or raw.get("id") or ""
    tags = raw.get("tags") or []
    pipeline = raw.get("pipeline_tag") or ""
    if pipeline and pipeline not in tags:
        tags = [pipeline] + tags
    return normalise(
        source=SOURCE_HUGGINGFACE,
        record_type="hf_model",
        raw_id=model_id,
        title=model_id,
        body=(
            f"Pipeline: {pipeline}\n"
            f"Library: {raw.get('library_name', '')}\n"
            f"Downloads (last month): {raw.get('downloads', 0)}\n"
            f"Likes: {raw.get('likes', 0)}\n"
            f"Private: {raw.get('private', False)}\n"
        ),
        url=f"https://huggingface.co/{model_id}" if model_id else "",
        created_at=raw.get("createdAt"),
        updated_at=raw.get("lastModified"),
        tags=tags[:20],
        author=raw.get("author") or model_id.split("/")[0] if "/" in model_id else "",
        extra={
            "downloads": raw.get("downloads", 0),
            "likes": raw.get("likes", 0),
            "pipeline_tag": pipeline,
            "library_name": raw.get("library_name", ""),
            "private": raw.get("private", False),
        },
        synthetic=False,
    )


def _normalise_dataset(raw: dict) -> NormalisedRecord:
    dataset_id = raw.get("id") or raw.get("datasetId") or ""
    tags = raw.get("tags") or []
    task_cats = raw.get("cardData", {}).get("task_categories") or []
    if isinstance(task_cats, list):
        tags = task_cats + tags
    return normalise(
        source=SOURCE_HUGGINGFACE,
        record_type="hf_dataset",
        raw_id=dataset_id,
        title=dataset_id,
        body=(
            f"Downloads (last month): {raw.get('downloads', 0)}\n"
            f"Likes: {raw.get('likes', 0)}\n"
            f"Size categories: {raw.get('cardData', {}).get('size_categories', 'unknown')}\n"
        ),
        url=f"https://huggingface.co/datasets/{dataset_id}" if dataset_id else "",
        created_at=raw.get("createdAt"),
        updated_at=raw.get("lastModified"),
        tags=tags[:20],
        author=raw.get("author") or (dataset_id.split("/")[0] if "/" in dataset_id else ""),
        extra={
            "downloads": raw.get("downloads", 0),
            "likes": raw.get("likes", 0),
            "private": raw.get("private", False),
        },
        synthetic=False,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def fetch_models(
    search: str = "",
    pipeline_tag: str = "",
    limit_pages: int = 2,
    use_cache: bool = True,
    db_path=None,
) -> tuple[list[NormalisedRecord], list[str]]:
    """
    Fetch public model metadata from Hugging Face Hub.

    Parameters
    ----------
    search : str
        Free-text search term (e.g., "gemma", "bert-base").
    pipeline_tag : str
        Filter by pipeline (e.g., "text-classification").
    limit_pages : int
        Max pages to fetch (safety bound).
    use_cache : bool
        Use cached records if fresh.
    db_path : Path | None
        Override for tests.

    Returns
    -------
    (records, warnings)
    """
    kwargs = {} if db_path is None else {"db_path": db_path}
    warnings: list[str] = []
    records: list[NormalisedRecord] = []

    if not _REQUESTS_OK:
        warnings.append("requests library not installed")
        return records, warnings

    # Cache check
    if use_cache:
        cached = cache_get_by_source(SOURCE_HUGGINGFACE, max_age_seconds=TTL_HUGGINGFACE, **kwargs)
        hf_models = [r for r, _ in cached if r.record_type == "hf_model"]
        if hf_models:
            if search:
                hf_models = [
                    r for r in hf_models
                    if search.lower() in r.title.lower() or
                       any(search.lower() in t.lower() for t in r.tags)
                ]
            stale_any = any(s for _, s in cached)
            if stale_any:
                warnings.append("⚠️ Cached HuggingFace model records are stale. Consider refreshing.")
            if hf_models:
                return hf_models, warnings

    url = f"{HF_API_BASE}/models"
    params: dict = {"sort": "downloads", "direction": -1}
    if search:
        params["search"] = search
    if pipeline_tag:
        params["pipeline_tag"] = pipeline_tag

    try:
        for items, page_num in _paginate_hf(
            url, params, max_pages=min(limit_pages, MAX_PAGES)
        ):
            for raw in items:
                rec = _normalise_model(raw)
                if not rec.is_valid:
                    warnings.append(f"HF model validation errors: {rec.validation_errors}")
                cache_put(rec, TTL_HUGGINGFACE, **kwargs)
                provenance_put(
                    ProvenanceEntry(
                        record_id=rec.display_id,
                        source=SOURCE_HUGGINGFACE,
                        fetch_ts=time.time(),
                        endpoint=url,
                        cache_hit=False,
                        ttl_seconds=TTL_HUGGINGFACE,
                        page=page_num,
                    ),
                    **kwargs,
                )
                records.append(rec)
    except TimeoutError as exc:
        warnings.append(f"HF API timeout: {exc}")
    except RuntimeError as exc:
        warnings.append(f"HF API error: {exc}")
    except Exception as exc:
        warnings.append(f"Unexpected HF error: {exc}")

    return records, warnings


def fetch_datasets(
    search: str = "",
    limit_pages: int = 2,
    use_cache: bool = True,
    db_path=None,
) -> tuple[list[NormalisedRecord], list[str]]:
    """Fetch public dataset metadata from Hugging Face Hub."""
    kwargs = {} if db_path is None else {"db_path": db_path}
    warnings: list[str] = []
    records: list[NormalisedRecord] = []

    if not _REQUESTS_OK:
        warnings.append("requests library not installed")
        return records, warnings

    if use_cache:
        cached = cache_get_by_source(SOURCE_HUGGINGFACE, max_age_seconds=TTL_HUGGINGFACE, **kwargs)
        hf_datasets = [r for r, _ in cached if r.record_type == "hf_dataset"]
        if hf_datasets:
            if search:
                hf_datasets = [
                    r for r in hf_datasets
                    if search.lower() in r.title.lower()
                ]
            if hf_datasets:
                return hf_datasets, warnings

    url = f"{HF_API_BASE}/datasets"
    params: dict = {"sort": "downloads", "direction": -1}
    if search:
        params["search"] = search

    try:
        for items, page_num in _paginate_hf(
            url, params, max_pages=min(limit_pages, MAX_PAGES)
        ):
            for raw in items:
                rec = _normalise_dataset(raw)
                if not rec.is_valid:
                    warnings.append(f"HF dataset validation errors: {rec.validation_errors}")
                cache_put(rec, TTL_HUGGINGFACE, **kwargs)
                provenance_put(
                    ProvenanceEntry(
                        record_id=rec.display_id,
                        source=SOURCE_HUGGINGFACE,
                        fetch_ts=time.time(),
                        endpoint=url,
                        cache_hit=False,
                        ttl_seconds=TTL_HUGGINGFACE,
                        page=page_num,
                    ),
                    **kwargs,
                )
                records.append(rec)
    except TimeoutError as exc:
        warnings.append(f"HF API timeout: {exc}")
    except RuntimeError as exc:
        warnings.append(f"HF API error: {exc}")
    except Exception as exc:
        warnings.append(f"Unexpected HF error: {exc}")

    return records, warnings
