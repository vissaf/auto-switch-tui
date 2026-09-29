"""First-run onboarding: create instance data and select the generation backend.

- ``ensure_profile`` — runs the identity screen when ``data/profile.md`` is
  missing, whitespace-only, or still on template placeholders.
- ``ensure_experience_years`` — one-time mini-screen asking for years of
  experience when an existing profile lacks the field (level-fit anchor).
- ``ensure_backend`` — runs the backend + cache screen once (persisted via
  ``generation.selected``); ``--backend`` flag can re-select it any time.
- ``select_locations`` — runs the target-areas screen on every interactive run.
"""

from __future__ import annotations

from pathlib import Path

from .paths import profile_path


def profile_is_ready(workspace: str | Path) -> bool:
    path = profile_path(workspace)
    if not path.exists():
        return False
    try:
        text = path.read_text(encoding="utf-8").strip()
    except Exception:
        return False
    if len(text) < 200:  # whitespace-only or a stub
        return False
    from .profile import load_profile

    data = load_profile(Path(workspace))
    name = (data.get("name") or "").strip()
    if not name or name.startswith("<"):
        return False
    return True


def ensure_profile(workspace: str | Path, cfg: dict) -> bool:
    """True = profile usable (created or pre-existing). False = user aborted."""
    if profile_is_ready(workspace):
        return True
    from .ui.setup import ProfileOnboardingApp

    return bool(ProfileOnboardingApp(workspace).run())


def profile_has_years(workspace: str | Path) -> bool:
    """Whether profile.md records years of experience (the level-fit anchor)."""
    import re

    path = profile_path(workspace)
    if not path.exists():
        return False
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return False
    return bool(re.search(r"^- Years of experience:\s*\S", text, re.M))


def ensure_experience_years(workspace: str | Path, cfg: dict) -> bool:
    """One-time: ask for years of experience when profile.md lacks the field.

    The value anchors the matcher's level fit (relative seniority caps). Users
    can skip — matching then falls back to corpus date inference or no caps.
    Never blocks: aborts still return True (the run continues).
    """
    if profile_has_years(workspace):
        return True
    from .ui.setup import ExperienceYearsApp

    ExperienceYearsApp(workspace).run()
    return True


def ensure_backend(cfg: dict) -> bool:
    """True = backend chosen (or persisted earlier). False = user aborted."""
    if (cfg.get("generation") or {}).get("selected"):
        return True
    from .backends import detect_agents
    from .ui.setup import BackendSetupApp

    return bool(BackendSetupApp(cfg, detect_agents()).run())


def select_locations(cfg: dict) -> bool:
    """True = areas chosen. False = user quit before fetching."""
    from .ui.setup import LocationsApp

    return bool(LocationsApp(cfg).run())


def first_run_complete(cfg: dict) -> bool:
    """Backend selection done and profile ready for the configured workspace."""
    return bool((cfg.get("generation") or {}).get("selected"))
