"""Adzuna — optional API-key provider with real location filtering (Gulf + India).

Enabled only when `api_keys.adzuna_app_id` and `adzuna_app_key` are set.
"""

from __future__ import annotations

import httpx

from ..models import Job
from ..util import strip_html
from .base import Provider

COUNTRY_MAP = {
    "india": "in", "gurugram": "in", "gurgaon": "in", "bengaluru": "in",
    "bangalore": "in", "delhi": "in", "mumbai": "in", "pune": "in",
    "hyderabad": "in", "chennai": "in", "noida": "in",
    "uae": "ae", "dubai": "ae", "abu dhabi": "ae", "sharjah": "ae",
    "saudi": "sa", "saudi arabia": "sa", "riyadh": "sa", "jeddah": "sa",
    "qatar": "qa", "doha": "qa",
    "bahrain": "bh", "manama": "bh",
    "kuwait": "kw", "kuwait city": "kw",
    "oman": "om", "muscat": "om",
    "usa": "us", "united states": "us",
    "uk": "gb", "united kingdom": "gb", "london": "gb",
    "singapore": "sg", "canada": "ca", "australia": "au", "germany": "de",
}

CURRENCY_BY_COUNTRY = {
    "in": "INR", "ae": "AED", "sa": "SAR", "qa": "QAR", "bh": "BHD",
    "kw": "KWD", "om": "OMR", "us": "USD", "gb": "GBP", "sg": "SGD",
    "ca": "CAD", "au": "AUD", "de": "EUR",
}


class AdzunaProvider(Provider):
    name = "adzuna"

    async def fetch(self, client: httpx.AsyncClient) -> list[Job]:
        app_id = self.keys.get("adzuna_app_id")
        app_key = self.keys.get("adzuna_app_key")
        if not app_id or not app_key:
            return []

        out: list[Job] = []
        for loc in self.cfg.get("locations", []):
            country = COUNTRY_MAP.get(loc.lower().strip())
            if not country:
                continue
            for term in self.terms[:2]:
                try:
                    r = await client.get(
                        f"https://api.adzuna.com/v1/api/jobs/{country}/search/1",
                        params={
                            "app_id": app_id,
                            "app_key": app_key,
                            "results_per_page": 30,
                            "what": term,
                            "where": loc,
                            "content-type": "application/json",
                        },
                    )
                    if r.status_code != 200:
                        continue
                    results = r.json().get("results", [])
                except Exception:
                    continue
                for j in results:
                    out.append(
                        Job(
                            id=f"adzuna-{j.get('id')}",
                            title=j.get("title", ""),
                            company=(j.get("company") or {}).get("display_name", ""),
                            location=(j.get("location") or {}).get("display_name", ""),
                            url=j.get("redirect_url", ""),
                            description=strip_html(j.get("description", "")),
                            salary_min=j.get("salary_min"),
                            salary_max=j.get("salary_max"),
                            salary_currency=CURRENCY_BY_COUNTRY.get(country),
                            salary_text=_salary_text(j, country),
                            source="adzuna",
                            posted_at=j.get("created"),
                        )
                    )
        return out


def _salary_text(j: dict, country: str) -> str | None:
    lo, hi = j.get("salary_min"), j.get("salary_max")
    if lo is None and hi is None:
        return None
    cur = CURRENCY_BY_COUNTRY.get(country, "")
    if lo and hi and lo != hi:
        return f"{cur} {lo:,.0f} – {hi:,.0f}"
    return f"{cur} {hi or lo:,.0f}"
