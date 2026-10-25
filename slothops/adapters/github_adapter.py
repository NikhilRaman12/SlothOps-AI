"""
slothops/adapters/github_adapter.py
Fetches public GitHub issues and pull-requests via the REST API.

Security
--------
* API responses are UNTRUSTED — all fields normalised before use.
* Embedded instructions in issue/PR bodies are never executed.
* Private documents on disk are never sent to GitHub's API.
* Token is optional (raises rate-limit to 5000 req/hr). Stored in .env only.
* All network calls have explicit timeouts.
* Pagination is bounded by max_pages to prevent runaway fetches.
"""

from __future__ import annotations

import os
import time
import urllib.parse
from typing import Any, Iterator, Optional

from .models import (
    NormalisedRecord,
    ProvenanceEntry,
    SOURCE_GITHUB,
    TTL_GITHUB,
)
from .normaliser import normalise
from .cache import cache_get, cache_put, provenance_put

try:
    import requests  # type: ignore
    _REQUESTS_OK = True
except ImportError:
    _REQUESTS_OK = False

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

GITHUB_API_BASE = "https://api.github.com"
DEFAULT_TIMEOUT = 15          # seconds
DEFAULT_PER_PAGE = 30
MAX_PAGES = 10                # safety bound
RATE_LIMIT_SLEEP = 60         # seconds to sleep on 403/429


def _get_token() -> Optional[str]:
    """Read GITHUB_TOKEN from env (never hardcoded)."""
    return os.environ.get("GITHUB_TOKEN") or None


def _headers() -> dict[str, str]:
    h = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "SlothOps-AI/1.0",
    }
    token = _get_token()
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


# ---------------------------------------------------------------------------
# Pagination helper
# ---------------------------------------------------------------------------


def _paginate(
    url: str,
    params: dict,
    timeout: int = DEFAULT_TIMEOUT,
    max_pages: int = MAX_PAGES,
) -> Iterator[tuple[list[dict], int, bool]]:
    """
    Yield (items, page_number, is_last_page) for each page.
    Handles 429/403 rate limits with a single retry after sleep.
    """
    if not _REQUESTS_OK:
        raise RuntimeError("requests library not installed")

    page = 1
    while page <= max_pages:
        params["page"] = page
        params["per_page"] = DEFAULT_PER_PAGE

        try:
            resp = requests.get(
                url,
                headers=_headers(),
                params=params,
                timeout=timeout,
            )
        except requests.exceptions.Timeout:
            raise TimeoutError(f"GitHub API timeout on page {page}")
        except requests.exceptions.RequestException as exc:
            raise RuntimeError(f"GitHub API request error: {exc}") from exc

        if resp.status_code in (403, 429):
            retry_after = int(resp.headers.get("Retry-After", RATE_LIMIT_SLEEP))
            time.sleep(min(retry_after, RATE_LIMIT_SLEEP))
            # Single retry
            try:
                resp = requests.get(
                    url, headers=_headers(), params=params, timeout=timeout
                )
            except Exception as exc:
                raise RuntimeError(f"GitHub API failed after rate-limit retry: {exc}") from exc

        resp.raise_for_status()
        items = resp.json()
        if not isinstance(items, list):
            break

        link_header = resp.headers.get("Link", "")
        has_next = 'rel="next"' in link_header
        yield items, page, not has_next

        if not has_next or not items:
            break
        page += 1


# ---------------------------------------------------------------------------
# Normalisation
# ---------------------------------------------------------------------------


def _normalise_issue(raw: dict, repo: str) -> NormalisedRecord:
    is_pr = "pull_request" in raw
    rtype = "github_pr" if is_pr else "github_issue"
    raw_id = f"{repo}#{raw.get('number', 'unknown')}"
    return normalise(
        source=SOURCE_GITHUB,
        record_type=rtype,
        raw_id=raw_id,
        title=raw.get("title", ""),
        body=raw.get("body") or "",
        url=raw.get("html_url", ""),
        created_at=raw.get("created_at"),
        updated_at=raw.get("updated_at"),
        tags=[lbl.get("name", "") for lbl in (raw.get("labels") or [])],
        author=(raw.get("user") or {}).get("login", ""),
        extra={
            "state": raw.get("state", ""),
            "comments": raw.get("comments", 0),
            "repo": repo,
            "number": raw.get("number"),
        },
        synthetic=False,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def fetch_repo_issues(
    owner: str,
    repo: str,
    state: str = "open",
    max_pages: int = 3,
    use_cache: bool = True,
    db_path=None,
) -> tuple[list[NormalisedRecord], list[str]]:
    """
    Fetch public issues (and PRs) from a GitHub repository.

    Parameters
    ----------
    owner, repo : str
        e.g. "python", "cpython"
    state : str
        "open" | "closed" | "all"
    max_pages : int
        Safety bound on pagination (max MAX_PAGES).
    use_cache : bool
        Return cached records without hitting the API if fresh.
    db_path : Path | None
        Override DB path (for tests).

    Returns
    -------
    (records, warnings)
    """
    kwargs = {} if db_path is None else {"db_path": db_path}
    warnings: list[str] = []
    records: list[NormalisedRecord] = []
    max_pages = min(max_pages, MAX_PAGES)

    if not _REQUESTS_OK:
        warnings.append("requests library not installed — cannot fetch from GitHub")
        return records, warnings

    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/issues"
    params = {"state": state, "filter": "all"}

    # Check cache for first-page items (rough cache key)
    if use_cache:
        cache_key = f"{SOURCE_GITHUB}:{owner}/{repo}#{state}-p1"
        rec, is_stale = cache_get(cache_key, **kwargs)
        if rec is not None:
            # Cache exists — pull all for this repo from cache
            from .cache import cache_get_by_source
            all_cached = cache_get_by_source(SOURCE_GITHUB, **kwargs)
            repo_records = [
                r for r, stale in all_cached
                if r.extra.get("repo") == f"{owner}/{repo}"
                and r.extra.get("state") == state
            ]
            if repo_records:
                if any(s for _, s in all_cached if s):
                    warnings.append(
                        f"⚠️ Cached GitHub records for {owner}/{repo} are stale (TTL expired). "
                        "Consider refreshing."
                    )
                return repo_records, warnings

    try:
        for items, page_num, is_last in _paginate(
            url, params, max_pages=max_pages
        ):
            for raw in items:
                rec = _normalise_issue(raw, f"{owner}/{repo}")
                if not rec.is_valid:
                    warnings.append(
                        f"Validation errors for issue {rec.raw_id}: "
                        + "; ".join(rec.validation_errors)
                    )
                cache_put(rec, TTL_GITHUB, **kwargs)
                prov = ProvenanceEntry(
                    record_id=rec.display_id,
                    source=SOURCE_GITHUB,
                    fetch_ts=time.time(),
                    endpoint=url,
                    cache_hit=False,
                    ttl_seconds=TTL_GITHUB,
                    page=page_num,
                )
                provenance_put(prov, **kwargs)
                records.append(rec)

    except TimeoutError as exc:
        warnings.append(f"GitHub API timeout: {exc}")
    except RuntimeError as exc:
        warnings.append(f"GitHub API error: {exc}")
    except Exception as exc:
        warnings.append(f"Unexpected GitHub error: {exc}")

    return records, warnings
