"""Ashby — per-company job-board API (free, no key; includes compensation)."""

from __future__ import annotations

import httpx

from ..models import Job
from ..util import is_relevant_title, strip_html
from .base import Provider


class AshbyProvider(Provider):
    name = "ashby"

    async def fetch(self, client: httpx.AsyncClient) -> list[Job]:
        out: list[Job] = []
        for slug in self.companies:
            try:
                r = await client.get(
                    f"https://api.ashbyhq.com/posting-api/job-board/{slug}",
                    params={"includeCompensation": "true"},
                )
                if r.status_code != 200:
                    continue
                listings = r.json().get("jobs", [])
            except Exception:
                continue

            for j in listings:
                title = j.get("title", "")
                if not is_relevant_title(title):
                    continue

                comp = j.get("compensation") or {}
                salary_text = (
                    comp.get("compensationTierSummary")
                    or comp.get("scrapeableCompensationSalarySummary")
                )

                out.append(
                    Job(
                        id=f"ashby-{slug}-{j.get('id')}",
                        title=title,
                        company=slug.title(),
                        location=j.get("location", "") or "Remote",
                        url=j.get("jobUrl", ""),
                        description=strip_html(j.get("descriptionHtml") or j.get("descriptionPlain") or ""),
                        remote=bool(j.get("isRemote")),
                        salary_text=salary_text,
                        source="ashby",
                        posted_at=j.get("publishedAt"),
                    )
                )
        return out
