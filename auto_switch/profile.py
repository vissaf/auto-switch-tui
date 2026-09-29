"""Profile parsing: skills, proficiency tiers, and matching helpers.

A skill is matched against job text via a word-boundary alias regex, with an
optional *exclude* list that forbids compound matches (e.g. ``react`` must not
match inside ``react native``).

Each skill carries two orthogonal numbers:

- ``weight``  — how important this skill is to a frontend role (JD demand size).
- ``tier``    — the candidate's proficiency; converted to an earned-credit
  factor via :data:`TIER_FACTOR` when a JD demands the skill.

Tiers are resolved by priority: the manual ``## Experience matrix`` section in
``profile.md`` first, then corpus mining (:mod:`.evidence`), then the curated
default tier baked into :data:`SKILLS`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .paths import experiences_dir as _experiences_dir
from .paths import profile_path as _profile_path

# Proficiency -> earned-credit multiplier when a JD demands this skill.
# "has-it" tiers (core..familiar) are assignable by auto-mining; the rest are
# curated (adjacent = transferable framework, unfamiliar = JS-adjacent but not
# used, foreign = different discipline).
TIER_FACTOR = {
    "core": 1.00,
    "strong": 0.88,
    "secondary": 0.72,
    "adjacent": 0.66,      # React Native — closest transferable framework
    "familiar": 0.45,
    "unfamiliar": 0.30,    # Vue/Nuxt/Svelte/jQuery — JS-adjacent, not used
    "foreign_low": 0.12,   # Flutter / page builders / legacy CMS
    "foreign": 0.00,       # non-JS backends / native mobile
}

# Order for "upgrade-only" tier resolution (best -> worst among has-it tiers).
_TIER_ORDER = ("core", "strong", "secondary", "familiar")
_TIER_RANK = {t: i for i, t in enumerate(_TIER_ORDER)}


@dataclass
class Keyword:
    label: str
    aliases: tuple[str, ...]
    weight: int
    tier: str = "strong"
    exclude: tuple[str, ...] = ()


# Curated skill registry. `tier` is the DEFAULT (curated) proficiency; it is
# overridden by corpus mining and/or the profile.md Experience matrix. Weights
# express how strongly a JD's demand for that skill should steer the score.
SKILLS: list[Keyword] = [
    # --- React ecosystem (core: 4y senior React, prominence per user) -------
    Keyword("React", ("react", "react.js", "reactjs"), 10, "core", ("native",)),
    Keyword("Next.js", ("next.js", "nextjs", "next js"), 10, "core"),
    Keyword("TypeScript", ("typescript",), 10, "core"),
    Keyword("Redux", ("redux", "redux toolkit", "rtk"), 8, "core"),
    Keyword("Zustand", ("zustand",), 5, "core"),
    Keyword("TanStack Query", ("tanstack", "react-query", "react query"), 5, "core"),
    Keyword("Preact", ("preact",), 5, "core"),
    Keyword("Build Tools", ("vite", "webpack", "esbuild", "bundler", "parcel"), 6, "core"),
    Keyword("Bun", ("bun", "bun.sh"), 4, "core"),
    # --- strong (used heavily, verified in corpus) ---------------------------
    Keyword("JavaScript", ("javascript", "es6", "es2024", "ecmascript"), 8, "strong"),
    Keyword("Node.js", ("node.js", "nodejs", "node js"), 6, "secondary"),
    Keyword("Testing", ("jest", "react testing library", "vitest", "karma", "jasmine"), 6, "strong"),
    Keyword("E2E Testing", ("playwright", "cypress", "e2e", "end-to-end"), 4, "strong"),
    Keyword("Tailwind CSS", ("tailwind", "tailwindcss", "tailwind css"), 5, "strong"),
    Keyword("shadcn/ui", ("shadcn", "shadcn/ui", "shadcn ui"), 4, "strong"),
    Keyword("React Hook Form", ("react hook form", "react-hook-form"), 4, "strong"),
    Keyword("Zod", ("zod",), 3, "strong"),
    Keyword("MSW", ("msw",), 3, "strong"),
    Keyword("PWA", ("pwa", "progressive web app", "service worker", "service workers", "offline support"), 4, "strong"),
    Keyword("Data Grids", ("data grid", "data grids", "virtualized list", "virtualized table", "react-window", "react virtualized", "react-table", "react table"), 4, "strong"),
    Keyword("GraphQL", ("graphql",), 6, "strong"),
    Keyword("SSR/SSG/ISR", ("ssr", "ssg", "isr", "server-side rendering", "static site generation", "incremental static regeneration"), 5, "strong"),
    Keyword("Sanity CMS", ("sanity", "sanity studio", "sanity cms"), 5, "strong"),
    Keyword("REST APIs", ("rest api", "restful", "rest endpoints", "rest"), 4, "strong"),
    Keyword("Storybook", ("storybook",), 4, "strong"),
    Keyword("Accessibility", ("accessibility", "a11y", "wcag", "aria", "screen-reader"), 5, "strong"),
    Keyword("Design System", ("design system", "design systems"), 5, "strong"),
    Keyword("Performance", ("performance", "optimization", "web vitals", "lighthouse", "core web vitals"), 4, "strong"),
    Keyword("HTML/CSS", ("html5", "css3", "scss", "sass", "css"), 5, "strong"),
    Keyword("Analytics", ("analytics", "google analytics", "mixpanel", "amplitude", "event tracking"), 3, "secondary"),
    # --- secondary (known, but junior-era or domain-specific) ---------------
    Keyword("Angular", ("angular", "angularjs"), 7, "secondary"),
    Keyword("E-commerce", ("e-commerce", "ecommerce", "e commerce", "checkout", "shopping cart"), 6, "secondary"),
    Keyword("B2B", ("b2b", "business-to-business"), 5, "secondary"),
    Keyword("SaaS", ("saas",), 5, "secondary"),
    Keyword("EdTech", ("edtech", "ed-tech", "e-learning", "elearning"), 4, "secondary"),
    Keyword("CRM", ("crm",), 4, "secondary"),
    Keyword("Monorepo", ("monorepo", "turborepo", "nx"), 4, "secondary"),
    Keyword("Micro-frontends", ("micro-frontend", "microfrontend", "module federation"), 4, "secondary"),
    # --- familiar (supporting skills) ---------------------------------------
    Keyword("CI/CD", ("ci/cd", "ci cd", "pipeline", "github actions"), 3, "familiar"),
    Keyword("Agile", ("agile", "scrum", "sprint"), 3, "familiar"),
    Keyword("Git", ("git", "github"), 3, "familiar"),
    Keyword("CMS", ("headless cms", "contentful", "strapi", "cms"), 3, "familiar"),
    Keyword("AI-Assisted Dev", ("copilot", "claude", "ai-assisted", "ai assisted", "llm"), 3, "familiar"),
    # --- adjacent / unfamiliar / foreign (NOT in the profile corpus) --------
    Keyword("React Native", ("react native", "react-native", "reactnative"), 9, "adjacent"),
    Keyword("Vue", ("vue", "vue.js", "vuejs", "nuxt", "nuxt.js", "nuxtjs"), 7, "unfamiliar"),
    Keyword("Svelte", ("svelte", "sveltekit", "svelte kit"), 6, "unfamiliar"),
    Keyword("jQuery", ("jquery",), 4, "unfamiliar"),
    # --- backend / infra (NOT frontend — drags full-stack JDs down) ----------
    Keyword("Databases", ("postgresql", "postgres", "mysql", "mongodb", "sql", "nosql", "redis", "dynamodb", "database"), 6, "foreign"),
    Keyword("Backend Frameworks", ("express", "express.js", "nestjs", "nest.js", "fastify"), 6, "foreign"),
    Keyword("Cloud/DevOps", ("aws", "azure", "gcp", "google cloud", "docker", "kubernetes", "terraform", "lambda", "serverless"), 6, "foreign"),
    Keyword("Flutter", ("flutter", "dart"), 6, "foreign_low"),
    Keyword("WordPress", ("wordpress", "drupal", "wix", "webflow", "squarespace"), 4, "foreign_low"),
    Keyword("Swift", ("swift", "objective-c", "objective c"), 5, "foreign"),
    Keyword("Kotlin", ("kotlin",), 5, "foreign"),
    Keyword("Java", ("java", "spring", "spring boot"), 6, "foreign"),
    Keyword(".NET", (".net", "c#", "dotnet", "asp.net"), 6, "foreign"),
    Keyword("PHP", ("php", "laravel", "symfony"), 5, "foreign"),
    Keyword("Python", ("python", "django", "flask", "fastapi"), 5, "foreign"),
    Keyword("Ruby", ("ruby", "ruby on rails", "rails"), 5, "foreign"),
    Keyword("Go", ("golang",), 4, "foreign"),
]

# Backward-compatible alias (the app historically referred to this as KEYWORDS).
KEYWORDS = SKILLS


def _alias_pattern(alias: str, exclude: tuple[str, ...]) -> re.Pattern:
    """Word-boundary alias regex with negative lookaheads for compound terms.

    ``exclude=("native",)`` for alias ``react`` yields a pattern that matches
    ``react`` / ``react.js`` but NOT ``react native`` / ``react-native`` /
    ``reactnative``.
    """
    parts = [rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])"]
    for ex in exclude:
        parts.append(rf"(?![\s\-]{{0,2}}{re.escape(ex)}(?![a-z0-9]))")
    return re.compile("".join(parts))


# Precompile matching patterns once.
_ALIAS_PATTERNS: dict[tuple[str, tuple[str, ...]], re.Pattern] = {}


def _pattern_for(alias: str, exclude: tuple[str, ...]) -> re.Pattern:
    key = (alias, exclude)
    if key not in _ALIAS_PATTERNS:
        _ALIAS_PATTERNS[key] = _alias_pattern(alias, exclude)
    return _ALIAS_PATTERNS[key]


def match_skills(text: str, skills: list[Keyword]) -> dict[str, int]:
    """Return {label: occurrence_count} for every skill mentioned in ``text``.

    Occurrences are summed across a skill's aliases (each alias matched
    non-overlapping). The caller is responsible for capping / weighting.
    """
    low = text.lower()
    counts: dict[str, int] = {}
    for sk in skills:
        n = 0
        for alias in sk.aliases:
            n += len(_pattern_for(alias, sk.exclude).findall(low))
        if n:
            counts[sk.label] = n
    return counts


def keyword_hits(text: str, keywords: list[Keyword]) -> tuple[int, list[str]]:
    """Backward-compatible summary: (sum of weights, [matched labels])."""
    counts = match_skills(text, keywords)
    by_label = {k.label: k for k in keywords}
    total = sum(by_label[lbl].weight for lbl in counts)
    return total, list(counts)


# A job title with any of these is considered a reasonable target level.
TITLE_PATTERNS = {
    "frontend": re.compile(r"front[- ]?end|frontend|web (engineer|developer)|ui (engineer|developer)|software engineer", re.I),
    "senior": re.compile(r"\bsenior\b|\bsr\.?\b", re.I),
    "lead": re.compile(r"\blead\b", re.I),
    "staff": re.compile(r"\bstaff\b|\bprincipal\b", re.I),
    "engineer": re.compile(r"\bengineer\b|\bdeveloper\b", re.I),
    "junior": re.compile(
        r"\bintern(?:ship)?\b|\bjunior\b|\bgraduate\b|\bentry[- ]?level\b|\btrainee\b|\bfresher\b"
        r"|\bsde[- ]?[i1]\b|\b(?:software\s+)?(?:engineer|developer|dev)[- ]?[i1]\b",
        re.I,
    ),
    "mid": re.compile(r"\bsde[- ]?(?:ii|2)\b|\b(?:software\s+)?(?:engineer|developer|dev)[- ]?(?:ii|2)\b", re.I),
}

# Small role-fit bonus (kept low so normalized coverage dominates the score).
TITLE_BONUS = {"frontend": 4, "senior": 2, "lead": 1, "staff": 1, "engineer": 1, "junior": -10, "mid": -4}
TITLE_BONUS_CAP = 6


def _grab(pattern: str, text: str) -> Optional[str]:
    m = re.search(pattern, text)
    if m is None:
        return None
    # Patterns without a capture group return the whole match, stripped.
    return (m.group(1) if m.groups() else m.group(0)).strip()


def load_profile(workspace: Path) -> dict:
    profile_path = _profile_path(workspace)
    data: dict = {}
    if profile_path.exists():
        text = profile_path.read_text(encoding="utf-8")
        data["name"] = _grab(r"Name:\s*(.+)", text)
        data["headline"] = _grab(r"Headline:\s*(.+)", text)
        data["years"] = _grab(r"Years of experience:\s*(.+)", text)
        data["location"] = _grab(r"Location:\s*(.+)", text)
        data["summary"] = _grab(r"## Professional summary[\s\S]*?(?=\n## )", text) or ""
        data["skills"] = _grab(r"## Skills[\s\S]*?(?=\n## )", text) or ""
    return data


_YEARS_NUM = re.compile(r"(\d+(?:\.\d+)?)")


def _years_from_field(value: str) -> Optional[float]:
    m = _YEARS_NUM.search(value or "")
    return float(m.group(1)) if m else None


def _years_from_corpus(workspace: Path) -> Optional[float]:
    """Infer years of experience from 4-digit dates in the evidence corpus."""
    exp_dir = _experiences_dir(workspace)
    if not exp_dir.exists():
        return None
    years: set[int] = set()
    for name in ("PORTFOLIO.md", "RESUME_BULLETS.md"):
        for f in exp_dir.glob(f"**/{name}"):
            try:
                text = f.read_text(encoding="utf-8")
            except Exception:
                continue
            for y in re.findall(r"\b(20\d{2})\b", text):
                years.add(int(y))
    if not years:
        return None
    return float(max(years) - min(years) + 1)


def resolve_years(workspace: Path) -> Optional[float]:
    """Candidate's total years of experience, from profile.md or the evidence.

    Priority: the ``Years of experience:`` field in ``data/profile.md`` (set by
    onboarding), then an inference from year mentions in the experience corpus.
    Returns ``None`` when unknown — callers then skip level-based penalties.
    """
    profile = _profile_path(workspace)
    if profile.exists():
        data = load_profile(workspace)
        years = _years_from_field(data.get("years") or "")
        if years is not None:
            return years
    return _years_from_corpus(workspace)


# -- Experience matrix (manual tier override) ---------------------------------

_MATRIX_HEADER = re.compile(r"^##\s+Experience matrix\b", re.I | re.M)
_MATRIX_END = re.compile(r"^\n##\s+", re.M)


def _match_label(skills: list[Keyword], name: str) -> Optional[str]:
    low = name.strip().lower()
    for sk in skills:
        if low == sk.label.lower():
            return sk.label
    for sk in skills:
        if any(a.lower() == low for a in sk.aliases):
            return sk.label
    return None


def parse_experience_matrix(workspace: Path, skills: list[Keyword]) -> dict[str, str]:
    """Parse ``## Experience matrix`` from profile.md -> {label: tier}."""
    profile_path = _profile_path(workspace)
    if not profile_path.exists():
        return {}
    text = profile_path.read_text(encoding="utf-8")
    m = _MATRIX_HEADER.search(text)
    if not m:
        return {}
    start = m.end()
    end = _MATRIX_END.search(text, start)
    section = text[start:end.start()] if end else text[start:]

    overrides: dict[str, str] = {}
    tier_col = None
    for line in section.splitlines():
        line = line.strip()
        if not line.startswith("|") or not line.endswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if not cells or not cells[0]:
            continue
        # Header row -> locate the "tier" column.
        if tier_col is None and "tier" in [c.lower() for c in cells]:
            tier_col = [c.lower() for c in cells].index("tier")
            continue
        if "---" in cells[0] or set(cells[0]) <= {"-", ":"}:
            continue
        label = _match_label(skills, cells[0])
        if label is None:
            continue
        tier = cells[tier_col].lower() if tier_col is not None else (cells[-1].lower() if len(cells) > 1 else "")
        if tier in TIER_FACTOR:
            overrides[label] = tier
    return overrides


def build_keywords(workspace: Path) -> list[Keyword]:
    """Resolve final proficiency tiers and return the skill list.

    Priority: profile.md ``## Experience matrix`` > corpus mining > curated
    default. Corpus mining only ever *upgrades* a has-it skill's tier (never
    downgrades the curated default); the matrix is authoritative either way.
    """
    skills = [Keyword(sk.label, sk.aliases, sk.weight, sk.tier, sk.exclude) for sk in SKILLS]

    matrix = parse_experience_matrix(workspace, skills)
    mined: dict[str, str] = {}
    try:
        from .evidence import mine_tiers
        mined = mine_tiers(workspace, skills)
    except Exception:
        mined = {}

    for sk in skills:
        if sk.label in matrix:
            sk.tier = matrix[sk.label]
        elif sk.label in mined and sk.tier in _TIER_RANK:
            if _TIER_RANK.get(mined[sk.label], 99) < _TIER_RANK.get(sk.tier, 99):
                sk.tier = mined[sk.label]
    return skills
