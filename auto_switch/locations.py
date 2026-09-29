"""Location resolution + matching: turn a user's target areas into a
region classifier and a per-job matcher."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .models import Job

# Selectable areas shown in the setup menu (config.py) — order matters.
REGIONS = ["UAE", "India", "USA", "Canada", "UK", "EU", "Remote"]

# Main IT-hub locations per region (menu display; kept consistent with the
# keyword sets below so hub jobs always pass the post-fetch filter).
REGION_HUBS = {
    "UAE": ["Dubai", "Abu Dhabi"],
    "India": [
        "Bengaluru", "Gurugram", "Hyderabad", "Pune", "Mumbai",
        "Noida", "Chennai", "Chandigarh", "Panchkula", "Mohali", "Shimla",
    ],
    "USA": [
        "SF Bay Area", "New York", "Seattle", "Austin",
        "Boston", "Atlanta", "Denver", "Chicago",
    ],
    "Canada": ["Toronto", "Vancouver", "Montreal", "Calgary", "Ottawa"],
    "UK": ["London", "Manchester", "Birmingham", "Edinburgh", "Bristol"],
    "EU": [
        "Berlin", "Munich", "Amsterdam", "Dublin", "Paris",
        "Madrid", "Warsaw", "Lisbon",
    ],
    "Remote": ["Worldwide"],
}

UAE_KEYWORDS = [
    "uae", "united arab emirates", "emirates", "dubai", "abu dhabi",
    "sharjah", "ajman", "ras al khaimah", "fujairah", "umm al quwain",
]

INDIA_KEYWORDS = [
    "india", "bharat",
    "gurugram", "gurgaon", "bengaluru", "bangalore", "delhi",
    "new delhi", "ncr", "mumbai", "navi mumbai", "pune", "hyderabad", "noida",
    "greater noida", "chennai", "madras", "chandigarh", "panchkula", "mohali", "shimla",
    "ahmedabad", "gandhinagar", "kolkata", "calcutta",
    "kochi", "cochin", "trivandrum", "thiruvananthapuram", "calicut", "kozhikode",
    "indore", "bhopal", "jaipur", "surat", "vadodara", "baroda",
    "coimbatore", "nagpur", "visakhapatnam", "vizag", "vijayawada",
    "bhubaneswar", "bhubaneshwar", "patna", "ranchi", "raipur",
    "lucknow", "kanpur", "dehradun", "mysuru", "mysore",
    "mangalore", "mangaluru", "goa", "panaji", "madurai", "tirupati",
    # States & Union Territories
    "karnataka", "maharashtra", "tamil nadu", "telangana", "andhra pradesh",
    "uttar pradesh", "haryana", "kerala", "gujarat", "west bengal",
    "rajasthan", "madhya pradesh", "punjab", "odisha", "orissa",
    "bihar", "jharkhand", "assam", "uttarakhand", "himachal pradesh",
    "chhattisgarh",
]

USA_KEYWORDS = [
    "usa", "us", "united states", "america",
    # States & territories
    "california", "new york", "texas", "washington", "massachusetts",
    "georgia", "colorado", "illinois", "florida", "washington dc",
    "north carolina", "virginia", "pennsylvania", "arizona", "utah",
    "oregon", "minnesota", "michigan", "ohio", "new jersey", "indiana",
    # Major tech hubs & cities
    "san francisco", "bay area", "silicon valley", "san jose", "palo alto",
    "mountain view", "sunnyvale", "santa clara", "redwood city", "menlo park",
    "cupertino", "oakland", "berkeley", "los angeles", "san diego",
    "seattle", "bellevue", "redmond", "kirkland", "portland",
    "austin", "dallas", "houston",
    "boston", "cambridge",
    "atlanta", "denver", "boulder", "chicago",
    "miami", "orlando", "tampa",
    "raleigh", "durham", "charlotte",
    "pittsburgh", "philadelphia",
    "phoenix", "salt lake city", "minneapolis", "detroit",
    "arlington", "mclean", "reston", "baltimore", "honolulu",
]

CANADA_KEYWORDS = [
    "canada", "ontario", "british columbia", "quebec", "alberta",
    "nova scotia", "manitoba", "saskatchewan", "new brunswick", "newfoundland",
    # Major tech hubs & cities
    "toronto", "vancouver", "montreal", "calgary", "ottawa",
    "waterloo", "kitchener", "victoria", "edmonton", "halifax",
    "mississauga", "burnaby", "quebec city", "winnipeg",
]

UK_KEYWORDS = [
    "uk", "united kingdom", "great britain", "britain", "england", "scotland", "wales",
    "northern ireland",
    # Major tech hubs & cities
    "london", "manchester", "birmingham", "edinburgh", "bristol",
    "cambridge", "oxford", "glasgow", "cardiff", "belfast",
    "leeds", "sheffield", "newcastle",
]

EU_KEYWORDS = [
    "eu", "europe", "european union",
    # Western & Central Europe
    "germany", "netherlands", "ireland", "france", "spain", "poland",
    "portugal", "sweden", "italy", "belgium", "austria", "switzerland",
    # Nordics & Eastern / Southern Europe
    "denmark", "finland", "norway", "estonia", "czech republic", "czechia",
    "romania", "greece", "hungary", "luxembourg", "bulgaria", "croatia",
    "slovakia", "slovenia", "lithuania", "latvia", "cyprus", "malta", "iceland",
    # Major tech hubs & cities
    "berlin", "munich", "amsterdam", "dublin", "paris", "madrid",
    "barcelona", "warsaw", "lisbon", "stockholm",
    "copenhagen", "helsinki", "oslo", "tallinn", "prague",
    "vienna", "brussels", "zurich", "geneva", "bucharest", "cluj",
    "athens", "budapest",
]

REMOTE_KEYWORDS = ["remote", "worldwide", "anywhere", "work from home", "wfh"]

_INDIA_STATE_CODES = {
    "ap", "ar", "as", "br", "cg", "ct", "ga", "gj", "hr", "hp", "jh",
    "ka", "kl", "mp", "mh", "mn", "ml", "mz", "nl", "od", "or", "pb",
    "rj", "sk", "tn", "ts", "tr", "up", "uk", "ut", "wb", "dl", "jk",
    "la", "py", "ch",
}

_UAE_EMIRATE_CODES = {"az", "aj", "du", "fu", "ra", "sh", "uq"}

# 50 US states + DC (note: "in" is omitted from bare states to prevent colliding
# with India's ISO country code; Indiana in the US is handled via full name or explicit ", IN, USA")
_US_STATE_CODES = {
    "al", "ak", "az", "ar", "ca", "co", "ct", "de", "fl", "ga", "hi", "id",
    "il", "ia", "ks", "ky", "la", "me", "md", "ma", "mi", "mn", "ms", "mo",
    "mt", "ne", "nv", "nh", "nj", "nm", "ny", "nc", "nd", "oh", "ok", "or",
    "pa", "ri", "sc", "sd", "tn", "tx", "ut", "vt", "va", "wa", "wv", "wi",
    "wy", "dc",
}

_CANADA_PROVINCE_CODES = {
    "on", "bc", "qc", "ab", "ns", "mb", "sk", "nb", "nl", "pe", "nt", "yt", "nu",
}

# Common board location formats (Indeed, JobSpy, LinkedIn, Ashby, Greenhouse, Lever)
_INDIA_CODE_RE = re.compile(
    r"(?:"
    r"^in$"
    r"|(?:^|[\s,])remote,\s*in\b"
    r"|(?:^|[\s,])(?:" + "|".join(_INDIA_STATE_CODES) + r"),\s*in\b"
    r")",
    re.IGNORECASE,
)

_UAE_CODE_RE = re.compile(
    r"(?:"
    r"^ae$"
    r"|(?:^|[\s,])remote,\s*ae\b"
    r"|(?:^|[\s,])(?:" + "|".join(_UAE_EMIRATE_CODES) + r"),\s*ae\b"
    r")",
    re.IGNORECASE,
)

_US_CODE_RE = re.compile(
    r"(?:"
    r"(?:^|[\s,])(?:remote,\s*us\b|us\s*-\s*remote\b|remote\s*-\s*usa\b)"
    r"|,\s*(?:" + "|".join(_US_STATE_CODES) + r")(?:\s*,\s*(?:usa|united states|us))?$"
    r"|,\s*(?:" + "|".join(_US_STATE_CODES) + r")\s*,\s*(?:usa|united states|us)\b"
    r"|,\s*in\s*,\s*(?:usa|united states|us)\b"
    r")",
    re.IGNORECASE,
)

_CANADA_CODE_RE = re.compile(
    r"(?:"
    r"^ca$"
    r"|(?:^|[\s,])(?:remote,\s*ca\b|remote\s*-\s*canada\b)"
    r"|,\s*(?:" + "|".join(_CANADA_PROVINCE_CODES) + r")(?:\s*,\s*(?:canada|ca))?$"
    r"|,\s*(?:" + "|".join(_CANADA_PROVINCE_CODES) + r")\s*,\s*(?:canada|ca)\b"
    r")",
    re.IGNORECASE,
)

_UK_CODE_RE = re.compile(
    r"(?:"
    r"^gb$"
    r"|(?:^|[\s,])(?:remote,\s*gb\b|remote\s*-\s*uk\b|remote\s*-\s*gb\b)"
    r"|,\s*gb(?:\s*,\s*(?:uk|united kingdom))?$"
    r"|,\s*gb\s*,\s*(?:uk|united kingdom)\b"
    r")",
    re.IGNORECASE,
)

_EU_CODE_RE = re.compile(
    r"(?:"
    r"^eu$"
    r"|(?:^|[\s,])(?:remote,\s*eu\b|remote\s*-\s*eu\b)"
    r"|,\s*eu$"
    r")",
    re.IGNORECASE,
)

_REGION_NAMES = {
    "uae": "uae", "united arab emirates": "uae", "emirates": "uae",
    "ae": "uae",
    "gulf": "uae",  # legacy alias from pre-rename configs
    "india": "india", "in": "india",
    "usa": "usa", "us": "usa", "united states": "usa", "america": "usa",
    "canada": "canada",
    "uk": "uk", "united kingdom": "uk", "great britain": "uk", "britain": "uk", "england": "uk", "gb": "uk",
    "eu": "eu", "europe": "eu", "european union": "eu",
}


@dataclass
class LocTargets:
    uae: bool = False
    india: bool = False
    usa: bool = False
    canada: bool = False
    uk: bool = False
    eu: bool = False
    remote: bool = False
    explicit: list[str] = field(default_factory=list)

    @property
    def active(self) -> bool:
        return (
            self.uae or self.india or self.usa or self.canada
            or self.uk or self.eu or self.remote or bool(self.explicit)
        )

    @property
    def has_preset_geo(self) -> bool:
        """Any preset geographic region selected (Remote/custom don't count)."""
        return (
            self.uae or self.india or self.usa
            or self.canada or self.uk or self.eu
        )


def _boundary(kw: str) -> re.Pattern:
    return re.compile(rf"(?<![a-z0-9]){re.escape(kw)}(?![a-z0-9])")


def _any(loc: str, keywords: list[str]) -> bool:
    return any(_boundary(kw).search(loc) for kw in keywords)


def _classify_one(loc: str) -> str:
    norm = loc.strip().lower()
    if not norm:
        return "none"
    if norm in REMOTE_KEYWORDS:
        return "remote"
    region = _REGION_NAMES.get(norm)
    if region:
        return region
    # Hub cities / states classify into their preset region.
    for region_name, kws in (
        ("uae", UAE_KEYWORDS), ("india", INDIA_KEYWORDS),
        ("usa", USA_KEYWORDS), ("canada", CANADA_KEYWORDS),
        ("uk", UK_KEYWORDS), ("eu", EU_KEYWORDS),
    ):
        if norm in kws:
            return region_name
    return "other"


def resolve(locations: list[str] | None) -> LocTargets:
    targets = LocTargets()
    for loc in locations or []:
        kind = _classify_one(loc)
        if kind == "remote":
            targets.remote = True
        elif kind == "other":
            targets.explicit.append(loc.strip().lower())
        elif kind != "none":
            setattr(targets, kind, True)
    return targets


def matches(job: Job, targets: LocTargets) -> bool:
    """Whether a job's location satisfies the target areas."""
    if not targets.active:
        return True
    loc = (job.location or "").lower()
    is_remote_job = bool(job.remote) or _any(loc, REMOTE_KEYWORDS)
    if targets.remote and is_remote_job:
        return True
    if targets.uae and (_any(loc, UAE_KEYWORDS) or _UAE_CODE_RE.search(loc)):
        return True
    if targets.india and (_any(loc, INDIA_KEYWORDS) or _INDIA_CODE_RE.search(loc)):
        return True
    if targets.usa and (_any(loc, USA_KEYWORDS) or _US_CODE_RE.search(loc)):
        return True
    if targets.canada and (_any(loc, CANADA_KEYWORDS) or _CANADA_CODE_RE.search(loc)):
        return True
    if targets.uk and (_any(loc, UK_KEYWORDS) or _UK_CODE_RE.search(loc)):
        return True
    if targets.eu and (_any(loc, EU_KEYWORDS) or _EU_CODE_RE.search(loc)):
        return True
    for kw in targets.explicit:
        if _boundary(kw).search(loc):
            return True
    return False


def filter_jobs(jobs: list[Job], locations: list[str] | None) -> list[Job]:
    targets = resolve(locations)
    return [j for j in jobs if matches(j, targets)]
