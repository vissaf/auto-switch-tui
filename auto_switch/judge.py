"""LLM judging: re-score top candidates via the configured backend.

Routes through whatever backend onboarding selected — an agent CLI
(opencode/claude/pi/deepseek) runs the bundled ``job-match-topup`` skill and
writes ``judged.json`` itself, while the direct API backend scores the batch in
one JSON-mode call and the verdicts are merged here. Verdicts persist by job
id, so re-runs only judge new candidates.

The offline (structural + semantic) scores remain the base layer: they pick
the top-N the judge sees and stay authoritative whenever judging is disabled
or the judge call fails.

Cached verdicts are keyed to the judge skill's content: when the skill file
changes, old verdicts expire and candidates are re-judged under the new
calibration.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from .backends import resolve_backend
from .backends.base import skill_path
from .topup import (
    _out_dir,
    apply_judged,
    export_candidates,
    ingest_judged,
    judged_meta,
    merge_judged,
    serialize_candidates,
    stamp_meta,
)

# Requirements live at the top of a JD; the tail is boilerplate. Judging on
# the head keeps each agent run fast without losing the decision signal.
_JD_CHARS_FOR_JUDGE = 3000


def _skill_sha(workspace: Path) -> str:
    path = skill_path(workspace, "judge")
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return ""
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def _candidate_context(workspace: Path) -> str:
    """Candidate level anchor read from data (never hard-coded)."""
    from .profile import load_profile, resolve_years

    data = load_profile(workspace)
    headline = (data.get("headline") or "").strip() or "unknown"
    years = resolve_years(workspace)
    years_s = f"{years:g}+" if years is not None else "unknown"
    return (
        f"Candidate level anchor (from data/profile.md): target headline "
        f"'{headline}', {years_s} years of professional experience. If years "
        "are unknown, judge stack coverage only — apply no level caps."
    )


def _judge_message(workspace: Path, count: int) -> str:
    return (
        "Run the bundled job-match-topup skill "
        f"(.agents/skills/job-match-topup) on the {count} candidates exported "
        "to output/llm-topup/candidates.json. Judge ONLY those candidates "
        "against data/profile.md and data/work-experiences/. Append your "
        "results ({id: {score, level, verdict}}) to "
        "output/llm-topup/judged.json, preserving any entries already present "
        "for other ids. Follow the skill's two-axis calibration "
        "(stack coverage x level fit) exactly.\n\n"
        f"{_candidate_context(workspace)}\n\n"
        "Reply with one line: how many candidates you judged."
    )


def judge_top(jobs, cfg: dict, workspace: Path) -> str | None:
    """Judge unjudged jobs among the top-N via the configured backend.

    Returns a one-line status for the progress display, or ``None`` when
    judging is disabled. Never raises — failures fall back to offline scores.
    """
    matching = cfg.get("matching", {}) or {}
    judge_cfg = matching.get("judge", {}) or {}
    if not judge_cfg.get("enabled"):
        return None

    min_score = judge_cfg.get("min_score")
    top_n = int(judge_cfg.get("top_n") or 15)
    max_n = int(judge_cfg.get("max_n") or 40)

    sha = _skill_sha(workspace)
    judged = ingest_judged(workspace)
    if sha and judged_meta(workspace).get("skill_sha") != sha:
        # Skill calibration changed — existing verdicts are stale. Wipe them
        # so the agent (which preserves other ids) can't keep old scores alive.
        path = _out_dir(workspace) / "judged.json"
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        judged = {}
    if judged:
        apply_judged(jobs, judged)

    if min_score is not None:
        min_score_val = float(min_score)
        eligible_ids: set[str] = set()
        for j in jobs:
            if (j.compatibility or 0) >= min_score_val:
                eligible_ids.add(j.id)
        for j in jobs[:top_n]:
            eligible_ids.add(j.id)
        eligible_jobs = [j for j in jobs if j.id in eligible_ids][:max_n]
    else:
        eligible_jobs = jobs[:top_n]

    unjudged = [j for j in eligible_jobs if j.id not in judged]
    if not unjudged:
        return f"match judge: {len(judged)} cached verdicts applied"

    out = export_candidates(
        jobs, workspace, top_n=len(eligible_jobs), only_ids={j.id for j in unjudged},
        description_limit=_JD_CHARS_FOR_JUDGE,
    )
    backend = resolve_backend(cfg)

    if getattr(backend, "name", None) == "api":
        try:
            verdicts = backend.judge_verdicts(
                workspace,
                serialize_candidates(unjudged, description_limit=_JD_CHARS_FOR_JUDGE),
                cfg,
            )
        except Exception as exc:  # noqa: BLE001 — judge is best-effort
            return f"match judge failed ({exc}); keeping offline scores"
        if not verdicts:
            return "match judge returned no verdicts; keeping offline scores"
        merge_judged(workspace, verdicts)
        if sha:
            stamp_meta(workspace, {"skill_sha": sha})
    else:
        candidates_md = Path(out) / "candidates.md" if out else None
        if candidates_md is None or not candidates_md.exists():
            return "match judge: no candidates exported; keeping offline scores"
        timeout = int(judge_cfg.get("timeout") or 1200)
        run_cfg = {
            **cfg,
            "generation": {**(cfg.get("generation") or {}), "timeout": timeout},
        }
        try:
            res = backend.generate(workspace, candidates_md, "judge",
                                   _judge_message(workspace, len(unjudged)), run_cfg)
        except Exception as exc:  # noqa: BLE001
            return f"match judge failed ({exc}); keeping offline scores"
        if res.returncode != 0:
            return f"match judge failed (rc={res.returncode}); keeping offline scores"
        if sha:
            stamp_meta(workspace, {"skill_sha": sha})

    judged = ingest_judged(workspace)
    apply_judged(jobs, judged)
    jobs.sort(key=lambda j: (j.compatibility, j.salary_annual_usd or 0), reverse=True)
    fresh = sum(1 for j in unjudged if j.id in judged)
    return f"match judge: {fresh}/{len(unjudged)} new verdicts via {backend.name}"
