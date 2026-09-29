"""Greenhouse — per-company board API (free, no key)."""

from __future__ import annotations

import asyncio

import httpx

from ..models import Job
from ..util import is_relevant_title, strip_html
from .base import Provider

# Cap detail-page fetches per company to keep aggregate runs fast (the list
# endpoint already has title/location; only a subset needs the full body).
MAX_DETAILS = 6
# Politeness: cap concurrent requests to the Greenhouse API.
CONCURRENCY = 8


class GreenhouseProvider(Provider):
    name = "greenhouse"

    async def _company_listings(self, client: httpx.AsyncClient, slug: str) -> list[dict]:
        r = await client.get(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs")
        if r.status_code != 200:
            return []
        relevant = [
            j for j in r.json().get("jobs", [])
            if is_relevant_title(j.get("title", ""))
        ]
        return relevant[:MAX_DETAILS]

    async def _fill_detail(self, client: httpx.AsyncClient, slug: str, j: dict,
                           sem: asyncio.Semaphore) -> Job:
        title = j.get("title", "")
        loc = j.get("location")
        loc_name = loc.get("name", "") if isinstance(loc, dict) else str(loc or "")
        jid = j.get("id")
        description = ""
        try:
            async with sem:
                d = await client.get(
                    f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs/{jid}"
                )
            if d.status_code == 200:
                description = strip_html(d.json().get("content", ""))
        except Exception:
            pass
        return Job(
            id=f"greenhouse-{slug}-{jid}",
            title=title,
            company=j.get("company_name") or slug.title(),
            location=loc_name,
            url=j.get("absolute_url", ""),
            description=description,
            source="greenhouse",
            posted_at=j.get("updated_at"),
        )

    async def fetch(self, client: httpx.AsyncClient) -> list[Job]:
        sem = asyncio.Semaphore(CONCURRENCY)

        listings: list[tuple[str, list[dict]]] = []
        for slug in self.companies:
            try:
                listings.append((slug, await self._company_listings(client, slug)))
            except Exception:
                continue

        detail_tasks = [
            self._fill_detail(client, slug, j, sem)
            for slug, jobs in listings for j in jobs
        ]
        return list(await asyncio.gather(*detail_tasks))
