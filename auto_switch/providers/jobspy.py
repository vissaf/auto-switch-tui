"""JobSpy-backed providers (https://github.com/speedyapply/JobSpy).

One provider per job board, all delegating to the validated `python-jobspy`
scrapers (LinkedIn, Indeed, Glassdoor, ZipRecruiter, Google, Bayt, Naukri).
`scrape_jobs()` is synchronous and manages its own HTTP stack (curl_cffi TLS
fingerprinting), so each fetch runs in a worker thread via asyncio.to_thread.
"""

from __future__ import annotations

import asyncio
import hashlib
from typing import Any, Optional

from ..locations import LocTargets, resolve
from ..models import Job
from ..util import CURRENCY_RATE
from .base import Provider

# Registry name -> python-jobspy site name. Google is absent: its direct
# scraper is routinely IP-blocked, so the registry maps "google" to the
# SerpApi-backed provider instead (google_serpapi.py).
JOBSPY_SITES = {
    "linkedin": "linkedin",
    "indeed": "indeed",
    "glassdoor": "glassdoor",
    "zip_recruiter": "zip_recruiter",
    "naukri": "naukri",
}

# Preset regions (see locations.py) map to these Indeed/Glassdoor countries.
UAE_COUNTRY = "United Arab Emirates"

# EU searched country-level, ordered by IT market size; per-site pruning via
# SITE_COUNTRIES drops boards that don't serve a country.
EU_COUNTRIES = [
    "Germany", "Netherlands", "Ireland", "France",
    "Spain", "Poland", "Portugal", "Sweden",
]

CITY_TO_COUNTRY = {
    # UAE
    "dubai": UAE_COUNTRY, "abu dhabi": UAE_COUNTRY,
    "sharjah": UAE_COUNTRY, "ajman": UAE_COUNTRY,
    "ras al khaimah": UAE_COUNTRY, "fujairah": UAE_COUNTRY,
    # Rest of Gulf — reachable only via Custom entries
    "riyadh": "Saudi Arabia", "jeddah": "Saudi Arabia", "dammam": "Saudi Arabia",
    "doha": "Qatar", "kuwait city": "Kuwait", "manama": "Bahrain", "muscat": "Oman",
    # India
    "gurugram": "India", "gurgaon": "India", "bengaluru": "India",
    "bangalore": "India", "delhi": "India", "new delhi": "India",
    "mumbai": "India", "pune": "India", "hyderabad": "India",
    "noida": "India", "chandigarh": "India", "panchkula": "India",
    "mohali": "India", "shimla": "India",
    # USA
    "san francisco": "USA", "bay area": "USA", "new york": "USA",
    "seattle": "USA", "austin": "USA", "boston": "USA",
    "atlanta": "USA", "denver": "USA", "chicago": "USA",
    # Canada
    "toronto": "Canada", "vancouver": "Canada", "montreal": "Canada",
    "calgary": "Canada", "ottawa": "Canada",
    # UK
    "london": "UK", "manchester": "UK", "birmingham": "UK",
    "edinburgh": "UK", "bristol": "UK",
    # EU
    "berlin": "Germany", "munich": "Germany", "amsterdam": "Netherlands",
    "dublin": "Ireland", "paris": "France", "madrid": "Spain",
    "barcelona": "Spain", "warsaw": "Poland", "lisbon": "Portugal",
}

INDIA_CITIES = [
    "gurugram", "gurgaon", "bengaluru", "bangalore", "delhi", "new delhi",
    "mumbai", "pune", "hyderabad", "noida",
    "chandigarh", "panchkula", "mohali", "shimla",
]

# Multipliers to annualize a salary by its pay interval.
_INTERVAL_MULTIPLIER = {
    "yearly": 1.0,
    "monthly": 12.0,
    "weekly": 52.0,
    "daily": 260.0,
    "hourly": 2080.0,
}

MAX_TERMS_PER_RUN = 6

# Boards restricted to specific countries: geo specs outside this set are
# dropped (e.g. ZipRecruiter only serves US/Canada).
GLASSDOOR_COUNTRIES = {
    "Australia", "Austria", "Belgium", "Brazil", "Canada", "France",
    "Germany", "Hong Kong", "India", "Ireland", "Italy", "Malaysia",
    "Malta", "Mexico", "Netherlands", "New Zealand", "Singapore", "Spain",
    "Switzerland", "UK", "USA", "Vietnam",
}
SITE_COUNTRIES = {
    "zip_recruiter": {"USA", "Canada"},
    "naukri": {"India"},
    "glassdoor": GLASSDOOR_COUNTRIES,
}


