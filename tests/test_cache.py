"""Fetch cache behavior: keying, TTL, disabled flag, roundtrip."""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from auto_switch import cache  # noqa: E402
from auto_switch.models import Job  # noqa: E402


@pytest.fixture(autouse=True)
def tmp_cache_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(cache, "CACHE_DIR", tmp_path)
    yield tmp_path


def _cfg(**over):
    cfg = {
        "locations": ["UAE"],
        "search_terms": ["react"],
        "providers": {"remotive": True, "linkedin": False},
        "jobspy": {"results_wanted": 25},
        "companies": {"greenhouse": ["airbnb"]},
        "cache": {"ttl_minutes": 30},
    }
    cfg.update(over)
    return cfg


def _job(i):
    return Job(id=f"j{i}", title=f"T{i}", company="C", location="Dubai", url="https://x")


def test_key_stable_across_runs():
    assert cache.cache_file(_cfg()) == cache.cache_file(_cfg())


def test_key_changes_with_locations():
    assert cache.cache_file(_cfg(locations=["USA"])) != cache.cache_file(_cfg())


def test_key_changes_with_providers():
    cfg2 = _cfg(providers={"remotive": False, "linkedin": False})
    assert cache.cache_file(cfg2) != cache.cache_file(_cfg())


def test_roundtrip():
    jobs = [_job(0), _job(1)]
    cache.save(_cfg(), jobs)
    hit = cache.load(_cfg())
    assert hit is not None
    loaded, age = hit
    assert [j.id for j in loaded] == ["j0", "j1"]
    assert 0 <= age < 1


def test_expired_ttl():
    jobs = [_job(0)]
    cache.save(_cfg(cache={"ttl_minutes": 0}), jobs)
    time.sleep(0.05)
    assert cache.load(_cfg(cache={"ttl_minutes": 0})) is None


def test_disabled_skips_read_and_write(tmp_cache_dir):
    cfg = _cfg(cache={"ttl_minutes": 30, "disabled": True})
    assert cache.load(cfg) is None
    cache.save(cfg, [_job(0)])
    assert not list(tmp_cache_dir.glob("fetch-*.json"))


def test_corrupt_file_returns_none():
    path = cache.cache_file(_cfg())
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not json")
    assert cache.load(_cfg()) is None
