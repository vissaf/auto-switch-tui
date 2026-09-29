"""Google Jobs via SerpApi (config ``api_keys.serpapi``).

JobSpy's direct Google scraper is routinely IP-blocked without residential
proxies (it returns empty result sets). SerpApi's ``google_jobs`` engine is the
reliable path and needs a SerpApi key (serpapi.com — 100 free searches/month).
Without a key the provider is a fast no-op with a one-line hint.
"""

from __future__ import annotations

import asyncio
import hashlib

import httpx

from ..models import Job
from .base import Provider
from .jobspy import MAX_TERMS_PER_RUN

BASE = "https://serpapi.com/search.json"

_CONCURRENCY = 3


class GoogleSerpApiProvider(Provider):
    name = "google"

    def __init__(self, cfg: dict):
        super().__init__(cfg)
        self.key = (cfg.get("api_keys") or {}).get("serpapi") or ""
        js = cfg.get("jobspy") or {}
        self.max_calls = int(js.get("max_calls") or 16)
        self.google_search_terms = js.get("google_search_terms") or []
        self._hinted = False

    def _queries(self) -> list[tuple[str, str | None]]:
        """(query, location) pairs, capped at max_calls."""
        from ..locations import resolve

        if self.google_search_terms:
            return [(q, None) for q in self.google_search_terms[: self.max_calls]]

        targets = resolve(self.cfg.get("locations") or [])
        loc_labels: list[str | None] = [raw.strip() for raw in (targets.explicit or [])]
        for flag, label in (
            (targets.uae, "United Arab Emirates"),
            (targets.india, "India"),
            (targets.usa, "USA"),
            (targets.canada, "Canada"),
            (targets.uk, "UK"),
        ):
            if flag:
                loc_labels.append(label)
        if targets.eu:
            loc_labels += ["Germany", "Netherlands", "Ireland", "France"]
        if not loc_labels:
            loc_labels = [None]

        queries: list[tuple[str, str | None]] = []
        for term in self.terms[:MAX_TERMS_PER_RUN]:
            for loc in loc_labels:
                queries.append((term, loc))
        return queries[: self.max_calls]

    def _parse(self, data: dict) -> list[Job]:
        out: list[Job] = []
        for j in data.get("jobs_results") or []:
            title = (j.get("title") or "").strip()
            company = (j.get("company_name") or "").strip()
            if not title or not company:
                continue
            url = j.get("share_link") or ""
            related = j.get("related_links") or []
            if not url and related:
                url = related[0].get("link") or ""
            ext = j.get("detected_extensions") or {}
            schedule = (ext.get("schedule_type") or "").lower()
            native_id = j.get("job_id") or url or f"{company}-{title}"
            out.append(
                Job(
                    id=f"google-{hashlib.sha1(str(native_id).encode()).hexdigest()[:12]}",
                    title=title,
                    company=company,
                    location=j.get("location") or "",
                    url=url,
                    description=j.get("description") or "",
                    remote="remote" in schedule,
                    salary_text=ext.get("salary") or "",
                    source="google",
                )
            )
        return out

    async def _one(self, client: httpx.AsyncClient, query: str, loc: str | None,
                   sem: asyncio.Semaphore) -> list[Job]:
        params: dict = {"engine": "google_jobs", "api_key": self.key}
        if query:
            params["q"] = query
        if loc:
            params["location"] = loc
        try:
            async with sem:
                r = await client.get(BASE, params=params)
            if r.status_code != 200:
                return []
            return self._parse(r.json())
        except Exception:
            return []

    async def fetch(self, client: httpx.AsyncClient) -> list[Job]:
        if not self.key:
            if not self._hinted:
                self._hinted = True
                print(
                    "  ! google: no api_keys.serpapi in ~/.config/auto-switch/config.json "
                    "— add one (serpapi.com, 100 free searches/month) for Google Jobs results."
                )
            return []
        sem = asyncio.Semaphore(_CONCURRENCY)
        results = await asyncio.gather(*[self._one(client, query, loc, sem) for query, loc in self._queries()])
        jobs: dict[str, Job] = {}
        for lst in results:
            for j in lst:
                jobs.setdefault(j.id, j)
        return list(jobs.values())
