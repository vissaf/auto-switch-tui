"""Onboarding readiness checks: missing / empty / placeholder / real profiles."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from auto_switch import onboard  # noqa: E402
from auto_switch.paths import data_dir  # noqa: E402

REAL_PROFILE = """# Jane Doe — Canonical Profile

## Identity

- Name: Jane Doe
- Headline: Frontend Engineer
- Email: jane@example.com

## Professional summary

Six years building web applications with React.

## Skills

- Frontend: React, TypeScript

## Experience matrix

| Skill | Tier |
|-------|------|
| React | core |
"""

PLACEHOLDER_PROFILE = """# <Your Name> — Canonical Profile

## Identity

- Name: <Your Name>
- Headline: <Your Target Title, e.g. Senior Frontend Engineer>
- Email: <you@example.com>
"""


def _make_profile(tmp_path, text=None):
    data = data_dir(tmp_path)
    data.mkdir(parents=True, exist_ok=True)
    profile = data / "profile.md"
    if text is not None:
        profile.write_text(text, encoding="utf-8")
    return tmp_path


def test_missing_profile_not_ready(tmp_path):
    assert not onboard.profile_is_ready(tmp_path)


def test_empty_profile_not_ready(tmp_path):
    ws = _make_profile(tmp_path, "\n   \n")
    assert not onboard.profile_is_ready(ws)


def test_stub_profile_not_ready(tmp_path):
    ws = _make_profile(tmp_path, "# Profile\n\n")
    assert not onboard.profile_is_ready(ws)


def test_placeholder_profile_not_ready(tmp_path):
    ws = _make_profile(tmp_path, PLACEHOLDER_PROFILE)
    assert not onboard.profile_is_ready(ws)


def test_real_profile_ready(tmp_path):
    ws = _make_profile(tmp_path, REAL_PROFILE)
    assert onboard.profile_is_ready(ws)
