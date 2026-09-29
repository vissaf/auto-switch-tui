"""Level-fit logic: years resolution, required-years parsing, judge expiry."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from auto_switch.profile import TITLE_PATTERNS, resolve_years  # noqa: E402
from auto_switch.ranking import _required_years, _seniority_factor  # noqa: E402
from auto_switch.topup import ingest_judged, judged_meta  # noqa: E402


def _ws_with_profile(tmp_path, identity: str = "") -> Path:
    (tmp_path / "data").mkdir(exist_ok=True)
    profile = (
        "# Test\n\n## Identity\n\n- Name: Test\n- Headline: Senior Frontend Engineer\n"
        f"{identity}- Email: t@example.com\n\n## Skills\n\n- Frontend: React\n"
    )
    (tmp_path / "data" / "profile.md").write_text(profile, encoding="utf-8")
    return tmp_path


def test_resolve_years_from_profile_field(tmp_path):
    ws = _ws_with_profile(tmp_path, "- Years of experience: 6+\n")
    assert resolve_years(ws) == 6.0


def test_resolve_years_corpus_fallback(tmp_path):
    ws = _ws_with_profile(tmp_path)
    exp = tmp_path / "data" / "work-experiences" / "acme"
    exp.mkdir(parents=True)
    (exp / "RESUME_BULLETS.md").write_text("Shipped the platform (Jan 2020 – Mar 2024).\n")
    assert resolve_years(ws) == 5.0


def test_resolve_years_unknown(tmp_path):
    ws = _ws_with_profile(tmp_path)
    assert resolve_years(ws) is None


def test_required_years_parsing():
    assert _required_years("3+ years of experience with React") == 3
    assert _required_years("minimum 5 years of experience") == 5
    assert _required_years("5-8 years of experience") == 5
    assert _required_years("1-2 years experience required") == 1
    assert _required_years("worked 5 years ago on a legacy app") is None
    assert _required_years("we value experience") is None


def test_seniority_factor_relative():
    assert _seniority_factor(2, 6) == 0.55   # junior vs senior candidate
    assert _seniority_factor(4, 6) == 0.85   # mid vs senior candidate
    assert _seniority_factor(5, 6) == 1.0    # senior-to-senior
    assert _seniority_factor(2, 1) == 1.0    # junior candidate, no penalty
    assert _seniority_factor(None, 6) == 1.0
    assert _seniority_factor(3, None) == 1.0


def test_title_level_patterns():
    assert TITLE_PATTERNS["junior"].search("SDE I (Frontend)")
    assert TITLE_PATTERNS["junior"].search("React JS Developer -SDE 1")
    assert TITLE_PATTERNS["junior"].search("Fresher React Developer")
    assert not TITLE_PATTERNS["junior"].search("Senior Frontend Engineer")
    assert TITLE_PATTERNS["mid"].search("Developer II")
    assert not TITLE_PATTERNS["mid"].search("Senior Developer")


def test_judge_stale_verdicts_wiped(tmp_path):
    from auto_switch.judge import judge_top, _skill_sha
    from auto_switch.models import Job

    ws = tmp_path
    out = ws / "output" / "llm-topup"
    out.mkdir(parents=True)
    (out / "judged.json").write_text(
        '{"_meta": {"skill_sha": "stale"}, "old-1": {"score": 95, "verdict": "old"}}',
        encoding="utf-8",
    )

    jobs = [Job(id=f"j{i}", title=f"React Developer {i}", company=f"C{i}",
                location="India", url=f"https://x/{i}",
                description="Senior React TypeScript role, 5+ years of experience",
                source="test", compatibility=90 - i) for i in range(5)]

    cfg = {"workspace": str(ws), "matching": {"judge": {"enabled": True, "top_n": 3}},
           "generation": {"backend": "api"}}

    class FakeAPI:
        name = "api"

        def judge_verdicts(self, workspace, candidates, cfg=None):
            return {c["id"]: {"score": 80, "level": "senior", "verdict": "ok"} for c in candidates}

    with patch("auto_switch.judge.resolve_backend", return_value=FakeAPI()):
        status = judge_top(jobs, cfg, ws)

    assert "3/3" in status, status
    judged = ingest_judged(ws)
    assert "old-1" not in judged, "stale verdict must be wiped"
    assert judged_meta(ws).get("skill_sha") == _skill_sha(ws)
    levels = {j.id: j.llm_level for j in jobs}
    for i in range(3):
        assert levels[f"j{i}"] == "senior"
        assert {j.id: j.compatibility for j in jobs}[f"j{i}"] == 80
    for i in (3, 4):
        assert levels[f"j{i}"] == ""


def test_judge_skips_when_all_cached(tmp_path):
    from auto_switch.judge import judge_top, _skill_sha
    from auto_switch.models import Job

    ws = tmp_path
    out = ws / "output" / "llm-topup"
    out.mkdir(parents=True)
    (out / "judged.json").write_text(
        '{"_meta": {"skill_sha": "%s"}, "j0": {"score": 77, "level": "senior", "verdict": "x"}}'
        % _skill_sha(ws),
        encoding="utf-8",
    )
    jobs = [Job(id="j0", title="React Developer", company="C",
                location="India", url="https://x/0", description="React",
                source="test", compatibility=50)]
    cfg = {"workspace": str(ws), "matching": {"judge": {"enabled": True, "top_n": 3}},
           "generation": {"backend": "api"}}

    class Boom:
        name = "api"

        def judge_verdicts(self, *a, **k):
            raise AssertionError("should not be called — all cached")

    with patch("auto_switch.judge.resolve_backend", return_value=Boom()):
        status = judge_top(jobs, cfg, ws)
    assert "cached" in status
    assert jobs[0].compatibility == 77


def test_judge_includes_all_jobs_above_min_score(tmp_path):
    from auto_switch.judge import judge_top
    from auto_switch.models import Job

    ws = tmp_path
    jobs = [
        Job(id=f"j{i}", title=f"Dev {i}", company=f"C{i}", location="Remote",
            url=f"https://x/{i}", description="React TypeScript", source="test",
            compatibility=score)
        for i, score in enumerate([90, 85, 80, 78, 75, 70, 60, 50])
    ]

    cfg = {
        "workspace": str(ws),
        "matching": {"judge": {"enabled": True, "min_score": 75.0, "top_n": 2, "max_n": 20}},
        "generation": {"backend": "api"},
    }

    class FakeAPI:
        name = "api"

        def judge_verdicts(self, workspace, candidates, cfg=None):
            return {c["id"]: {"score": 85, "level": "senior", "verdict": "verified"} for c in candidates}

    with patch("auto_switch.judge.resolve_backend", return_value=FakeAPI()):
        status = judge_top(jobs, cfg, ws)

    # 5 jobs are >= 75%, so even though top_n=2, all 5 must be judged
    assert "5/5 new verdicts" in status
    levels = {j.id: j.llm_level for j in jobs}
    for i in range(5):
        assert levels[f"j{i}"] == "senior"
    for i in range(5, 8):
        assert levels[f"j{i}"] == ""

