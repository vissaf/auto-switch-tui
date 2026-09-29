"""Compatibility scoring and sorting.

Scoring model (evidence-grounded, deterministic):

For a job we first analyse *what the JD demands* — every skill from the
registry that appears in the title or body. Title mentions count 3x; body
mentions are capped at 3 occurrences each to resist keyword stuffing. Each
demanded skill contributes ``weight * prominence`` to the *demand pool* and
``weight * prominence * TIER_FACTOR[tier]`` to the *earned pool*.

The structural score is the earned/demand ratio (a proficiency-weighted
coverage), expressed as a percentage, plus a small role-fit bonus for
frontend/senior/lead/engineer titles. A skill the candidate lacks (e.g.
``foreign``/``unfamiliar``) drags coverage down in proportion to its demand,
while ``adjacent`` frameworks (React Native) only partially drag it.

Optionally a semantic-similarity component (see :mod:`.semantic`) is applied as
a one-sided, bounded *boost* so that synonym-rich JDs the structural keywords
miss still get credit — without disturbing the tier-based calibration.
"""

from __future__ import annotations

import re
from typing import Optional

from .models import Job
from .profile import TIER_FACTOR, TITLE_BONUS, TITLE_BONUS_CAP, TITLE_PATTERNS, Keyword, match_skills
from .util import strip_html

# Body mentions of a single skill are capped at this many for demand weighting.
_BODY_CAP = 3
_TITLE_MULT = 3

# Semantic similarity is applied as a one-sided, bounded boost (see _blend).
_LIFT_CAP = 12.0

# A JD with total demand below this magnitude has too little signal to be a
# confident match (e.g. one or two spurious keyword hits — "react" in a hotel
# posting, or a lone "B2B" tag). Its coverage is discounted proportionally so
# low-signal JDs can't ride a single high-weight keyword to a high score.
_DEMAND_FLOOR = 40.0

# Required-experience extraction from JDs. Ordered so ranges ("3-5 years")
# resolve before single numbers; bare "X years" without "of experience" is
# deliberately ignored (too many narrative false positives).
_REQUIRED_YEARS_RES = [
    re.compile(r"(\d+)\s*(?:-|–|—|to)\s*(\d+)\s*\+?\s*years?(?:\s+of\s+experience)?", re.I),
    re.compile(r"(\d+)\+\s*years?(?:\s+of\s+experience)?", re.I),
    re.compile(r"(\d+)\s*years?\s+of\s+experience", re.I),
    re.compile(r"(?:minimum|min|at least)\s+(?:of\s+)?(\d+)\s*\+?\s*years?", re.I),
]


def _required_years(text: str):
    """Minimum years of experience a JD demands, or None if unspecified."""
    lows: list[int] = []
    for pat in _REQUIRED_YEARS_RES:
        for m in pat.finditer(text):
            vals = [int(g) for g in m.groups() if g]
            lows.append(min(vals))
    return min(lows) if lows else None


def _seniority_factor(required: Optional[int], candidate: Optional[float]) -> float:
    """Coverage multiplier for level fit, relative to the candidate's years.

    Only penalizes when both numbers are known: a senior candidate applying to
    a junior/mid role is a real mismatch (comp regression, flight risk), while
    a junior candidate is never penalized for stretch applications.
    """
    if required is None or candidate is None:
        return 1.0
    if required < 3 and candidate >= 5:
        return 0.55   # junior role vs senior candidate — strong down-level
    if required <= 4 and candidate >= 5:
        return 0.85   # mid-level role vs senior candidate
    return 1.0


def _blend(structural: float, semantic: Optional[float], weight: float) -> float:
    """Blend a semantic-similarity component into the structural score.

    The blend is *one-sided*: semantic similarity can only confirm additional
    relevance (lifting a JD whose phrasing structural keywords missed), never
    subtract from a precise structural match. This keeps the tier-based
    calibration (e.g. React Native ~80s) authoritative while letting embeddings
    catch synonym-rich JDs.
    """
    if semantic is None or weight <= 0.0 or semantic <= structural:
        return structural
    lift = weight * (semantic - structural)
    return min(structural + min(lift, _LIFT_CAP), 100.0)


