"""Lever — per-company postings API (free, no key)."""

from __future__ import annotations

import httpx

from ..models import Job
from ..util import is_relevant_title
from .base import Provider


class LeverProvider(Provider):
    name = "lever"

    async def fetch(self, client: httpx.AsyncClient) -> list[Job]:
        out: list[Job] = []
        for slug in self.companies:
            try:
                r = await client.get(f"https://api.lever.co/v0/postings/{slug}?mode=json")
                if r.status_code != 200:
                    continue
                postings = r.json()
            except Exception:
                continue

            for p in postings:
                title = p.get("text", "")
                if not is_relevant_title(title):
                    continue
                categories = p.get("categories", {}) or {}
                loc = categories.get("location") or categories.get("allLocations") or ""
                if isinstance(loc, list):
                    loc = loc[0] if loc else ""
                remote = str(categories.get("workplaceType", "")).lower() == "remote"

                out.append(
                    Job(
                        id=f"lever-{slug}-{p.get('id', title)}",
                        title=title,
                        company=p.get("companyName") or slug.title(),
                        location=loc,
                        url=p.get("hostedUrl", ""),
                        description=p.get("additionalPlain") or p.get("descriptionPlain") or "",
                        remote=remote,
                        source="lever",
                        posted_at=p.get("createdAt"),
                    )
                )
        return out
