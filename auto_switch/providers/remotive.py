"""Remotive — free remote-jobs API (no key)."""

from __future__ import annotations

import httpx

from ..models import Job
from ..util import is_relevant_title, strip_html
from .base import Provider


class RemotiveProvider(Provider):
    name = "remotive"

    async def fetch(self, client: httpx.AsyncClient) -> list[Job]:
        out: list[Job] = []
        seen: set[str] = set()
        for term in self.terms:
            try:
                r = await client.get(
                    "https://remotive.com/api/remote-jobs",
                    params={"search": term, "limit": 30},
                )
                if r.status_code != 200:
                    continue
                data = r.json()
            except Exception:
                continue
            for j in data.get("jobs", []):
                title = j.get("title", "")
                if not is_relevant_title(title):
                    continue
                jid = str(j.get("id"))
                if jid in seen:
                    continue
                seen.add(jid)
                out.append(
                    Job(
                        id=f"remotive-{jid}",
                        title=title,
                        company=j.get("company_name", ""),
                        location=j.get("candidate_required_location", "Remote"),
                        url=j.get("url", ""),
                        description=strip_html(j.get("description", "")),
                        remote=True,
                        salary_text=j.get("salary"),
                        source="remotive",
                        posted_at=j.get("publication_date"),
                    )
                )
        return out
