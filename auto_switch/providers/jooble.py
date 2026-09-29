"""Jooble — optional API-key provider with location + keyword search."""

from __future__ import annotations

import httpx

from ..models import Job
from ..util import strip_html
from .base import Provider


class JoobleProvider(Provider):
    name = "jooble"

    async def fetch(self, client: httpx.AsyncClient) -> list[Job]:
        key = self.keys.get("jooble")
        if not key:
            return []

        out: list[Job] = []
        locations = self.cfg.get("locations") or [""]
        for loc in locations:
            for term in self.terms[:2]:
                try:
                    r = await client.post(
                        f"https://jooble.org/api/{key}",
                        json={"keywords": term, "location": loc, "page": "1"},
                    )
                    if r.status_code != 200:
                        continue
                    jobs = r.json().get("jobs", [])
                except Exception:
                    continue
                for j in jobs:
                    out.append(
                        Job(
                            id=f"jooble-{j.get('id')}",
                            title=j.get("title", ""),
                            company=j.get("company", ""),
                            location=j.get("location", ""),
                            url=j.get("link", ""),
                            description=strip_html(j.get("snippet", "")),
                            salary_text=j.get("salary") or None,
                            source="jooble",
                            posted_at=j.get("updated"),
                        )
                    )
        return out
