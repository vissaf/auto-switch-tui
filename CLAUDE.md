# CLAUDE.md

Guidance for Claude Code working in the **auto-switch-tui** workspace.

## What this project is

`auto-switch` is a high-performance Python terminal UI (TUI) and CLI tool that:
1. Scrapes job listings across top job boards, regional platforms, and direct company ATS boards.
2. Ranks them deterministically against an evidence-backed candidate profile (`data/profile.md` + `data/work-experiences/`).
3. Passes the best matches to an LLM agent CLI or direct API to generate ATS-optimized resumes and cover letters in Markdown, HTML, and pixel-perfect PDF.

## Commands

```bash
make setup                             # one-time: uv venv + editable install + playwright chromium
auto-switch                            # launch interactive TUI (or: uv run auto-switch)
auto-switch --list                     # ranked list in terminal
auto-switch --list --json              # machine-readable JSON list
auto-switch --provider instahyre --list# scrape only Instahyre
auto-switch --provider bayt --list    # scrape only Bayt
auto-switch --provider remotive --list# scrape only Remotive
make test                              # run pytest test suite (uv run pytest tests/ -q)
make lint                              # run ruff linter (uv run ruff check .)
make format                            # auto-format with ruff (uv run ruff format .)
uv run python scripts/test_ranking.py  # matcher calibration verification
```

## Architecture & Code Map

- `auto_switch/`:
  - `main.py`: CLI entry point (`auto-switch`).
  - `ranking.py`: Deterministic keyword demand/earned ratio scoring and seniority adjustment.
  - `semantic.py`: Optional local ONNX embedding similarity (`BAAI/bge-small-en-v1.5`) with lazy loading and disk caching.
  - `profile.py` & `evidence.py`: Profile parsing and evidence corpus tier mining with file-fingerprint caching.
  - `providers/`:
    - **Custom in-house scrapers**:
      - `instahyre.py`: Custom REST API + HTML JSON-LD scraper for India tech hubs and remote roles.
      - `bayt.py`: Custom curl-based TLS-spoofing HTML/JSON-LD scraper for Gulf region (UAE, KSA, Qatar, etc.).
      - `ashby.py`, `greenhouse.py`, `lever.py`: Direct company ATS board API clients (no keys required, compensation parsing).
      - `google_serpapi.py`: Reliable Google Jobs integration via SerpApi.
      - `remotive.py`: Direct API for remote software engineering jobs.
      - `adzuna.py`, `jooble.py`: Keyed international job search APIs.
    - **JobSpy scrapers** (`jobspy.py`):
      - LinkedIn, Indeed, Glassdoor, ZipRecruiter, Naukri.
  - `ui/`: Textual TUI (`app.py`, `detail.py`, `setup.py`, `widgets.py`).
  - `backends/`: Generation backends (Claude Code, Antigravity, OpenCode, Pi, DeepSeek Harness, direct API).
- `scripts/`:
  - `build_resume.py` & `make_resume_html.py`: Markdown to ATS-styled HTML.
  - `build_cover_letter.py` & `make_cover_letter_html.py`: Markdown to ATS cover letter.
  - `html_to_pdf.py`: Headless Chromium PDF renderer (via Playwright).
- `.agents/skills/`:
  - Bundled Agent Skills: `resume-builder`, `cover-letter`, `job-match-topup`, `resume-codebase-extraction`.

## Key Conventions

- **Personal Data Isolation:** Identity and work history live exclusively under `data/`. Never hardcode candidate names, emails, or company names in code or prompts.
- **Evidence-Grounded Output:** Generated resumes and cover letters must draw facts strictly from `data/work-experiences/**/RESUME_BULLETS.md` and `PORTFOLIO.md`. Never invent claims, tools, or metrics.
- **Speed & Caching:** Tiers and embeddings are cached under `~/.cache/auto-switch/`. Keep CLI operations fast and offline by default.