def _num(value: Any) -> Optional[float]:
    """NaN/None-safe float conversion for pandas cells."""
    if value is None:
        return None
    try:
        if value != value:  # NaN
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _str(value: Any) -> str:
    if value is None:
        return ""
    try:
        if value != value:  # NaN
            return ""
    except TypeError:
        pass
    return str(value).strip()


def _mute_jobspy_loggers() -> None:
    """Silence python-jobspy's own console logging (we emit concise summaries).

    JobSpy logs one ERROR line per failed scrape call (e.g. Glassdoor's 403);
    when verbose==0 we already surface a single actionable summary, so its
    per-call spam is suppressed. We set the logger *level* (not just handler
    level) to CRITICAL and disable propagation, because jobspy's loggers stay
    at ERROR under verbose==0 and its timestamped StreamHandler would otherwise
    still emit.

    We also patch ``jobspy.create_logger`` so loggers created lazily *during* a
    scrape (e.g. ``create_logger(site_name).info("finished scraping")`` at the
    end of every scrape) are muted at birth — those are created after this
    function first ran and would otherwise leak an INFO line.
    """
    import logging

    for logger_name in list(logging.root.manager.loggerDict):
        if logger_name.startswith("JobSpy:"):
            lg = logging.getLogger(logger_name)
            lg.setLevel(logging.CRITICAL)
            lg.propagate = False
            for handler in lg.handlers:
                handler.setLevel(logging.CRITICAL)

    try:
        import jobspy
        import jobspy.util as _ju

        if not getattr(_ju.create_logger, "_muted_by_auto_switch", False):
            _orig = _ju.create_logger

            def _muted(name: str):
                lg = _orig(name)
                lg.setLevel(logging.CRITICAL)
                lg.propagate = False
                for handler in lg.handlers:
                    handler.setLevel(logging.CRITICAL)
                return lg

            _muted._muted_by_auto_switch = True  # type: ignore[attr-defined]
            _ju.create_logger = _muted
            # scrape_jobs references create_logger in jobspy/__init__'s namespace.
            jobspy.create_logger = _muted
    except Exception:  # noqa: BLE001 — best effort; jobspy may be missing
        pass


