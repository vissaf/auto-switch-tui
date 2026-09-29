"""Instahyre — India & Remote tech job board (REST API + JSON-LD enrichment).

Provides direct access to product and startup engineering roles across India's
tech hubs (Bengaluru, Gurgaon/NCR, Hyderabad, Pune, Mumbai, Chennai, etc.) and
remote positions via Instahyre's public search API and job detail pages.
"""

from __future__ import annotations

import asyncio
import json
import re
from typing import Optional

import httpx
from bs4 import BeautifulSoup

from ..locations import resolve
from ..models import Job
from ..util import is_relevant_title
from .base import BROWSER_HEADERS, Provider

SEARCH_API = "https://www.instahyre.com/api/v1/job_search"
PUBLIC_JOB_API = "https://www.instahyre.com/api/v1/employer_public_jobs/{}"

# Common city names mapped to Instahyre's canonical filter values.
INSTAHYRE_CITY_MAP: dict[str, str] = {
    "bangalore": "Bangalore",
    "bengaluru": "Bangalore",
    "delhi": "Delhi",
    "new delhi": "Delhi",
    "ncr": "Delhi",
    "gurgaon": "Gurgaon",
    "gurugram": "Gurgaon",
    "noida": "Noida",
    "mumbai": "Mumbai",
    "pune": "Pune",
    "hyderabad": "Hyderabad",
    "chennai": "Chennai",
    "chandigarh": "Chandigarh",
    "mohali": "Chandigarh",
    "panchkula": "Chandigarh",
    "ahmedabad": "Ahmedabad",
    "kolkata": "Kolkata",
    "remote": "Work From Home",
    "work from home": "Work From Home",
    "wfh": "Work From Home",
}

MAX_TERMS = 3
MAX_DETAILS = 60
CONCURRENCY = 10


