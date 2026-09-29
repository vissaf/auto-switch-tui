# AGENTS.md

Agent guidance for the **auto-switch-tui** workspace: a job hunt TUI
(`auto_switch`) that scrapes job boards, ranks jobs against a candidate's
evidence-backed profile, and hands the best ones to an LLM agent (or direct
LLM API) to generate tailored resumes and cover letters.

## Architecture map

- `auto_switch/` — the Python engine (Python 3.10+):
  - `main.py` CLI entry (`--list`, `--json`, `--provider`, `--setup`, …)
  - `config.py` config loading (config file: `~/.config/auto-switch/config.json`)
  - `profile.py` skill registry + proficiency tiers + Experience-matrix parsing
  - `evidence.py` corpus mining of work-experience evidence
  - `ranking.py` compatibility scoring; `semantic.py` optional local-embedding boost
  - `providers/` one module per job source (JobSpy-backed + company boards + APIs)
  - `backends/` generation backends: agent CLIs (`backends/adapters/`) or a
    direct LLM API (`backends/api.py`); `backends/base.py` holds the templated
    CLI runner + Backend protocol, `backends/__init__.py` the registry
  - `cache.py` 30-minute (configurable) fetch cache under `~/.cache/auto-switch/`
  - `onboard.py` first-run wizard (creates `data/` from `templates/`)
  - `ui/` Textual TUI (results table, detail, saved)
- `scripts/` — deterministic build pipeline: `build_resume.py` (md → html →
  pdf), `make_resume_html.py` (styled ATS HTML), `build_cover_letter.py`
  (cover letter md → html → pdf), `make_cover_letter_html.py` (styled ATS
  cover letter HTML), `html_to_pdf.py` (headless Chromium via Playwright),
  `test_ranking.py` (calibration)
- `.agents/skills/` — **the single source of truth for generation behavior**:
  `resume-builder`, `cover-letter`, `job-match-topup`,
  `resume-codebase-extraction`. Each is a `SKILL.md` per the Agent Skills
  standard (agentskills.io). Load them via the `skill` tool (opencode),
  `/skill:<name>` (pi), or by reading the file. Do NOT edit the copies under
  `~/.config/opencode/skills/` (removed; bundled ones win).
- `data/` — instance data (this private repo commits it; a public repo must
  gitignore it — onboarding recreates it from `templates/`):
  - `data/profile.md` — canonical identity, skills, `## Experience matrix`
  - `data/work-experiences/**/RESUME_BULLETS.md` — the only allowed bullet
    source (never invent claims; "Notes for accuracy" sections are NOT for
    the resume)
- `output/` — generated artifacts (gitignored): per-job `md/html/pdf`,
  `jds/`, `llm-topup/`, `match-analysis.md` files
- `templates/` — new-user templates used by onboarding

## Commands

```bash
make setup                             # one-time: uv venv + editable install + playwright chromium
auto-switch                            # run the TUI (or: uv run auto-switch)
auto-switch --list --json              # non-interactive ranked list (or: uv run auto-switch --list)
auto-switch --provider remotive --list
make test                              # run the test suite (uv run pytest)
make lint                              # run ruff linter
uv run python scripts/test_ranking.py  # matcher calibration check
```

## Conventions

- Personal data lives only under `data/`. Never hardcode identity facts (name,
  email, employers) in code, skills, or prompts — read `data/profile.md` at
  runtime. Every skill and module must remain portable across users.
- Resume/cover-letter output is grounded exclusively in
  `data/work-experiences/**/RESUME_BULLETS.md` Full/Short sections and
  `PORTFOLIO.md`. Never invent metrics, titles, tools, or skills; strip empty
  stats (LOC, blame %, commit counts); never use "Notes for accuracy" content.
- No internal identifiers (file paths, feature names, error codes) in generated
  documents.
- Match-analysis files are shared: `resume-builder` owns the `## Resume`
  section of `output/<Company>/match-analysis.md`, `cover-letter` owns
  `## Cover Letter` — keep the other section when editing.
- Config/state is machine-local: `~/.config/auto-switch/` (config, saved jobs,
  backend selection), `~/.cache/auto-switch/` (fetch cache). Secrets go in
  environment variables (`AUTO_SWITCH_API_KEY`), never in config.json or git.
- CLI flags must never break non-interactive use: `--list` mode skips all
  interactive screens.
- Python style: no comments unless they clarify a non-obvious invariant;
  docstrings on modules; match existing structure.

## Testing

- Run `make test` (pytest) before finishing changes to the engine.
- `scripts/test_ranking.py` verifies score calibration bands — run it after
  touching `ranking.py`, `profile.py`, or `evidence.py`.
- There is no lint/typecheck config; keep imports clean and run the smoke
  command `python -m auto_switch --list --provider remotive` for CLI sanity.

## Agent workflows you can ask for

- "Build/tailor my resume for this JD" → `resume-builder` skill
- "Write a cover letter for this job" → `cover-letter` skill
- "Extract my contribution from this codebase" → `resume-codebase-extraction`
  skill (git-blame-backed; run it inside the codebase being analyzed)
- "Judge the exported top candidates" → `job-match-topup` skill (writes back
  `output/llm-topup/judged.json`)
