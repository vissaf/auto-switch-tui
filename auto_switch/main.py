"""CLI entry point for auto-switch."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def parse_args(argv):
    p = argparse.ArgumentParser(
        prog="auto-switch",
        description="Find, rank, and tailor jobs to your profile (TUI).",
    )
    p.add_argument("-l", "--list", action="store_true", help="non-TUI: print ranked list and exit")
    p.add_argument("--max", type=int, help="max jobs to show (default: all; 0 = all)")
    p.add_argument("--location", help="comma-separated target locations (overrides config)")
    p.add_argument("--provider", help="only run this provider (e.g. remotive, greenhouse, ashby, instahyre)")
    p.add_argument("--sort", choices=["compat", "salary", "posted"], default="compat",
                   help="default sort order (default: compat)")
    p.add_argument("--setup", action="store_true", help="re-run first-run setup (backend selection)")
    p.add_argument("--json", action="store_true", help="with --list: emit JSON")
    p.add_argument("--config", help="config file path override")
    p.add_argument("--workspace", dest="workspace_override", help="workspace (resume-builder-system) override")
    p.add_argument("--semantic", dest="semantic", action="store_true", default=None,
                   help="enable semantic (embedding) score blend")
    p.add_argument("--no-semantic", dest="semantic", action="store_false",
                   help="disable semantic (embedding) score blend")
    p.add_argument("--topup", dest="topup", action="store_true", default=None,
                   help="export top candidates for LLM judging")
    p.add_argument("--no-topup", dest="topup", action="store_false",
                   help="do not export LLM top-up candidates")
    p.add_argument("--judge", dest="judge", action="store_true", default=None,
                   help="auto-judge top candidates via the configured backend")
    p.add_argument("--no-judge", dest="judge", action="store_false",
                   help="skip LLM judging; use offline scores only")
    p.add_argument("--judge-min-score", type=float,
                   help="minimum score threshold to trigger LLM judging (default: 75.0)")
    p.add_argument("--backend", choices=["auto", "antigravity", "agy", "opencode", "claude", "pi", "deepseek", "api"],
                   help="generation backend (re-selects it in config)")
    p.add_argument("--model", help="model override for generation backend (e.g. for agy or direct API)")
    p.add_argument("--effort", choices=["low", "medium", "high"],
                   help="reasoning effort for generation backend (e.g. agy)")
    p.add_argument("--cache-ttl", type=int, help="fetch cache lifetime in minutes")
    p.add_argument("--no-cache", action="store_true", help="disable the fetch cache")
    p.add_argument(
        "--toast-position",
        choices=["bottom-right", "top-right", "bottom-left", "top-left"],
        help="toast notifications placement (default: bottom-right)",
    )
    return p.parse_args(argv)


def _print_list(jobs, args):
    if args.json:
        print(json.dumps([j.to_dict() for j in jobs], indent=2))
        return
    cols = [
        ("#", 2), ("%", 4), ("Company", 24), ("Title", 46),
        ("Location", 24), ("Salary", 16), ("Source", 10),
    ]
    header = " ".join(f"{name:<{w}}" for name, w in cols)
    print(header)
    print("-" * len(header))
    for i, j in enumerate(jobs, 1):
        row = [
            f"{i:<2}", f"{j.compatibility:<4.0f}", j.company[:23], j.title[:45],
            j.display_location[:23], (j.salary_text or "")[:15], j.source[:9],
        ]
        print(" ".join(row))


def _fetch_with_progress(cfg):
    """Run the concurrent fetch behind a rich progress bar on stderr.

    A fresh 30-minute (configurable) cache hit skips the fetch entirely —
    cached jobs are raw (pre-ranking), so scoring/filtering still run fresh.
    """
    from . import cache
    from .cache import ttl_minutes

    cached = cache.load(cfg)
    if cached is not None:
        jobs, age = cached
        cfg["_cache_age"] = age
        print(
            f"  [dim]Using cached results ({len(jobs)} jobs, {age:.0f} min old — "
            f"ttl {ttl_minutes(cfg)}m). Use --no-cache to force a fresh fetch.[/dim]",
            file=sys.stderr,
        )
        return jobs

    from rich.console import Console
    from rich.progress import (
        BarColumn,
        Progress,
        SpinnerColumn,
        TextColumn,
        TimeElapsedColumn,
    )

    from .providers import aggregate, build_providers

    providers = build_providers(cfg)
    if not providers:
        print("  ! no providers enabled — edit ~/.config/auto-switch/config.json", file=sys.stderr)
        return []

    console = Console(stderr=True)
    with Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}[/bold blue]"),
        BarColumn(bar_width=None),
        TextColumn("{task.completed}/{task.total}"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Fetching jobs", total=len(providers))

        def cb(name, status, count, error):
            if error is not None:
                console.print(f"  [red]! {name}: {error}[/red]")
            elif status == "ok":
                console.print(f"  [dim]+ {name}: {count} jobs[/dim]")
            progress.advance(task)
            progress.update(task, description=f"Fetching jobs ({name})")

        jobs = asyncio.run(aggregate(cfg, progress=cb))
        progress.update(task, completed=len(providers), description="Fetching jobs")
        console.print(f"  [green]Fetched {len(jobs)} unique jobs.[/green]")
    cache.save(cfg, jobs)
    return jobs


def _rank_with_progress(jobs, keywords, cfg):
    """Score/rank jobs behind a spinner (semantic embedding is slow on first run)."""
    from rich.console import Console
    from rich.progress import Progress, SpinnerColumn, TextColumn

    from .ranking import rank_jobs

    console = Console(stderr=True)
    with Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}[/bold blue]"),
        console=console,
    ) as progress:
        task = progress.add_task("Ranking jobs…", total=None)
        jobs = rank_jobs(jobs, keywords, cfg)
        progress.update(task, description=f"Ranked {len(jobs)} jobs")
    return jobs


def _judge_with_progress(jobs, cfg, workspace):
    """Re-score top candidates via the configured backend (agent CLI or API).

    Offline scores remain authoritative when judging is disabled or fails.
    """
    from rich.console import Console
    from rich.progress import Progress, SpinnerColumn, TextColumn

    from .judge import judge_top

    console = Console(stderr=True)
    with Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}[/bold blue]"),
        console=console,
    ) as progress:
        task = progress.add_task("Judging top candidates…", total=None)
        status = judge_top(jobs, cfg, workspace)
        progress.update(task, description="Match judging done")
    if status:
        console.print(f"  [dim]{status}[/dim]")
    return jobs


def main(argv=None):
    from .config import load_config
    from .profile import build_keywords

    args = parse_args(argv or sys.argv[1:])
    workspace = Path(args.workspace_override) if args.workspace_override else ROOT
    cfg = load_config(workspace, args)

    # Interactive setup screens. Skipped entirely in --list mode so scripts
    # stay non-interactive.
    if not args.list:
        from .onboard import ensure_backend, ensure_experience_years, ensure_profile, select_locations

        if not ensure_profile(workspace, cfg):
            return 0
        ensure_experience_years(workspace, cfg)
        if not ensure_backend(cfg):
            return 0
        if not select_locations(cfg):
            return 0
        from .backends import backend_status

        print(f"  [dim]Generation backend: {backend_status(cfg)}[/dim]", file=sys.stderr)

    keywords = build_keywords(workspace)

    jobs = _fetch_with_progress(cfg)
    jobs = _rank_with_progress(jobs, keywords, cfg)

    # Ingest any prior LLM verdicts and fold them into the scores.
    from .topup import apply_judged, ingest_judged

    judged = ingest_judged(workspace)
    if judged:
        apply_judged(jobs, judged)
        jobs.sort(key=lambda j: (j.compatibility, j.salary_annual_usd or 0), reverse=True)

    # Drop jobs outside the target region(s) (e.g. "Gulf" -> UAE/KSA/Qatar/…).
    from .locations import filter_jobs, resolve

    targets = resolve(cfg.get("locations", []))
    if targets.active:
        before = len(jobs)
        jobs = filter_jobs(jobs, cfg.get("locations", []))
        print(
            f"  [dim]Kept {len(jobs)}/{before} jobs matching location(s): "
            f"{', '.join(cfg.get('locations') or ['—'])}[/dim]",
            file=sys.stderr,
        )

    # Judge the top candidates with the configured backend (agent CLI or API);
    # falls back to the offline scores when disabled or on failure. In --list
    # mode this runs synchronously; the TUI judges in the background instead so
    # the table renders immediately.
    if args.list:
        jobs = _judge_with_progress(jobs, cfg, workspace)

    # 0 (or missing) means show all jobs; otherwise cap at max_jobs.
    limit = cfg.get("max_jobs", 0) or 0
    if limit > 0:
        jobs = jobs[:limit]

    # Export top candidates for LLM judging (opencode job-match-topup skill).
    matching = cfg.get("matching", {}) or {}
    if matching.get("llm_topup", {}).get("enabled"):
        from .topup import export_candidates

        export_candidates(jobs, workspace, top_n=int(matching["llm_topup"].get("top_n") or 20))

    if args.list:
        _print_list(jobs, args)
        return 0

    from .ui.app import JobHuntApp

    try:
        JobHuntApp(cfg, jobs, keywords, default_sort=args.sort).run()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