class InstahyreProvider(Provider):
    name = "instahyre"

    def _target_locations(self) -> list[str]:
        raw_locs = self.cfg.get("locations", [])
        targets = resolve(raw_locs)

        # If user active filter does NOT include India or Remote, skip Instahyre.
        if targets.active and not targets.india and not targets.remote:
            has_indian_city = any(
                loc.strip().lower() in INSTAHYRE_CITY_MAP for loc in raw_locs
            )
            if not has_indian_city:
                return []

        # If no active filter is set, search all India.
        if not targets.active:
            return ["Anywhere in India"]

        cities: list[str] = []
        for loc in raw_locs:
            norm = loc.strip().lower()
            mapped = INSTAHYRE_CITY_MAP.get(norm)
            if mapped and mapped not in cities:
                cities.append(mapped)

        has_specific_indian_city = any(
            c in cities for c in INSTAHYRE_CITY_MAP.values() if c != "Work From Home"
        )
        if targets.india and not has_specific_indian_city and "Anywhere in India" not in cities:
            cities.append("Anywhere in India")

        if targets.remote and "Work From Home" not in cities:
            cities.append("Work From Home")

        return cities or ["Anywhere in India"]

    async def fetch(self, client: httpx.AsyncClient) -> list[Job]:
        locations = self._target_locations()
        if not locations:
            return []

        sem = asyncio.Semaphore(CONCURRENCY)
        terms = self.terms[:MAX_TERMS] if self.terms else ["frontend engineer"]
        company_filter = self.companies

        queries: list[dict] = []
        for loc in locations:
            if company_filter:
                for comp in company_filter:
                    queries.append({"jobLocations": loc, "companies": comp, "offset": 0})
            else:
                for term in terms:
                    queries.append({"skills": term, "jobLocations": loc, "offset": 0})

        async def fetch_page(params: dict) -> list[Job]:
            try:
                r = await client.get(
                    SEARCH_API,
                    params=params,
                    headers=BROWSER_HEADERS,
                    timeout=15,
                )
                if r.status_code != 200:
                    return []
                data = r.json()
                return self._parse_jobs(data.get("objects", []))
            except Exception:
                return []

        pages = await asyncio.gather(*[fetch_page(q) for q in queries])

        jobs_map: dict[str, Job] = {}
        for job_list in pages:
            for job in job_list:
                jobs_map.setdefault(job.id, job)
        results = list(jobs_map.values())

        # Concurrently enrich top relevant jobs with full JSON-LD descriptions.
        relevant = [j for j in results if is_relevant_title(j.title)][:MAX_DETAILS]
        await asyncio.gather(*[self._fill_detail(j, client, sem) for j in relevant])

        return results

    def _parse_jobs(self, objects: list[dict]) -> list[Job]:
        out: list[Job] = []
        for j in objects:
            jid = str(j.get("id", ""))
            if not jid:
                continue
            title = j.get("title") or j.get("candidate_title") or ""
            if not title:
                continue

            employer = j.get("employer") or {}
            company = employer.get("company_name") or ""
            location = j.get("locations") or ""
            url = j.get("public_url") or ""
            keywords = j.get("keywords") or []
            note = (employer.get("instahyre_note") or "").strip()

            desc_parts: list[str] = []
            if note:
                desc_parts.append(note)
            if keywords:
                desc_parts.append(f"Required Skills: {', '.join(keywords)}")
            description = "\n\n".join(desc_parts)

            loc_lower = location.lower()
            remote = "work from home" in loc_lower or "remote" in loc_lower

            out.append(
                Job(
                    id=f"instahyre-{jid}",
                    title=title,
                    company=company,
                    location=location,
                    url=url,
                    description=description,
                    remote=remote,
                    source="instahyre",
                )
            )
        return out

    async def _fill_detail(
        self, job: Job, client: httpx.AsyncClient, sem: asyncio.Semaphore
    ) -> None:
        if not job.url and not job.id:
            return
        async with sem:
            jid = _extract_job_id(job)
            company_note = _extract_company_note(job.description)
            existing_keywords = _extract_existing_keywords(job.description)

            # 1. Primary: Try direct REST API endpoint (fast, lightweight, structured)
            if jid:
                try:
                    api_url = PUBLIC_JOB_API.format(jid)
                    r = await client.get(api_url, headers=BROWSER_HEADERS, timeout=15)
                    if r.status_code == 200:
                        data = r.json()
                        desc_html = data.get("description") or ""
                        desc_text = _clean_html_description(desc_html)
                        keywords = data.get("keywords") or existing_keywords
                        workex_min = data.get("workex_min")
                        workex_max = data.get("workex_max")
                        company = data.get("hiring_company_name") or job.company or ""

                        job.description = _build_enriched_description(
                            desc_text=desc_text,
                            workex_min=workex_min,
                            workex_max=workex_max,
                            keywords=keywords,
                            company=company,
                            company_note=company_note,
                        )
                        return
                except Exception:
                    pass

            # 2. Secondary fallback: HTML JSON-LD scraping
            if not job.url:
                return
            try:
                r = await client.get(job.url, headers=BROWSER_HEADERS, timeout=15)
                if r.status_code != 200:
                    return
                soup = BeautifulSoup(r.text, "lxml")
                for s in soup.find_all("script", type="application/ld+json"):
                    try:
                        data = json.loads(s.string or "")
                    except Exception:
                        continue

                    postings = (
                        data if isinstance(data, list)
                        else data.get("@graph", [data]) if isinstance(data, dict)
                        else []
                    )
                    for item in postings:
                        if isinstance(item, dict) and item.get("@type") == "JobPosting":
                            if item.get("description"):
                                desc_text = _clean_html_description(item["description"])
                                job.description = _build_enriched_description(
                                    desc_text=desc_text,
                                    keywords=existing_keywords,
                                    company=job.company,
                                    company_note=company_note,
                                )
                            if item.get("datePosted"):
                                job.posted_at = str(item["datePosted"])
                            if item.get("baseSalary"):
                                job.salary_text = _format_salary(item["baseSalary"])
                            return
            except Exception:
                pass


