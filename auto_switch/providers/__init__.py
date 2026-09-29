"""Provider registry + concurrent aggregation."""

from __future__ import annotations

import asyncio
from typing import Callable, Optional

import httpx

from ..models import Job
from ..util import parse_salary
from .adzuna import AdzunaProvider
from .ashby import AshbyProvider
from .base import BROWSER_HEADERS, Provider
from .bayt import BaytProvider
from .google_serpapi import GoogleSerpApiProvider
from .greenhouse import GreenhouseProvider
from .instahyre import InstahyreProvider
from .jooble import JoobleProvider
from .jobspy import JOBSPY_SITES, make_jobspy_provider
from .lever import LeverProvider
from .remotive import RemotiveProvider

REGISTRY: dict[str, type[Provider]] = {
    "remotive": RemotiveProvider,
    "greenhouse": GreenhouseProvider,
    "lever": LeverProvider,
    "ashby": AshbyProvider,
    "adzuna": AdzunaProvider,
    "jooble": JoobleProvider,
    "bayt": BaytProvider,
    "instahyre": InstahyreProvider,
    "google": GoogleSerpApiProvider,
    **{name: make_jobspy_provider(name) for name in JOBSPY_SITES},
}


def build_providers(cfg: dict) -> list[Provider]:
    enabled = cfg.get("providers", {})
    return [cls(cfg) for name, cls in REGISTRY.items() if enabled.get(name, False)]


def _enrich_salary(job: Job) -> None:
    """Parse a provider-supplied salary string into numeric fields.

    Deliberately does NOT guess a salary from the job description — salaries
    are only shown when a listing actually provides one.
    """
    if job.salary_min is None and job.salary_text:
        parsed = parse_salary(job.salary_text)
        if parsed:
            _apply(job, parsed)


def _apply(job: Job, parsed: dict) -> None:
    job.salary_min = parsed["min"]
    job.salary_max = parsed["max"]
    job.salary_currency = parsed["currency"]
    job.salary_annual_usd = parsed["annual_usd"]
    if not job.salary_text:
        job.salary_text = parsed["text"]


def _dedupe(jobs: list[Job]) -> list[Job]:
    jobs.sort(key=lambda j: len(j.description), reverse=True)
    seen: dict[tuple[str, str], Job] = {}
    for j in jobs:
        key = (j.title.lower().strip(), j.company.lower().strip())
        if key not in seen:
            seen[key] = j
    return list(seen.values())


# progress callback signature: progress(provider_name, status, count, error)
#   status in {"ok", "error"}; error is an Exception (or None).
ProgressCb = Callable[[Optional[str], str, int, Optional[Exception]], None]


async def _run_one(p: Provider, client: httpx.AsyncClient) -> tuple:
    """Run one provider, swallowing errors so a single failure can't abort the run."""
    try:
        result = await p.fetch(client)
        return p.name, "ok", len(result), None, result
    except Exception as exc:  # noqa: BLE001
        return p.name, "error", 0, exc, []


async def aggregate(cfg: dict, progress: Optional[ProgressCb] = None) -> list[Job]:
    """Fetch from all enabled providers concurrently, enrich and dedupe.

    Each provider runs as an independent task; as each finishes the `progress`
    callback fires once with its name, status, job count, and any error. Errors
    in one provider never stop the others.
    """
    providers = build_providers(cfg)
    if not providers:
        if progress:
            progress(None, "noproviders", 0, None)
        return []

    jobs: list[Job] = []
    async with httpx.AsyncClient(
        timeout=12, follow_redirects=True, headers=BROWSER_HEADERS
    ) as client:
        coros = [_run_one(p, client) for p in providers]
        for done in asyncio.as_completed(coros):
            name, status, count, error, result = await done
            if progress:
                progress(name, status, count, error)
            jobs.extend(result)

    jobs = _dedupe(jobs)
    for j in jobs:
        _enrich_salary(j)
    return jobs