def _title_bonus(title: str) -> int:
    bonus = 0
    if TITLE_PATTERNS["frontend"].search(title):
        bonus += TITLE_BONUS["frontend"]
    if TITLE_PATTERNS["senior"].search(title):
        bonus += TITLE_BONUS["senior"]
    elif TITLE_PATTERNS["lead"].search(title):
        bonus += TITLE_BONUS["lead"]
    if TITLE_PATTERNS["staff"].search(title):
        bonus += TITLE_BONUS["staff"]
    if TITLE_PATTERNS["engineer"].search(title):
        bonus += TITLE_BONUS["engineer"]
    if TITLE_PATTERNS["junior"].search(title):
        bonus += TITLE_BONUS["junior"]
    elif TITLE_PATTERNS["mid"].search(title):
        bonus += TITLE_BONUS["mid"]
    return min(bonus, TITLE_BONUS_CAP)


def _structural(job: Job, by_label: dict[str, Keyword],
                candidate_years: Optional[float] = None) -> tuple[float, list[str]]:
    title = job.title or ""
    body = strip_html(job.description or "")

    skills = list(by_label.values())
    t_counts = match_skills(title, skills)
    b_counts = match_skills(body, skills)

    demand: dict[str, int] = {}
    for label, c in t_counts.items():
        demand[label] = demand.get(label, 0) + c * _TITLE_MULT
    for label, c in b_counts.items():
        demand[label] = demand.get(label, 0) + min(c, _BODY_CAP)

    earned = 0.0
    demanded = 0.0
    matched: list[str] = []
    for label, prom in demand.items():
        sk = by_label[label]
        w = sk.weight * prom
        demanded += w
        earned += w * TIER_FACTOR[sk.tier]
        matched.append(label)

    coverage = earned / demanded if demanded > 0 else 0.0
    # Level fit: a JD demanding far fewer years than the candidate has is a
    # down-level — shrink coverage proportionally (relative to the candidate).
    coverage *= _seniority_factor(_required_years(f"{title}. {body}"), candidate_years)
    signal = min(1.0, demanded / _DEMAND_FLOOR) if demanded > 0 else 0.0
    structural = 100.0 * coverage * signal + _title_bonus(title.lower())
    return min(100.0, structural), matched


def match_job(job: Job, keywords: list[Keyword], semantic: Optional[float] = None,
              semantic_weight: float = 0.25,
              candidate_years: Optional[float] = None) -> Job:
    """Score a job 0–100 and attach the matched-keyword labels."""
    by_label = {k.label: k for k in keywords}
    structural, matched = _structural(job, by_label, candidate_years)

    if semantic is not None and 0.0 < semantic_weight <= 1.0:
        # Junior-titled JDs get no semantic lift — it can only inflate a role
        # the candidate should be down-leveled against.
        if TITLE_PATTERNS["junior"].search(job.title or ""):
            semantic = None
    if semantic is not None and 0.0 < semantic_weight <= 1.0:
        final = _blend(structural, semantic, semantic_weight)
    else:
        final = structural

    job.compatibility = round(min(100.0, max(0.0, final)), 0)
    job.matched_keywords = matched[:14]
    return job


def rank_jobs(jobs: list[Job], keywords: list[Keyword], cfg: dict | None = None) -> list[Job]:
    """Score all jobs (structural + optional semantic blend) and sort desc.

    ``cfg`` carries the ``matching`` options (semantic on/off and blend weight)
    and the workspace (used to resolve the candidate's experience years).
    """
    cfg = cfg or {}
    matching = cfg.get("matching", {}) or {}
    semantic_weight = 0.0
    semantic_scores: dict[str, float] = {}

    if matching.get("semantic", True):
        try:
            from .semantic import semantic_scores as _sem
            workspace = cfg.get("workspace")
            semantic_scores = _sem(jobs, workspace) or {}
        except Exception:
            semantic_scores = {}
        semantic_weight = float(matching.get("semantic_weight", 0.25))

    candidate_years: Optional[float] = None
    try:
        from .profile import resolve_years
        workspace = cfg.get("workspace")
        if workspace:
            candidate_years = resolve_years(workspace)
    except Exception:
        candidate_years = None

    for j in jobs:
        sem = semantic_scores.get(j.id)
        if sem is not None and semantic_scores:
            match_job(j, keywords, semantic=sem, semantic_weight=semantic_weight,
                      candidate_years=candidate_years)
        else:
            match_job(j, keywords, semantic=None, candidate_years=candidate_years)

    jobs.sort(key=lambda j: (j.compatibility, j.salary_annual_usd or 0), reverse=True)
    return jobs


def sort_key_by(field: str):
    if field == "salary":
        return lambda j: (j.salary_annual_usd is not None, j.salary_annual_usd or 0, j.compatibility)
    if field == "posted":
        return lambda j: (j.posted_at or "", j.compatibility)
    if field == "company":
        return lambda j: (j.company.lower(), -j.compatibility)
    return lambda j: (j.compatibility, j.salary_annual_usd or 0)