class JobSpyProvider(Provider):
    """Fetches one JobSpy-supported board and maps rows onto the Job model."""

    site = ""  # set by make_jobspy_provider

    def __init__(self, cfg: dict):
        super().__init__(cfg)
        js = cfg.get("jobspy") or {}
        self.results_wanted = int(js.get("results_wanted") or 15)
        self.hours_old = js.get("hours_old") or None
        self.linkedin_fetch_description = bool(js.get("linkedin_fetch_description"))
        self.enforce_annual_salary = bool(js.get("enforce_annual_salary"))
        self.proxies = js.get("proxies") or None
        self.verbose = int(js.get("verbose") or 0)
        self.max_calls = int(js.get("max_calls") or 10)
        self.max_workers = max(1, int(js.get("max_workers") or 3))

    # -- search spec construction -------------------------------------------

    def _locations(self, targets: LocTargets) -> list[tuple[Optional[str], Optional[str]]]:
        """(country_indeed, city) pairs derived from configured target areas."""
        pairs: list[tuple[Optional[str], Optional[str]]] = []
        if targets.uae:
            pairs.append((UAE_COUNTRY, None))
        if targets.india:
            pairs.append(("India", None))
        if targets.usa:
            pairs.append(("USA", None))
        if targets.canada:
            pairs.append(("Canada", None))
        if targets.uk:
            pairs.append(("UK", None))
        if targets.eu:
            pairs += [(c, None) for c in EU_COUNTRIES]
        for raw in targets.explicit:
            city = raw.strip()
            country = CITY_TO_COUNTRY.get(city.lower())
            pairs.append((country, city.title() if country else city))
        if not pairs:
            pairs = [("USA", None)]
        seen: set = set()
        unique = []
        for p in pairs:
            if p not in seen:
                seen.add(p)
                unique.append(p)
        return unique

    def _remote_scope(self, targets: LocTargets) -> Optional[str]:
        """Country to scope remote passes to, or None for worldwide.

        A single selected country scopes remote passes to it; multi-country
        selections (EU, several regions, custom) go worldwide.
        """
        singles = [
            country for country, on in (
                (UAE_COUNTRY, targets.uae), ("India", targets.india),
                ("USA", targets.usa), ("Canada", targets.canada),
                ("UK", targets.uk),
            ) if on
        ]
        if len(singles) == 1 and not targets.eu:
            return singles[0]
        return None

    def _specs(self) -> list[dict]:
        """One scrape call per (term x location), plus remote passes; capped.

        Selecting any preset region automatically includes remote passes
        (scoped to that region's country when a single country is targeted).
        Remote passes are reserved budget so a long country list can't crowd
        them out, and geo specs are filtered to countries the site serves.
        """
        targets = resolve(self.cfg.get("locations") or [])
        terms = self.terms[:MAX_TERMS_PER_RUN]

        include_remote = targets.remote or targets.has_preset_geo
        scope = self._remote_scope(targets)
        allowed = SITE_COUNTRIES.get(self.site)
        if scope and allowed is not None and scope not in allowed:
            scope = None  # board can't serve that country; go worldwide
        remote_specs = [
            {
                "search_term": term,
                "location": scope,
                "country_indeed": scope,
                "is_remote": True,
            }
            for term in terms
        ] if include_remote else []

        locs = self._locations(targets)
        if allowed is not None:
            locs = [
                p for p in locs
                if p[0] in allowed or (p[0] is None and p[1])
            ]

        geo_specs: list[dict] = []
        if self.site == "bayt":  # searches internationally, term only
            geo_specs = [
                {
                    "search_term": term, "location": None,
                    "country_indeed": None, "is_remote": False,
                }
                for term in terms
            ]
        elif locs:
            for term in terms:
                for country, city in locs:
                    geo_specs.append({
                        "search_term": term,
                        "location": city or country,
                        "country_indeed": country,
                        "is_remote": False,
                    })

        max_geo = self.max_calls - len(remote_specs)
        if not geo_specs:
            return remote_specs[: self.max_calls]
        return geo_specs[: max(1, max_geo)] + remote_specs

    def _should_run(self, targets: LocTargets) -> bool:
        """Skip boards that cannot serve the configured areas."""
        if self.site == "zip_recruiter":
            # US/Canada only.
            return (
                not targets.active
                or targets.usa or targets.canada or targets.remote
                or any(
                    CITY_TO_COUNTRY.get(c) in ("USA", "Canada")
                    for c in targets.explicit
                )
            )
        if self.site == "naukri":
            return (
                not targets.active
                or targets.india
                or any(CITY_TO_COUNTRY.get(c) == "India" for c in targets.explicit)
            )
        return True

    # -- scraping -------------------------------------------------------------

    def _scrape_one(self, spec: dict) -> Any:
        from jobspy import scrape_jobs

        if self.verbose == 0:
            _mute_jobspy_loggers()

        kwargs: dict[str, Any] = dict(
            site_name=self.site,
            search_term=spec["search_term"],
            results_wanted=self.results_wanted,
            description_format="markdown",
            linkedin_fetch_description=self.linkedin_fetch_description,
            enforce_annual_salary=self.enforce_annual_salary,
            proxies=self.proxies,
            verbose=self.verbose,
        )
        if spec["is_remote"]:
            # Indeed limitation: hours_old cannot combine with is_remote.
            kwargs["hours_old"] = None
            kwargs["is_remote"] = True
        else:
            kwargs["hours_old"] = self.hours_old
        if spec["location"]:
            kwargs["location"] = spec["location"]
        if spec["country_indeed"]:
            kwargs["country_indeed"] = spec["country_indeed"]
        return scrape_jobs(**kwargs)

    _BLOCK_HINT = (
        "no results across repeated calls — likely IP-blocked by the board. "
        "Fix: set residential proxies in jobspy.proxies "
        "(~/.config/auto-switch/config.json) or disable providers.{board}."
    )
    _EMPTY_ABORT = 2  # consecutive empty results before treating a board as blocked

    def _scrape_sync(self):
        """Run all spec calls concurrently (bounded by max_workers).

        Specs are independent (term x location), so a worker pool cuts wall
        time from ``sum(spec)`` to roughly ``max(spec) * ceil(n/workers)``.
        Blocked-board detection is kept soft: once a board signals blocking
        (403/429 or repeated empties), pending spec calls are cancelled.
        """
        import pandas as pd
        from concurrent.futures import ThreadPoolExecutor, as_completed

        specs = self._specs()
        targets = resolve(self.cfg.get("locations") or [])
        if not self._should_run(targets) or not specs:
            return pd.DataFrame()

        frames = []
        errors = 0
        empty_streak = 0
        blocked = False
        block_msg = None

        with ThreadPoolExecutor(max_workers=min(self.max_workers, len(specs))) as pool:
            futures = {pool.submit(self._scrape_one, spec): spec for spec in specs}
            for fut in as_completed(futures):
                spec = futures[fut]
                try:
                    df = fut.result()
                except Exception as exc:  # noqa: BLE001 — keep scraping other specs
                    errors += 1
                    empty_streak += 1
                    if any(code in str(exc) for code in ("403", "429")):
                        blocked = True
                    print(f"  ! {self.name}/{spec['search_term']}: {exc}")
                else:
                    if df is not None and len(df):
                        frames.append(df)
                        empty_streak = 0
                    else:
                        empty_streak += 1
                        if empty_streak >= self._EMPTY_ABORT:
                            blocked = True

                if blocked:
                    for pending in futures:
                        pending.cancel()
                    block_msg = self._BLOCK_HINT.format(board=self.name)
                    break

        if frames:
            if block_msg:
                print(f"  ! {self.name}: {block_msg}")
            return pd.concat(frames, ignore_index=True)
        if errors or blocked:
            raise RuntimeError(block_msg or self._BLOCK_HINT.format(board=self.name))
        return pd.DataFrame()

    async def fetch(self, client) -> list[Job]:
        df = await asyncio.to_thread(self._scrape_sync)
        return _df_to_jobs(df, self.name)


