"""Backend registry: resolution, detection shape, adapter command templates."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from auto_switch.backends import (  # noqa: E402
    BACKEND_BY_NAME,
    AGENT_BACKENDS,
    backend_status,
    detect_agents,
    resolve_backend,
)
from auto_switch.backends import base  # noqa: E402
from auto_switch.backends.api import APIBackend  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def test_registry_has_all_backends():
    assert set(BACKEND_BY_NAME) == {"antigravity", "agy", "opencode", "claude", "pi", "deepseek", "api"}
    assert BACKEND_BY_NAME["agy"] is BACKEND_BY_NAME["antigravity"]


def test_detect_agents_shape():
    detected = detect_agents()
    assert set(detected) == {"antigravity", "opencode", "claude", "pi", "deepseek"}
    assert all(isinstance(v, bool) for v in detected.values())


def test_explicit_choice_wins(monkeypatch):
    cfg = {"generation": {"backend": "api"}}
    backend = resolve_backend(cfg)
    assert isinstance(backend, APIBackend)

    cfg_agy = {"generation": {"backend": "agy"}}
    backend_agy = resolve_backend(cfg_agy)
    assert backend_agy.name == "antigravity"

    cfg_anti = {"generation": {"backend": "antigravity"}}
    backend_anti = resolve_backend(cfg_anti)
    assert backend_anti.name == "antigravity"


def test_auto_falls_back_to_api_when_no_cli(monkeypatch):
    for cls in AGENT_BACKENDS:
        monkeypatch.setattr(cls, "detect", lambda self: False)
    cfg = {"generation": {"backend": "auto"}}
    assert isinstance(resolve_backend(cfg), APIBackend)


def test_auto_prefers_first_detected_agent(monkeypatch):
    monkeypatch.setattr(AGENT_BACKENDS[0], "detect", lambda self: True)
    for cls in AGENT_BACKENDS[1:]:
        monkeypatch.setattr(cls, "detect", lambda self: False)
    backend = resolve_backend({"generation": {"backend": "auto"}})
    assert isinstance(backend, AGENT_BACKENDS[0])


def test_skill_path_falls_back_to_bundled():
    path = base.skill_path(ROOT, "resume")
    assert path.exists()
    assert path.name == "SKILL.md"
    assert "resume-builder" in path.parts


def test_skill_text_nonempty():
    assert "Never put a lie" in base.skill_text(ROOT, "resume")


def test_backend_status_line():
    cfg = {"generation": {"backend": "api"}}
    assert "api" in backend_status(cfg)


def test_adapter_command_shapes():
    jd = ROOT / "output" / "jds" / "acme-dev.md"
    msg = "build the resume"
    opencode_cmd = BACKEND_BY_NAME["opencode"]().build_command(ROOT, jd, "resume", msg)
    assert opencode_cmd[0] == "opencode" and "--dir" in opencode_cmd and "--auto" in opencode_cmd

    claude_cmd = BACKEND_BY_NAME["claude"]().build_command(ROOT, jd, "resume", msg)
    assert claude_cmd[:2] == ["claude", "-p"]
    assert "resume-builder" in claude_cmd[-1]

    pi_cmd = BACKEND_BY_NAME["pi"]().build_command(ROOT, jd, "resume", msg)
    assert "-a" in pi_cmd and "-p" in pi_cmd and "--skill" in pi_cmd

    dsh_cmd = BACKEND_BY_NAME["deepseek"]().build_command(ROOT, jd, "resume", msg)
    assert dsh_cmd[:3] == ["dsh", "--profile", "headless"]

    agy_cmd = BACKEND_BY_NAME["antigravity"]().build_command(ROOT, jd, "resume", msg)
    assert agy_cmd[0] == "agy"
    assert "--add-dir" in agy_cmd
    assert "--print-timeout" in agy_cmd
    assert "600s" in agy_cmd
    assert "--dangerously-skip-permissions" in agy_cmd
    assert "--print" in agy_cmd
    assert "resume-builder" in agy_cmd[-1]

    # Test with custom generation cfg (timeout alignment, model, and effort)
    custom_cfg = {
        "generation": {
            "timeout": 900,
            "model": "gemini-2.5-pro",
            "effort": "high",
        }
    }
    custom_cmd = BACKEND_BY_NAME["antigravity"]().build_command(
        ROOT, jd, "resume", msg, cfg=custom_cfg
    )
    assert "--print-timeout" in custom_cmd
    assert custom_cmd[custom_cmd.index("--print-timeout") + 1] == "900s"
    assert "--model" in custom_cmd
    assert custom_cmd[custom_cmd.index("--model") + 1] == "gemini-2.5-pro"
    assert "--effort" in custom_cmd
    assert custom_cmd[custom_cmd.index("--effort") + 1] == "high"


def test_templated_runner_missing_binary(tmp_path):
    backend = BACKEND_BY_NAME["opencode"]()
    result = backend.generate(
        tmp_path, tmp_path / "jd.md", "resume", "hi", {"generation": {"timeout": 5}}
    )
    if backend.detect():
        pytest.skip("opencode present on this machine")
    assert result.returncode == 127


def test_load_config_backend_flag_does_not_contaminate_providers(tmp_path):
    from types import SimpleNamespace
    import json
    from auto_switch.config import load_config, save_config

    cfg_file = tmp_path / "config.json"
    initial_cfg = {
        "providers": {"linkedin": True, "remotive": True, "greenhouse": True},
        "max_jobs": 0,
        "generation": {"backend": "auto"},
    }
    save_config(initial_cfg, cfg_file)

    args = SimpleNamespace(
        config=str(cfg_file),
        provider="remotive",
        max=2,
        backend="agy",
        list=True,
        location=None,
        workspace_override=None,
        semantic=None,
        topup=None,
        judge=None,
        setup=False,
        cache_ttl=None,
        no_cache=False,
    )
    loaded = load_config(tmp_path, args)
    assert loaded["generation"]["backend"] == "antigravity"
    assert loaded["max_jobs"] == 2
    assert loaded["providers"]["remotive"] is True
    assert loaded["providers"]["linkedin"] is False

    disk_saved = json.loads(cfg_file.read_text(encoding="utf-8"))
    assert disk_saved["generation"]["backend"] == "antigravity"
    assert disk_saved["max_jobs"] == 0
    assert disk_saved["providers"] == {"linkedin": True, "remotive": True, "greenhouse": True}


def test_load_config_model_and_effort_flags(tmp_path):
    from types import SimpleNamespace
    from auto_switch.config import load_config

    args = SimpleNamespace(
        config=str(tmp_path / "config.json"),
        model="gemini-2.5-pro",
        effort="high",
        backend=None,
        provider=None,
        max=None,
        list=True,
        location=None,
        workspace_override=None,
        semantic=None,
        topup=None,
        judge=None,
        setup=False,
        cache_ttl=None,
        no_cache=False,
    )
    loaded = load_config(tmp_path, args)
    assert loaded["generation"]["model"] == "gemini-2.5-pro"
    assert loaded["generation"]["effort"] == "high"