def _clean_html_description(html_str: str) -> str:
    """Format HTML job description into clean, readable text preserving bullets."""
    if not html_str:
        return ""
    soup = BeautifulSoup(html_str, "lxml")
    for li in soup.find_all("li"):
        li.insert_before("\n• ")
    for block in soup.find_all(["p", "div", "br", "h1", "h2", "h3", "h4"]):
        block.append("\n")
    text = soup.get_text()
    cleaned_lines: list[str] = []
    for line in text.splitlines():
        line_s = line.strip()
        if line_s:
            cleaned_lines.append(line_s)
    return "\n".join(cleaned_lines)


def _extract_job_id(job: Job) -> Optional[str]:
    """Extract numeric job ID from job.id (instahyre-<id>) or job.url."""
    if job.id and job.id.startswith("instahyre-"):
        cand = job.id[len("instahyre-"):].strip()
        if cand.isdigit():
            return cand
    if job.url:
        m = re.search(r"/job-(\d+)", job.url)
        if m:
            return m.group(1)
    return None


def _format_workex(workex_min: Optional[int], workex_max: Optional[int]) -> Optional[str]:
    """Format work experience range nicely."""
    if workex_min is not None and workex_max is not None:
        if workex_min == workex_max:
            return f"{workex_min} Years" if workex_min != 1 else "1 Year"
        return f"{workex_min} – {workex_max} Years"
    if workex_min is not None:
        return f"{workex_min}+ Years"
    if workex_max is not None:
        return f"Up to {workex_max} Years"
    return None


def _extract_company_note(existing_desc: str) -> str:
    """Extract the company overview note from a teaser description."""
    if not existing_desc:
        return ""
    if "Required Skills:" in existing_desc:
        return existing_desc.split("Required Skills:")[0].strip()
    return existing_desc.strip()


def _extract_existing_keywords(existing_desc: str) -> list[str]:
    """Extract required skills keywords from a teaser description."""
    if not existing_desc or "Required Skills:" not in existing_desc:
        return []
    part = existing_desc.split("Required Skills:")[1].strip()
    return [k.strip() for k in part.split(",") if k.strip()]


def _build_enriched_description(
    desc_text: str,
    workex_min: Optional[int] = None,
    workex_max: Optional[int] = None,
    keywords: Optional[list[str]] = None,
    company: str = "",
    company_note: str = "",
) -> str:
    """Assemble a structured ATS-friendly job description."""
    sections: list[str] = []
    if desc_text:
        sections.append(desc_text)
    workex_str = _format_workex(workex_min, workex_max)
    if workex_str:
        sections.append(f"Experience Required: {workex_str}")
    if keywords:
        sections.append(f"Required Skills: {', '.join(keywords)}")
    if company_note and company_note not in desc_text:
        header = f"About {company}:" if company else "About the Company:"
        sections.append(f"{header}\n{company_note}")
    return "\n\n".join(sections).strip()


async def enrich_instahyre_job(job: Job, client: Optional[httpx.AsyncClient] = None) -> bool:
    """Enrich an Instahyre job with full details on-demand."""
    if not job or job.source != "instahyre":
        return False
    if len(job.description or "") > 500 and (
        "Responsibilities" in job.description or "Experience Required:" in job.description
    ):
        return True

    sem = asyncio.Semaphore(1)
    provider = InstahyreProvider({})
    if client is not None:
        await provider._fill_detail(job, client, sem)
        return True
    async with httpx.AsyncClient(timeout=15, follow_redirects=True, headers=BROWSER_HEADERS) as c:
        await provider._fill_detail(job, c, sem)
        return True


def enrich_instahyre_job_sync(job: Job) -> bool:
    """Synchronously enrich an Instahyre job if not in an active event loop."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, enrich_instahyre_job(job)).result()
    else:
        return asyncio.run(enrich_instahyre_job(job))


def _format_salary(base_salary) -> Optional[str]:
    if not isinstance(base_salary, dict):
        return None
    value = base_salary.get("value") or {}
    lo = value.get("minValue") if isinstance(value, dict) else None
    hi = value.get("maxValue") if isinstance(value, dict) else None
    cur = value.get("currency") if isinstance(value, dict) else None
    if lo is None and hi is None:
        return None
    cur = cur or "INR"
    if lo and hi and lo != hi:
        return f"{cur} {lo:,.0f} – {hi:,.0f}"
    return f"{cur} {hi or lo:,.0f}"