# -- DataFrame -> Job mapping -------------------------------------------------


def _salary_text(lo: Optional[float], hi: Optional[float],
                 currency: str, interval: Optional[str]) -> Optional[str]:
    if lo is None and hi is None:
        return None
    parts = []
    if lo is not None and hi is not None and lo != hi:
        parts.append(f"{lo:,.0f}-{hi:,.0f}")
    else:
        parts.append(f"{(lo if lo is not None else hi):,.0f}")
    if currency:
        parts.append(currency)
    if interval:
        parts.append(interval)
    return " ".join(parts)


def _annual_usd(lo: Optional[float], hi: Optional[float],
                currency: str, interval: Optional[str]) -> Optional[float]:
    amount = hi or lo
    if amount is None:
        return None
    mult = _INTERVAL_MULTIPLIER.get(interval or "yearly", 1.0)
    rate = CURRENCY_RATE.get((currency or "USD").upper(), 1.0)
    return round(amount * mult * rate, 0)


def _row_to_job(row: Any, source: str) -> Job:
    url = _str(row.get("job_url")) or _str(row.get("job_url_direct"))
    native_id = _str(row.get("id")) or hashlib.sha1(url.encode()).hexdigest()[:12]
    currency = (_str(row.get("currency")) or "USD").upper()
    interval = _str(row.get("interval")) or None
    lo, hi = _num(row.get("min_amount")), _num(row.get("max_amount"))

    posted = row.get("date_posted")
    posted_at = None
    if posted is not None and str(posted) not in ("NaT", "nan"):
        try:
            posted_at = getattr(posted, "isoformat", lambda: str(posted))()
        except Exception:  # noqa: BLE001
            posted_at = str(posted)

    return Job(
        id=f"{source}-{native_id}",
        title=_str(row.get("title")),
        company=_str(row.get("company")),
        location=_str(row.get("location")),
        url=url,
        description=_str(row.get("description")),
        remote=bool(row.get("is_remote")),
        salary_min=lo,
        salary_max=hi,
        salary_currency=currency if (lo is not None or hi is not None) else None,
        salary_text=_salary_text(lo, hi, currency, interval),
        salary_annual_usd=_annual_usd(lo, hi, currency, interval),
        source=source,
        posted_at=posted_at,
    )


def _df_to_jobs(df: Any, source: str) -> list[Job]:
    if df is None or not len(df):
        return []
    jobs: list[Job] = []
    seen_urls: set[str] = set()
    for _, row in df.iterrows():
        job = _row_to_job(row, source)
        if not job.title or not job.url or job.url in seen_urls:
            continue
        seen_urls.add(job.url)
        jobs.append(job)
    return jobs


def make_jobspy_provider(name: str) -> type[JobSpyProvider]:
    """Create a Provider subclass bound to one JobSpy board."""
    site = JOBSPY_SITES[name]

    class _Bound(JobSpyProvider):
        pass

    _Bound.name = name
    _Bound.site = site
    _Bound.__doc__ = f"JobSpy-backed {site} provider."
    return _Bound
