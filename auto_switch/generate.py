"""Hand off a job to the configured generation backend (agent CLI or API)."""

from __future__ import annotations

from pathlib import Path

from .backends import resolve_backend
from .backends.base import GenerationResult


def _match_context(job) -> str:
    """Serialize the matcher's read on this job so the generator can reuse it."""
    lines = [f"Match score: {job.compatibility:.0f}%"]
    if getattr(job, "matched_keywords", None):
        lines.append(f"Matched skills (evidence-backed): {', '.join(job.matched_keywords)}")
    if getattr(job, "llm_score", None) is not None:
        lines.append(f"LLM judge score: {job.llm_score:.0f}% — {job.llm_verdict or ''}")
    return "\n".join(lines)


def _workspace_path(cfg: dict) -> Path:
    return Path(cfg["workspace"])


def generate_resume(cfg: dict, job, jd_path: Path) -> GenerationResult:
    msg = (
        f"Generate an ATS-friendly resume tailored to the job description in "
        f"{jd_path.name} (role: '{job.title}' at {job.company}), following the "
        f"bundled resume-builder skill (.agents/skills/resume-builder). First "
        f"complete the mandatory Step 2.5 match analysis (JD needs -> evidence "
        f"map -> gap policy) and save it to output/<Company>/match-analysis.md, "
        f"then write the resume. Write the Markdown + PDF into the output/ "
        f"directory.\n\n"
        f"Matcher context (use as a starting point, verify against the evidence):\n"
        f"{_match_context(job)}"
    )
    backend = resolve_backend(cfg)
    return backend.generate(_workspace_path(cfg), jd_path, "resume", msg, cfg)


def generate_cover_letter(cfg: dict, job, jd_path: Path) -> GenerationResult:
    msg = (
        f"Write a tailored cover letter for the role '{job.title}' at {job.company} "
        f"using the job description in {jd_path.name}, following the bundled "
        f"cover-letter skill (.agents/skills/cover-letter). First complete the "
        f"mandatory Step 2 match analysis (JD asks -> evidence map -> gap policy) "
        f"and save it to output/<Company>/match-analysis.md, then write the "
        f"letter. Write the Markdown + PDF into the output/ directory.\n\n"
        f"Matcher context (use as a starting point, verify against the evidence):\n"
        f"{_match_context(job)}"
    )
    backend = resolve_backend(cfg)
    return backend.generate(_workspace_path(cfg), jd_path, "cover-letter", msg, cfg)
