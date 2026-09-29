"""Bayt.com — Gulf / Middle East / India job board (HTML scraping, no key).

Bayt is server-rendered and returns job cards (title, company, location,
summary, posted date) plus a JSON-LD JobPosting block on each detail page.

Bayt's CDN blocks Python's TLS fingerprint (httpx/requests return 403) while
accepting curl, so this provider fetches through a `curl` subprocess run in a
worker thread. This is the pragmatic, working path for a bot-hostile board —
and why it is isolated in this module.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import json
import re
import shutil
import subprocess
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..models import Job
from ..util import is_relevant_title, slugify, strip_html
from .base import Provider

BASE = "https://www.bayt.com"

BAYT_COUNTRIES_GULF = ["uae", "saudi-arabia", "qatar", "kuwait", "bahrain", "oman"]

# Cap detail-page fetches across the whole run (only for relevant titles).
MAX_DETAILS = 8
# Politeness: cap concurrent requests to Bayt.
CONCURRENCY = 6

CURL_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
_STATUS_SEP = "\n__CURL_STATUS__"


def _curl_get(url: str, timeout: int = 30) -> str | None:
    """Fetch a URL via curl (browser-like TLS fingerprint). Returns body or None."""
    if not shutil.which("curl"):
        return None
    for _ in range(2):
        proc = subprocess.run(
            [
                "curl", "-sL", "--http1.1", "--compressed",
                "-A", CURL_UA,
                "-H", "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "-H", "Accept-Language: en-US,en;q=0.9",
                "-w", f"{_STATUS_SEP}%{{http_code}}",
                "--max-time", str(timeout),
                url,
            ],
            capture_output=True, text=True,
        )
        out = proc.stdout or ""
        if _STATUS_SEP in out:
            body, status = out.rsplit(_STATUS_SEP, 1)
        else:
            body, status = out, "0"
        if status.strip() == "200" and body.strip():
            return body
    return None


class BaytProvider(Provider):
    name = "bayt"

    def _countries(self) -> list[str]:
        from ..locations import resolve

        targets = resolve(self.cfg.get("locations", []))
        out = []
        if targets.uae:
            out.append("uae")
        if targets.india:
            out.append("india")
        for loc in targets.explicit:
            slug = loc.replace(" ", "-")
            if slug in BAYT_COUNTRIES_GULF and slug not in out:
                out.append(slug)
        return out

    async def fetch(self, client) -> list[Job]:
        countries = self._countries()
        if not countries:
            return []

        sem = asyncio.Semaphore(CONCURRENCY)

        async def get_list(country: str, term: str) -> list[Job]:
            slug = slugify(term) + "-jobs"
            url = f"{BASE}/en/{country}/jobs/{slug}/"
            async with sem:
                html = await asyncio.to_thread(_curl_get, url)
                return self._parse_list(html or "")

        pages = [(c, t) for c in countries for t in self.terms[:1]]
        results = await asyncio.gather(*[get_list(c, t) for c, t in pages])

        jobs: dict[str, Job] = {}
        for lst in results:
            for j in lst:
                jobs.setdefault(j.id, j)
        result = list(jobs.values())

        # Enrich the most relevant titles with full descriptions (concurrently).
        relevant = [j for j in result if is_relevant_title(j.title)][:MAX_DETAILS]
        await asyncio.gather(*[self._fill_detail(j, sem) for j in relevant])
        return result

    def _parse_list(self, html: str) -> list[Job]:
        soup = BeautifulSoup(html, "lxml")
        out: list[Job] = []
        for card in soup.select("li[data-job-id]"):
            jid = card.get("data-job-id")
            h2 = card.select_one("h2")
            title = h2.get_text(" ", strip=True) if h2 else ""
            if not title:
                continue

            a = card.select_one('a[href*="/jobs/"]')
            url = urljoin(BASE, a["href"]) if a and a.get("href") else ""
            if not url:
                continue

            comp = card.select_one("div.job-company-location-wrapper")
            company = comp.get_text(" ", strip=True) if comp else ""

            loc_parts = [x.get_text(" ", strip=True) for x in card.select("dt.jb-label-location a")]
            location = " ".join(part for part in loc_parts if part)

            desc = card.select_one(".jb-descr")
            desc = desc.get_text(" ", strip=True) if desc else ""
            desc = re.sub(r"^Summary:\s*", "", desc)

            date_el = card.select_one(".jb-date")
            posted = date_el.get_text(" ", strip=True) if date_el else ""
            remote = bool(card.select_one("dt.jb-label-remote"))

            out.append(
                Job(
                    id=f"bayt-{jid}",
                    title=title,
                    company=company,
                    location=location,
                    url=url,
                    description=desc,
                    remote=remote,
                    source="bayt",
                    posted_at=_relative_to_date(posted),
                )
            )
        return out

    async def _fill_detail(self, job: Job, sem: asyncio.Semaphore) -> None:
        async with sem:
            html = await asyncio.to_thread(_curl_get, job.url)
            if not html:
                return
            soup = BeautifulSoup(html, "lxml")
            for s in soup.find_all("script", type="application/ld+json"):
                try:
                    d = json.loads(s.string or "")
                except Exception:
                    continue
                if isinstance(d, dict) and d.get("@type") == "JobPosting":
                    if d.get("description"):
                        job.description = strip_html(d["description"])
                    if d.get("datePosted"):
                        job.posted_at = d["datePosted"]
                    if d.get("baseSalary"):
                        job.salary_text = _salary_text(d["baseSalary"])
                    return


def _salary_text(base_salary) -> str | None:
    if not isinstance(base_salary, dict):
        return None
    value = base_salary.get("value") or {}
    lo = value.get("minValue") if isinstance(value, dict) else None
    hi = value.get("maxValue") if isinstance(value, dict) else None
    cur = value.get("currency") if isinstance(value, dict) else None
    if lo is None and hi is None:
        return None
    cur = cur or ""
    if lo and hi and lo != hi:
        return f"{cur} {lo} – {hi}"
    return f"{cur} {hi or lo}"


def _relative_to_date(text: str) -> str | None:
    m = re.search(r"(\d+)\+?\s+(hour|day|week|month)s?\s+ago", text or "")
    if not m:
        return None
    n = int(m.group(1))
    unit = m.group(2)
    now = dt.datetime.now(dt.timezone.utc)
    if unit == "hour":
        delta = dt.timedelta(hours=n)
    elif unit == "day":
        delta = dt.timedelta(days=n)
    elif unit == "week":
        delta = dt.timedelta(weeks=n)
    else:
        delta = dt.timedelta(days=n * 30)
    return (now - delta).strftime("%Y-%m-%d")
