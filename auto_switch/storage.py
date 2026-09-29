"""Saved jobs + job-description export."""

from __future__ import annotations

import json
from pathlib import Path

from .config import CONFIG_DIR
from .models import Job
from .util import slugify, strip_html

SAVED_PATH = CONFIG_DIR / "saved.json"


def _read_saved() -> list[Job]:
    if not SAVED_PATH.exists():
        return []
    try:
        data = json.loads(SAVED_PATH.read_text(encoding="utf-8"))
        return [Job.from_dict(d) for d in data]
    except Exception:
        return []


def _write_saved(jobs: list[Job]) -> None:
    SAVED_PATH.parent.mkdir(parents=True, exist_ok=True)
    SAVED_PATH.write_text(
        json.dumps([j.to_dict() for j in jobs], indent=2), encoding="utf-8"
    )


def load_saved() -> list[Job]:
    return _read_saved()


def is_saved(job: Job) -> bool:
    return any(j.id == job.id for j in _read_saved())


def toggle_save(job: Job) -> bool:
    """Add or remove a job from saved. Returns True if now saved."""
    jobs = _read_saved()
    if any(j.id == job.id for j in jobs):
        _write_saved([j for j in jobs if j.id != job.id])
        return False
    jobs.insert(0, job)
    _write_saved(jobs)
    return True


def export_jd(job: Job, workspace: str | Path) -> Path:
    """Write the job description to output/jds/<slug>.md and return the path."""
    if job.source == "instahyre" and len(job.description or "") < 400:
        from .providers.instahyre import enrich_instahyre_job_sync

        try:
            enrich_instahyre_job_sync(job)
        except Exception:
            pass

    out_dir = Path(workspace) / "output" / "jds"
    out_dir.mkdir(parents=True, exist_ok=True)
    slug = slugify(f"{job.company}-{job.title}")
    path = out_dir / f"{slug}.md"

    lines = [
        f"# {job.title}",
        "",
        f"- **Company:** {job.company}",
        f"- **Location:** {job.display_location}",
        f"- **Source:** {job.source}",
        f"- **URL:** {job.url}",
    ]
    if job.salary_text:
        lines.append(f"- **Salary:** {job.salary_text}")
    if job.posted_at:
        lines.append(f"- **Posted:** {job.posted_at}")
    lines += ["", "## Job Description", "", strip_html(job.description).strip() or "_No description provided._"]

    path.write_text("\n".join(lines), encoding="utf-8")
    return path
