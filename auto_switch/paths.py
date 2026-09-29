"""Canonical data locations inside the workspace.

The engine (auto_switch) and the bundled agent skills (.agents/skills) share
these constants so the user's instance data can live in one predictable place:

- ``data/profile.md``            — identity, skills, experience matrix
- ``data/work-experiences/``     — per-employer evidence (RESUME_BULLETS.md)
"""

from __future__ import annotations

from pathlib import Path

DATA_DIR_NAME = "data"
PROFILE_FILENAME = "profile.md"
EXPERIENCES_DIR_NAME = "work-experiences"
OUTPUT_DIR_NAME = "output"


def data_dir(workspace: str | Path) -> Path:
    return Path(workspace) / DATA_DIR_NAME


def profile_path(workspace: str | Path) -> Path:
    return data_dir(workspace) / PROFILE_FILENAME


def experiences_dir(workspace: str | Path) -> Path:
    return data_dir(workspace) / EXPERIENCES_DIR_NAME


def output_dir(workspace: str | Path) -> Path:
    return Path(workspace) / OUTPUT_DIR_NAME
