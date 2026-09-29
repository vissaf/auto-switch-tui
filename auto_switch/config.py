"""Configuration loading and defaults (machine-local state).

Interactive setup (profile onboarding, backend selection, target areas) lives
in ``onboard.py`` / ``ui/setup.py``; this module only loads, merges, and saves
config so non-interactive modes never block on input.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Optional

CONFIG_DIR = Path.home() / ".config" / "auto-switch"
CONFIG_PATH = CONFIG_DIR / "config.json"

# Machine-local API key file for the direct-LLM backend. Kept OUT of config.json
# (secrets never live in git-visible state); written with 0600 permissions.
API_KEY_FILE = CONFIG_DIR / "api_key"

_LEGACY_CONFIG_DIR = Path.home() / ".config" / "jobhunt"


def _migrate_legacy_dir() -> None:
    """One-time migration: move ~/.config/jobhunt -> ~/.config/auto-switch."""
    if _LEGACY_CONFIG_DIR.exists() and not CONFIG_DIR.exists():
        _LEGACY_CONFIG_DIR.rename(CONFIG_DIR)

# Conservative, verified-this-week company slugs for the ATS board APIs. Add or
# prune freely in the config file. Wrong slugs are skipped silently (404/empty).
DEFAULT_COMPANIES = {
    "greenhouse": ["airbnb", "stripe", "cloudflare", "canva", "figma"],
    "lever": ["palantir"],
    "ashby": ["openai", "linear", "posthog"],
}

DEFAULT_SEARCH_TERMS = [
    "frontend engineer", "front-end", "ui engineer",
    "react", "typescript", "javascript",
]


def _default_config(workspace: Path) -> dict[str, Any]:
    return {
        "locations": [],
        "max_jobs": 0,  # 0 = show all fetched jobs (no cap)
        "search_terms": DEFAULT_SEARCH_TERMS,
        "providers": {
            "remotive": True,
            "greenhouse": True,
            "lever": True,
            "ashby": True,
            # JobSpy-backed boards (validated scrapers from speedyapply/JobSpy)
            "linkedin": True,
            "indeed": True,
            "glassdoor": True,
            "zip_recruiter": True,
            "google": True,
            "bayt": True,
            "naukri": True,
            "instahyre": True,
            # Keyed APIs (need api_keys below)
            "adzuna": False,
            "jooble": False,
        },
        "jobspy": {
            "results_wanted": 25,       # per scrape call (per term x location)
            "hours_old": None,          # e.g. 168 = last 7 days
            "linkedin_fetch_description": True,   # +1 request per job, but fills description for ranking
            "enforce_annual_salary": False,
            "proxies": [],              # ["user:pass@host:port", ...]
            "verbose": 0,               # 0 errors only, 1 +warnings, 2 all logs
            "max_calls": 16,            # cap scrape calls per board per run
            "max_workers": 3,           # concurrent scrape calls per board
            # Exact Google Jobs queries (copy from Google Jobs search box);
            # replaces auto-generated queries when set.
            "google_search_terms": [],
        },
        "api_keys": {
            "adzuna_app_id": "",
            "adzuna_app_key": "",
            "jooble": "",
            "serpapi": "",           # Google Jobs via SerpApi (100 free/mo)
        },
        "matching": {
            "semantic": True,           # add a local-embedding similarity signal
            "semantic_weight": 0.5,     # one-sided boost weight (0..1)
            "llm_topup": {
                "enabled": False,       # export top candidates for LLM judging
                "top_n": 20,
            },
            "judge": {
                "enabled": True,        # auto-judge top candidates via the configured backend
                "min_score": 75.0,      # judge all jobs with and above this score
                "top_n": 15,            # fallback minimum candidates to judge
                "max_n": 40,            # upper safety cap on candidates judged per run
                "timeout": 1200,        # seconds per agent-CLI judge run
            },
        },
        "companies": DEFAULT_COMPANIES,
        "workspace": str(workspace),
        "profile_path": "data/profile.md",
        "generation": {
            "backend": "auto",       # antigravity | opencode | claude | pi | deepseek | api | auto
            "selected": False,       # becomes True after the first-run backend screen
            "timeout": 600,          # seconds per generation run
            "model": "",             # optional model override (e.g. for agy or direct API)
            "effort": "",            # optional reasoning effort (low|medium|high for agy)
            "api": {
                "provider": "openai",            # openai | anthropic | google | deepseek | openrouter
                "base_url": "",                  # optional OpenAI-compatible override
                "model": "",                     # empty = provider default
                "key_env": "AUTO_SWITCH_API_KEY",
            },
        },
        "cache": {
            "ttl_minutes": 30,       # fetch cache lifetime; set in onboarding
            "disabled": False,
        },
        "ui": {
            "toast_position": "bottom-right",  # bottom-right | top-right | bottom-left | top-left
        },
    }


def _deep_merge(base: dict, over: dict) -> dict:
    """Merge `over` onto `base`, recursing into nested dicts (so new provider
    keys / api_keys / companies added in a later release reach existing configs)."""
    out = dict(base)
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_config(workspace: Path, args: Any) -> dict[str, Any]:
    """Load config. Fresh configs get sensible defaults; interactive setup
    (locations screen, backend screen, onboarding) runs in main.py's TUI
    flow, never here — so non-interactive modes never block on input."""
    _migrate_legacy_dir()
    path = Path(args.config).expanduser() if getattr(args, "config", None) else CONFIG_PATH
    if path.exists():
        loaded = json.loads(path.read_text(encoding="utf-8"))
        cfg = _deep_merge(_default_config(workspace), loaded)
    else:
        cfg = _default_config(workspace)
        if getattr(args, "list", False) or not sys.stdin.isatty():
            cfg["locations"] = ["Remote"]
        save_config(cfg, path)

    # CLI overrides
    if getattr(args, "location", None):
        cfg["locations"] = [p.strip() for p in args.location.split(",") if p.strip()]
    if getattr(args, "max", None):
        cfg["max_jobs"] = args.max
    if getattr(args, "provider", None):
        cfg["providers"] = {p: (p == args.provider) for p in cfg["providers"]}
    if getattr(args, "workspace_override", None):
        cfg["workspace"] = args.workspace_override
    if getattr(args, "semantic", None) is not None:
        cfg.setdefault("matching", {})["semantic"] = args.semantic
    if getattr(args, "topup", None) is not None:
        cfg.setdefault("matching", {}).setdefault("llm_topup", {})["enabled"] = args.topup
    if getattr(args, "judge", None) is not None:
        cfg.setdefault("matching", {}).setdefault("judge", {})["enabled"] = args.judge
    if getattr(args, "judge_min_score", None) is not None:
        cfg.setdefault("matching", {}).setdefault("judge", {})["min_score"] = args.judge_min_score
    if getattr(args, "backend", None):
        backend_choice = "antigravity" if args.backend == "agy" else args.backend
        cfg.setdefault("generation", {})["backend"] = backend_choice
        cfg.setdefault("generation", {})["selected"] = True
        if path.exists():
            try:
                disk_cfg = json.loads(path.read_text(encoding="utf-8"))
                disk_cfg.setdefault("generation", {})["backend"] = backend_choice
                disk_cfg.setdefault("generation", {})["selected"] = True
                path.write_text(json.dumps(disk_cfg, indent=2), encoding="utf-8")
            except Exception:
                pass
    if getattr(args, "model", None):
        cfg.setdefault("generation", {})["model"] = args.model
    if getattr(args, "effort", None):
        cfg.setdefault("generation", {})["effort"] = args.effort
    if getattr(args, "setup", False):
        cfg.setdefault("generation", {})["selected"] = False
    if getattr(args, "cache_ttl", None) is not None:
        cfg.setdefault("cache", {})["ttl_minutes"] = args.cache_ttl
    if getattr(args, "no_cache", False):
        cfg.setdefault("cache", {})["disabled"] = True
    if getattr(args, "toast_position", None):
        cfg.setdefault("ui", {})["toast_position"] = args.toast_position

    cfg["workspace"] = str(Path(cfg["workspace"]).expanduser().resolve())
    return cfg


def save_config(cfg: dict[str, Any], path: Optional[Path] = None) -> None:
    path = path or CONFIG_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")


def write_api_key(key: str) -> None:
    """Persist the API key for the direct-LLM backend (0600, machine-local)."""
    API_KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
    API_KEY_FILE.write_text(key.strip(), encoding="utf-8")
    API_KEY_FILE.chmod(0o600)


def config_path() -> Path:
    return CONFIG_PATH


def toast_position(cfg: dict[str, Any]) -> str:
    """Return the configured toast position, defaulting to 'bottom-right'."""
    val = (
        cfg.get("ui", {}).get("toast_position")
        or cfg.get("toast_position")
        or "bottom-right"
    )
    if val in ("bottom-right", "top-right", "bottom-left", "top-left"):
        return val
    return "bottom-right"
