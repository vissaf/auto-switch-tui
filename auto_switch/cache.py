"""Fetch cache: reuse a recent fetch so repeated runs don't re-hit job APIs.

Cache files live under ``~/.cache/auto-switch/`` and are keyed by a hash of
everything that affects the fetch: target locations, search terms, enabled
providers, JobSpy tuning, and company slugs. Lifetime comes from
``cache.ttl_minutes`` (default 30, set in onboarding); ``--no-cache`` disables
read and write, ``--cache-ttl N`` overrides the lifetime.

Only raw fetched jobs are cached — ranking and filtering still run fresh, so a
cached hit is cheap and stays correct.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Optional

from .models import Job

CACHE_DIR = Path.home() / ".cache" / "auto-switch"

DEFAULT_TTL_MINUTES = 30


def _cache_key(cfg: dict) -> str:
    subset = {
        "locations": cfg.get("locations"),
        "search_terms": cfg.get("search_terms"),
        "providers": cfg.get("providers"),
        "jobspy": cfg.get("jobspy"),
        "companies": cfg.get("companies"),
    }
    raw = json.dumps(subset, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def cache_file(cfg: dict) -> Path:
    return CACHE_DIR / f"fetch-{_cache_key(cfg)}.json"


def ttl_minutes(cfg: dict) -> int:
    value = (cfg.get("cache") or {}).get("ttl_minutes")
    return int(value) if value is not None else DEFAULT_TTL_MINUTES


def load(cfg: dict) -> Optional[tuple[list[Job], float]]:
    """Return (jobs, age_minutes) on a fresh hit, else None."""
    if (cfg.get("cache") or {}).get("disabled"):
        return None
    path = cache_file(cfg)
    if not path.exists():
        return None
    age = (time.time() - path.stat().st_mtime) / 60.0
    if age > ttl_minutes(cfg):
        return None
    try:
        jobs = [Job.from_dict(d) for d in json.loads(path.read_text(encoding="utf-8"))]
    except Exception:
        return None
    return jobs, age


def save(cfg: dict, jobs: list[Job]) -> None:
    if (cfg.get("cache") or {}).get("disabled"):
        return
    path = cache_file(cfg)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([j.to_dict() for j in jobs]), encoding="utf-8")


def clear() -> None:
    if CACHE_DIR.exists():
        for f in CACHE_DIR.glob("fetch-*.json"):
            f.unlink(missing_ok=True)
