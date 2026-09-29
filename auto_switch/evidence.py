"""Corpus mining: derive per-skill proficiency tiers from the user's evidence.

Scans ``data/profile.md`` and every ``PORTFOLIO.md`` / ``RESUME_BULLETS.md`` under
``data/work-experiences/`` and, for each skill, counts:

- ``projects`` — how many distinct project folders mention the skill
- ``mentions`` — total occurrences across the corpus
- ``strong``   — occurrences preceded by an authorship/leadership verb

These map to a has-it tier (core/strong/secondary/familiar). The *"Notes for
accuracy (private)"* sections in the bullet files are stripped first so that
negations ("did not work in X", "not the architect of Y") and other people's
contributions never inflate the signal.

Mining is deliberately conservative: it can only *upgrade* a curated default
tier (see profile.build_keywords), never downgrade it.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Optional

from .profile import Keyword, _pattern_for
from .paths import experiences_dir, profile_path

# Verbs that signal senior/ownership-level work vs. contributor-level work.
_STRONG = {
    "designed", "architected", "led", "owned", "authored", "created",
    "introduced", "built", "delivered", "drove", "established", "pioneered",
    "designed and", "architected and", "owned end",
}
_WEAK = {
    "implemented", "assisted", "contributed", "co-built", "co built", "helped",
    "fixed", "extended", "integrated", "migrated", "rebuilt", "updated",
    "refactored", "debugged", "maintained",
}

# Private "notes for accuracy" sections — drop everything from here onward.
_NOTES_RE = re.compile(r"^#{1,3}\s*(notes for accuracy|notes for recruiters|notes)\b", re.I | re.M)


def _cache_dir() -> Path:
    d = Path.home() / ".cache" / "auto-switch"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _corpus_fingerprint(files: list[Path], skills: list[Keyword]) -> str:
    parts: list[str] = []
    for f in files:
        try:
            st = f.stat()
            parts.append(f"{f}:{st.st_mtime_ns}:{st.st_size}")
        except Exception:
            parts.append(str(f))
    for sk in skills:
        parts.append(f"{sk.label}:{sk.aliases}:{sk.exclude}")
    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()[:16]


def _strip_notes(text: str) -> str:
    m = _NOTES_RE.search(text)
    return text[: m.start()] if m else text


def _project_name(path: Path) -> str:
    # "data/work-experiences/01. Acme Corp/Mobile App/mobile-app-client/PORTFOLIO.md"
    # -> "mobile-app-client" (the innermost project dir).
    return path.parent.name


def _scan(text: str, skills: list[Keyword]) -> dict[str, tuple[int, int]]:
    """Return {label: (mentions, strong_mentions)} for one document."""
    low = text.lower()
    out: dict[str, tuple[int, int]] = {}
    for sk in skills:
        total = 0
        strong = 0
        for alias in sk.aliases:
            pat = _pattern_for(alias, sk.exclude)
            for m in pat.finditer(low):
                total += 1
                before = low[max(0, m.start() - 28): m.start()]
                if any(w in before for w in _STRONG) and not any(w in before for w in _WEAK):
                    strong += 1
        if total:
            out[sk.label] = (total, strong)
    return out


def _tier_from(projects: int, mentions: int, strong: int) -> Optional[str]:
    if projects >= 4 and mentions >= 15 and strong >= 4:
        return "core"
    if projects >= 2 and mentions >= 6 and strong >= 1:
        return "strong"
    if projects >= 1 and mentions >= 2:
        return "secondary"
    if mentions >= 1:
        return "familiar"
    return None


def mine_tiers(workspace: Path, skills: list[Keyword]) -> dict[str, str]:
    """Compute has-it tiers from the evidence corpus -> {label: tier}."""
    root = Path(workspace)
    exp_dir = experiences_dir(root)

    files: list[Path] = []
    if exp_dir.exists():
        for name in ("PORTFOLIO.md", "RESUME_BULLETS.md"):
            files.extend(sorted(exp_dir.glob(f"**/{name}")))
    profile = profile_path(root)
    if profile.exists():
        files.insert(0, profile)

    cache_dir = _cache_dir()
    sig = _corpus_fingerprint(files, skills)
    cache_file = cache_dir / f"tiers_{sig}.json"
    if cache_file.exists():
        try:
            return json.loads(cache_file.read_text(encoding="utf-8"))
        except Exception:
            pass

    per_skill: dict[str, tuple[int, int, int]] = {}  # label -> (projects, mentions, strong)
    project_hits: dict[str, set[str]] = {}

    for f in files:
        try:
            text = _strip_notes(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        project = _project_name(f) if exp_dir.exists() and str(f).startswith(str(exp_dir)) else "profile"
        for label, (mentions, strong) in _scan(text, skills).items():
            p, m, s = per_skill.get(label, (0, 0, 0))
            if label not in project_hits:
                project_hits[label] = set()
            is_new = project not in project_hits[label]
            if is_new:
                project_hits[label].add(project)
                p += 1
            per_skill[label] = (p, m + mentions, s + strong)

    tiers: dict[str, str] = {}
    for label, (p, m, s) in per_skill.items():
        tier = _tier_from(p, m, s)
        if tier:
            tiers[label] = tier

    try:
        cache_file.write_text(json.dumps(tiers, indent=2), encoding="utf-8")
        for old in cache_dir.glob("tiers_*.json"):
            if old != cache_file:
                old.unlink(missing_ok=True)
    except Exception:
        pass

    return tiers
