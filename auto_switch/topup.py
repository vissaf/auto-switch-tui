"""LLM top-up: export candidates for judging and ingest judged scores.

When ``matching.llm_topup.enabled`` is true, the ranked results are exported to
``output/llm-topup/candidates.{md,json}`` so that any LLM agent (via the
``job-match-topup`` opencode skill) can judge them against the profile + Work
experiences evidence and write back ``output/llm-topup/judged.json``.

The next run ingests ``judged.json`` and overrides each job's compatibility with
the LLM score (keeping the verdict string for the detail view).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from .models import Job

EXPORT_DIR_NAME = "llm-topup"


def _out_dir(workspace: str | Path) -> Path:
    return Path(workspace) / "output" / EXPORT_DIR_NAME


def export_candidates(
    jobs: list[Job], workspace: str | Path, top_n: int = 20,
    only_ids: Optional[set[str]] = None,
    description_limit: Optional[int] = None,
) -> Optional[Path]:
    if not jobs:
        return None
    out = _out_dir(workspace)
    out.mkdir(parents=True, exist_ok=True)

    if only_ids is not None:
        top = [j for j in jobs if j.id in only_ids][:top_n]
    else:
        top = jobs[:top_n]
    if not top:
        return None
    payload = serialize_candidates(top, description_limit=(description_limit or 1200))
    (out / "candidates.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")

    lines = ["# LLM Top-up Candidates", "",
             "Judge each job against the profile (`data/profile.md`) and the evidence in",
             "`data/work-experiences/`. Write back `judged.json` with `{id: {score, verdict}}`.",
             ""]
    for i, j in enumerate(top, 1):
        lines += [
            f"## {i}. {j.title} — {j.company}",
            "",
            f"- id: `{j.id}`",
            f"- location: {j.location or '—'}",
            f"- source: {j.source}",
            f"- current score: {j.compatibility:.0f}%",
            f"- matched: {', '.join(j.matched_keywords) or '—'}",
            f"- url: {j.url}",
            "",
            "### Description",
            "",
            j.description or "_No description provided._",
            "",
        ]
    (out / "candidates.md").write_text("\n".join(lines), encoding="utf-8")
    return out


def ingest_judged(workspace: str | Path) -> dict[str, dict]:
    path = _out_dir(workspace) / "judged.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return {k: v for k, v in data.items() if isinstance(v, dict) and "score" in v}


def judged_meta(workspace: str | Path) -> dict:
    """The `_meta` block of judged.json (skill version stamp), if present."""
    path = _out_dir(workspace) / "judged.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    meta = data.get("_meta")
    return meta if isinstance(meta, dict) else {}


def stamp_meta(workspace: str | Path, meta: dict) -> None:
    """Write `_meta` (e.g. skill hash) into judged.json without touching verdicts."""
    path = _out_dir(workspace) / "judged.json"
    data = {}
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    data["_meta"] = meta
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def merge_judged(workspace: str | Path, verdicts: dict[str, dict]) -> dict[str, dict]:
    """Merge new verdicts into judged.json (keeping entries for other job ids)."""
    existing = ingest_judged(workspace)
    for job_id, entry in verdicts.items():
        if not isinstance(entry, dict) or "score" not in entry:
            continue
        try:
            score = float(entry.get("score"))
        except (TypeError, ValueError):
            continue
        merged = {
            "score": round(max(0.0, min(100.0, score)), 0),
            "verdict": str(entry.get("verdict") or "").strip(),
        }
        level = str(entry.get("level") or "").strip().lower()
        if level in ("junior", "mid", "senior", "staff", "unknown"):
            merged["level"] = level
        existing[str(job_id)] = merged
    out = _out_dir(workspace)
    out.mkdir(parents=True, exist_ok=True)
    (out / "judged.json").write_text(json.dumps(existing, indent=2), encoding="utf-8")
    return existing


def serialize_candidates(jobs: list[Job], description_limit: int = 1200) -> list[dict]:
    """Machine-readable candidate payload (as written to candidates.json)."""
    return [
        {
            "id": j.id,
            "title": j.title,
            "company": j.company,
            "location": j.location,
            "url": j.url,
            "source": j.source,
            "structural_score": j.compatibility,
            "matched_keywords": j.matched_keywords,
            "description": (j.description or "")[:description_limit],
        }
        for j in jobs
    ]


def apply_judged(jobs: list[Job], judged: dict[str, dict]) -> None:
    """Override compatibility with the LLM score and attach the verdict."""
    if not judged:
        return
    for j in jobs:
        entry = judged.get(j.id)
        if not entry:
            continue
        try:
            score = float(entry.get("score"))
        except (TypeError, ValueError):
            continue
        j.llm_score = round(max(0.0, min(100.0, score)), 0)
        j.llm_verdict = str(entry.get("verdict") or "").strip()
        j.llm_level = str(entry.get("level") or "").strip()
        j.compatibility = j.llm_score
