"""Backend registry: detect agent CLIs on PATH and resolve the configured one.

Config key ``generation.backend`` accepts any adapter name (``opencode``,
``claude``, ``pi``, ``deepseek``), ``api`` (direct LLM API), or ``auto``
(default) — first detected agent CLI wins, with the API backend as the last
resort. The first-run TUI asks the user once and persists the choice; the
``--backend`` CLI flag re-selects it.
"""

from __future__ import annotations

from .adapters.antigravity import AntigravityBackend
from .adapters.claude import ClaudeBackend
from .adapters.deepseek import DeepSeekBackend
from .adapters.opencode import OpenCodeBackend
from .adapters.pi import PiBackend
from .api import APIBackend

AGENT_BACKENDS: list = [AntigravityBackend, OpenCodeBackend, ClaudeBackend, PiBackend, DeepSeekBackend]
ALL_BACKENDS: list = AGENT_BACKENDS + [APIBackend]
BACKEND_BY_NAME: dict[str, type] = {cls.name: cls for cls in ALL_BACKENDS}
BACKEND_BY_NAME["agy"] = AntigravityBackend

BACKEND_NAMES = list(BACKEND_BY_NAME)


def detect_agents() -> dict[str, bool]:
    """{name: available-on-PATH} for every agent CLI adapter."""
    return {cls.name: cls().detect() for cls in AGENT_BACKENDS}


def resolve_backend(cfg: dict):
    """Instantiate the configured backend, falling back sensibly."""
    choice = (cfg.get("generation", {}) or {}).get("backend") or "auto"
    if choice == "auto":
        for cls in AGENT_BACKENDS:
            backend = cls()
            if backend.detect():
                return backend
        return APIBackend()
    if choice in BACKEND_BY_NAME:
        return BACKEND_BY_NAME[choice]()
    # Unknown name: fall back to auto-resolution rather than crashing.
    return resolve_backend(dict(cfg, generation={**(cfg.get("generation") or {}), "backend": "auto"}))


def backend_status(cfg: dict) -> str:
    """Human-readable line describing which backend is active."""
    backend = resolve_backend(cfg)
    return f"{backend.display_name} ({backend.name})"
