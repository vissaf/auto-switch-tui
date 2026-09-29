# ⚡ Auto-Switch (`auto-switch-tui`)

> **Find, rank, and tailor jobs to your real-world experience.**  
> A high-performance Terminal UI (TUI) and CLI tool that aggregates jobs across 12+ platforms, ranks them against an evidence-backed candidate profile, and orchestrates LLMs or coding agent CLIs to generate ATS-optimized resumes and cover letters in Markdown, HTML, and PDF.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-brightgreen.svg)](https://www.python.org/)
[![Built with Textual](https://img.shields.io/badge/UI-Textual-teal.svg)](https://textual.textualize.io/)
[![Package Manager: uv](https://img.shields.io/badge/managed%20by-uv-purple.svg)](https://github.com/astral-sh/uv)

---

## 📑 Table of Contents

- [What is Auto-Switch?](#-what-is-auto-switch)
- [Key Features](#-key-features)
- [Quickstart (2-Minute Setup)](#-quickstart-2-minute-setup)
- [First-Run Walkthrough](#-first-run-walkthrough)
- [Keyboard Shortcuts (TUI Cheatsheet)](#-keyboard-shortcuts-tui-cheatsheet)
- [Evidence-Grounded Resume & Match System](#-evidence-grounded-resume--match-system)
  - [Auto-Extracting Evidence from Your Codebases (`resume-codebase-extraction`)](#-auto-extracting-evidence-from-your-codebases-resume-codebase-extraction)
- [Generation Backends](#-generation-backends)
- [Supported Job Providers](#-supported-job-providers)
- [Configuration Guide](#-configuration-guide)
- [CLI / Headless Mode](#-cli--headless-mode)
- [Troubleshooting & FAQ](#-troubleshooting--faq)
- [Contributing & License](#-contributing--license)

---

## 💡 What is Auto-Switch?

Job hunting today is fragmented: you check five different aggregators, get flooded with irrelevantly matched listings, and manually tweak your resume for each application.

**Auto-Switch** bridges that gap into a unified terminal workspace:

1. **Scrapes Multi-Board Postings Concurrently**: Pulls fresh listings directly from company ATS career portals (Ashby, Greenhouse, Lever), regional tech portals (Instahyre, Bayt with anti-bot TLS bypass), search engines (Google Jobs via SerpApi), and global aggregators (LinkedIn, Indeed, Glassdoor, ZipRecruiter, Naukri, Remotive).
2. **Deterministic Match Scoring (0–100%)**: Calibrated against your real, documented skills and experience matrix. No hallucinated keyword matches — a role demanding React Native scores down if you only know React web; missing core competencies penalize heavily, while deep domain overlaps score near 100%.
3. **1-Click Tailored ATS Resumes & Cover Letters**: Hit `r` for Resume or `c` for Cover Letter on any listing. Auto-Switch extracts the job description, hands it off to your chosen agent CLI or direct LLM API, and builds a complete artifact package: tailored Markdown, styled single-column HTML, and a pixel-perfect, ATS-verified PDF via headless Chromium.

---

## ✨ Key Features

- 🖥️ **Full-Featured Terminal UI**: Beautiful dark-mode dashboard built with Textual featuring real-time search filtering, multi-key sorting (match score, salary, date posted, location), detail views, and saved bookmarks.
- 🛡️ **Anti-Bot & Direct ATS Scrapers**: Custom scrapers for Instahyre (concurrent JSON-LD detail extraction), Bayt (lightweight curl TLS fingerprint spoofing to bypass CDN blocks), and direct company board scrapers for Ashby, Greenhouse, and Lever.
- 🔍 **Local Semantic AI Matcher (Optional)**: In addition to deterministic keyword demand scoring, local ONNX embeddings (`BAAI/bge-small-en-v1.5`) provide synonym similarity boosts without sending any data over the wire.
- 🧬 **Git-Backed Evidence Extraction**: Bundles a standalone agent skill (`resume-codebase-extraction`) that performs line-level `git blame` scans on any repository you've worked on to extract truthful portfolio writeups and ATS-ready bullets in Auto-Switch's native format.
- 🤖 **Universal Agent & API Support**: Works out of the box with your preferred coding agent CLI (**Antigravity**, **OpenCode**, **Claude Code**, **Pi**, **DeepSeek Harness**) or via direct LLM API key (**OpenAI**, **Anthropic**, **Google Gemini**, **DeepSeek**, **OpenRouter**).
- 🔒 **Privacy-First Architecture**: Your personal identity, contact details, and work history live exclusively inside local files in `data/` (gitignored). No personal data is ever tracked in the repository.

---

## 🚀 Quickstart (2-Minute Setup)

### Prerequisites

- **Python 3.10 to 3.12**
- **[uv](https://github.com/astral-sh/uv)** (recommended fast Python manager)
  - **macOS / Linux**: `curl -LsSf https://astral.sh/uv/install.sh | sh` or `brew install uv`
  - **Windows (WSL)**: `curl -LsSf https://astral.sh/uv/install.sh | sh`
- One of the following for resume/cover letter generation:
  - An agent CLI installed on your terminal `$PATH`: `agy` (Antigravity), `opencode`, `claude`, `pi`, or `dsh` (DeepSeek Harness)
  - *OR* an LLM API key (`AUTO_SWITCH_API_KEY` env variable or entered during setup)

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/vissaf/auto-switch-tui.git
cd auto-switch-tui

# 2. Run one-time setup
make setup
```

What `make setup` does:
- Creates a local `.venv` and installs dependencies via `pyproject.toml`
- Installs `auto-switch` globally onto your terminal `$PATH` (editable mode via `uv tool`)
- Downloads the Playwright Chromium browser binary used for ATS PDF rendering

### Launch

```bash
auto-switch
```

*(You can also run directly with `uv run auto-switch`)*

---

## 🧭 First-Run Walkthrough

When you start `auto-switch` for the first time, an interactive 3-step setup wizard guides you:

```
┌────────────────────────────────────────────────────────┐
│         Step 1: Create Candidate Profile               │
│  Name, email, contact, headline, years of experience   │
└──────────────────────────┬─────────────────────────────┘
                           │
┌──────────────────────────▼─────────────────────────────┐
│         Step 2: Generation Backend & Cache             │
│  Pick detected Agent CLI or Direct LLM API key         │
└──────────────────────────┬─────────────────────────────┘
                           │
┌──────────────────────────▼─────────────────────────────┐
│         Step 3: Target Job Locations                   │
│  Select regions (UAE, India, USA, EU, Remote, etc.)    │
└──────────────────────────┬─────────────────────────────┘
                           │
                           ▼
                  [ Launch TUI Dashboard ]
```

1. **Profile Setup**: Populates your local `data/profile.md` with your name, contact information, target role title, and years of experience.
2. **Backend & Cache**: Auto-detects agent CLIs installed on your machine (`agy`, `claude`, `opencode`, `pi`, `dsh`) or lets you enter an API key. Configures the job-fetch cache lifetime (default: 30 minutes).
3. **Target Locations**: Choose from preset hubs (UAE / Dubai, India, USA, Canada, UK, EU, Remote) or enter custom cities.

---

## ⌨️ Keyboard Shortcuts (TUI Cheatsheet)

### Results Table View

| Key | Action |
| :--- | :--- |
| `↑` / `k` | Move cursor up |
| `↓` / `j` | Move cursor down |
| `PgUp` / `PgDn` | Scroll page up / down |
| `Enter` | Open selected job in Detail View |
| `/` | Focus live search filter |
| `r` | Sort by match score (highest first) |
| `t` | Sort by salary (highest first) |
| `p` | Sort by posted date (newest first) |
| `l` | Sort by location |
| `s` | Bookmark / Save selected job |
| `v` | View saved jobs screen |
| `q` | Quit application |

### Job Detail View

| Key | Action |
| :--- | :--- |
| `o` | Open original job posting URL in default browser |
| `s` | Bookmark / Un-save job |
| `r` | Generate tailored resume (`resume-builder` skill) |
| `c` | Generate tailored cover letter (`cover-letter` skill) |
| `Esc` | Back to results table |
| `q` | Quit application |

---

## 📂 Evidence-Grounded Resume & Match System

Unlike generic tools that hallucinate qualifications, Auto-Switch operates on a strict **Evidence-Grounded principle**:

> **Rule 1**: Never put an unsupported claim on the resume.  
> **Rule 2**: Every bullet must trace back to verifiable evidence in `data/work-experiences/`.  
> **Rule 3**: Strictly ATS-friendly output (single-column, standard headings, no multi-column tables or graphics).

### Directory Structure

```
data/
├── profile.md                  # Canonical identity, summary, skills & experience matrix
└── work-experiences/
    ├── 01. Acme Corp/
    │   └── Mobile App/
    │       ├── RESUME_BULLETS.md  # Full & Short version bullet points
    │       └── PORTFOLIO.md       # Architectural deep-dive & team context
    └── 02. Beta Tech/
        └── Analytics Platform/
            ├── RESUME_BULLETS.md
            └── PORTFOLIO.md
```

### 1. `data/profile.md`
Created automatically from `templates/profile.md`. Defines your contact info, target title, professional summary, and an `## Experience matrix` table assigning proficiency tiers:
- `core`: Primary stack, maximum demand match credit (100%)
- `strong`: Regularly used technologies (88%)
- `secondary`: Competent, supportive stack (72%)
- `adjacent`: Transferable framework (e.g. React Native for a React web engineer) (66%)
- `familiar`: Basic working knowledge (45%)
- `unfamiliar`: Adjacent discipline, minimal credit (30%)
- `foreign`: Unrelated stack / negative match

### 2. `data/work-experiences/**/RESUME_BULLETS.md`
Document your projects with **Full version** (5–7 bullets) and **Short version** (3–4 bullets) per project. Follow the formula:
`[Action built/fixed] + [Technical mechanism / architecture] + [Verifiable outcome/metric]`

---

### 🔍 Auto-Extracting Evidence from Your Codebases (`resume-codebase-extraction`)

Manually recalling what you built years ago or drafting resume bullet points from scratch often leads to vague descriptions or inflated claims that fail technical screens.

Auto-Switch bundles a specialized, open-standard Agent Skill at [`.agents/skills/resume-codebase-extraction/`](.agents/skills/resume-codebase-extraction/SKILL.md) (conforming to the [Agent Skills](https://agentskills.io) standard). You can run this skill **inside any Git repository you have worked on** (past employers, client projects, open-source codebases) to automatically generate verifiable, line-level Git-backed evidence in the exact format required by Auto-Switch.

```
┌────────────────────────────────────────────────────────┐
│  Run Agent Skill in your Project Repo                  │
│  "Extract my contribution using resume-codebase-extraction"
└──────────────────────────┬─────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────┐
│  Phase 1 & 2: Author Context & Stack Analysis          │
│  - Match author commit aliases & email addresses       │
│  - Understand tech stack, architecture & dependencies  │
└──────────────────────────┬─────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────┐
│  Phase 3: Line-Level Authorship via `git blame`        │
│  - Distinguishes files touched vs files truly owned    │
│  - Classifies: Sole Author (>90%), Majority, Contributor│
│  - Reads actual implementation code & edge cases       │
└──────────────────────────┬─────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────┐
│  Phase 4 & 5: Guardrails & ATS-Ready Generation        │
│  - Zero internal leaks: strips file paths & error codes │
│  - Strict anti-hallucination & metric verification     │
└──────────────────────────┬─────────────────────────────┘
                           │
                           ▼
          Produces Auto-Switch Ready Artifacts:
          ├── PORTFOLIO.md        (Architectural overview)
          └── RESUME_BULLETS.md   (Full & Short bullets)
```

#### How the Extraction Scan Works

1. **Line-Level Authorship Analysis (`git blame`)**: Rather than relying on misleading commit counts (which often reflect minor touches, renames, or lint fixes), the skill executes:
   ```bash
   git blame -w --line-porcelain <file> | grep '^author ' | sort | uniq -c | sort -rn
   ```
   This isolates surviving line-level ownership into three strict tiers: **Sole author** (~90%+), **Majority author**, and **Contributor**.
2. **Context Gathering Interview**: The agent asks you for your commit email aliases, team size, parts of the system you *did not* build (e.g. backend services, infra, or CMS owned by other teams), and explicit business metrics.
3. **Architectural Translation (Confidentiality Guardrails)**: Senior interviewers care about system design and trade-offs, not internal identifiers. The skill translates raw code into architectural mechanisms (e.g., atomic cart operations, session re-authentication) while **strictly omitting internal file paths, function names, feature flags, ticket numbers, and error codes**.
4. **Zero-Hallucination Policy**: Claims must trace to a verified `git blame` result, code actually read, or a metric explicitly confirmed by you. If a metric cannot be verified, it is omitted.

#### What It Produces

The skill generates the exact two files that populate an Auto-Switch project folder:

| File | Contents & Purpose |
| :--- | :--- |
| **`PORTFOLIO.md`** | ~1-page architectural breakdown of the systems you owned, problems solved, tradeoffs made, and an explicit **collaboration model** stating what was *not* built by you (giving 15+ YOE readers confidence in your authenticity). |
| **`RESUME_BULLETS.md`** | **Full version** (5–7 bullets) + **Short version** (3–4 bullets) following the `[Action] + [Mechanism] + [Outcome]` formula, plus a private **Notes for accuracy** section for interview prep. |

#### Step-by-Step: How to Run the Extraction

You can run the skill in any repository you want to analyze using your preferred coding agent:

##### Option 1: Using OpenCode
Navigate to the repository you worked on and pass the skill path:
```bash
cd /path/to/your-past-work-repo
opencode --skill /path/to/auto-switch-tui/.agents/skills/resume-codebase-extraction
```
Prompt:
> *"Extract my engineering contribution from this codebase using resume-codebase-extraction"*

##### Option 2: Using Antigravity / Claude Code / Pi / Cursor
Copy or symlink the skill folder into your project's `.agents/skills/` directory (or configure your harness's global skill search path):
```bash
# Copy skill into target project
mkdir -p /path/to/your-past-work-repo/.agents/skills
cp -r /path/to/auto-switch-tui/.agents/skills/resume-codebase-extraction /path/to/your-past-work-repo/.agents/skills/

# Open target project and run your agent CLI
cd /path/to/your-past-work-repo
agy  # or claude / pi / cursor
```
Prompt:
> *"Extract my engineering contribution from this codebase using resume-codebase-extraction"*

##### Option 3: Copying Generated Artifacts into Auto-Switch
Once the agent finishes, move the generated `PORTFOLIO.md` and `RESUME_BULLETS.md` into your Auto-Switch workspace under `data/work-experiences/<Company>/<Project>/`:

```bash
cd /path/to/auto-switch-tui
mkdir -p "data/work-experiences/01. Acme Corp/Checkout Engine"
mv /path/to/your-past-work-repo/PORTFOLIO.md "data/work-experiences/01. Acme Corp/Checkout Engine/"
mv /path/to/your-past-work-repo/RESUME_BULLETS.md "data/work-experiences/01. Acme Corp/Checkout Engine/"
```

#### How Auto-Switch Uses Your Extracted Evidence

Once placed in `data/work-experiences/`:
- **Automated Skill Tier Mining**: Auto-Switch's evidence engine (`auto_switch/evidence.py`) automatically scans the corpus on startup. Mentions paired with senior authorship verbs (`designed`, `architected`, `owned`, `led`) automatically upgrade your skill proficiency tiers (`core`, `strong`, `secondary`).
- **Grounded Match Calibration**: The job ranking algorithm uses your mined experience to score matching listings with high fidelity.
- **Truthful 1-Click Tailoring**: When you press `r` (Resume) or `c` (Cover Letter) in the TUI, the `resume-builder` and `cover-letter` skills assemble documents sourced directly from your verified Git bullets—never hallucinating qualifications or metrics.

---

## 🤖 Generation Backends

Auto-Switch generates tailored resumes and cover letters by passing the target job description and your grounded evidence to an AI engine:

### 1. Coding Agent CLIs (Headless Execution)
Auto-Switch can run agent CLIs headlessly with bundled Agent Skills (`.agents/skills/`):
- **Antigravity CLI** (`agy`)
- **OpenCode CLI** (`opencode`)
- **Claude Code CLI** (`claude`)
- **Pi CLI** (`pi`)
- **DeepSeek Harness** (`dsh`)

### 2. Direct LLM API
If you prefer not to use an agent CLI, select the **Direct API backend**:
- Supports: **OpenAI** (`gpt-4o`), **Anthropic** (`claude-3-5-sonnet`), **Google Gemini** (`gemini-2.0-flash`), **DeepSeek**, and **OpenRouter**.
- Provide your key via environment variable:
  ```bash
  export AUTO_SWITCH_API_KEY="your-api-key-here"
  ```
  *(Or input it into the first-run prompt; stored at `~/.config/auto-switch/api_key` with 0600 file permissions).*

Generated output files are organized cleanly in per-company folders under `output/`:
- `output/<Company>/<Company>-resume.md` (tailored Markdown)
- `output/<Company>/<Company>-resume.html` (ATS-styled HTML)
- `output/<Company>/<Company>-resume.pdf` (printable A4 PDF)
- `output/<Company>/match-analysis.md` (transparent analysis of JD requirements vs candidate evidence)

---

## 🌐 Supported Job Providers

| Provider | Type | API Key Needed | Default | Target Hubs & Strengths |
| :--- | :--- | :---: | :---: | :--- |
| **Instahyre** | Custom Scraper | No | **On** | India tech hubs (Bengaluru, Gurgaon/NCR, Hyderabad, Pune, Mumbai) + Remote. REST search + JSON-LD detail parsing. |
| **Bayt** | Custom Scraper | No | **On** | Gulf / Middle East (UAE, Saudi Arabia, Qatar, Kuwait, Bahrain, Oman). Features TLS spoofing to bypass CDN blocking. |
| **Ashby** | Direct ATS API | No | **On** | Direct company career board API (OpenAI, Linear, PostHog, etc.). Captures explicit compensation bands. |
| **Greenhouse** | Direct ATS API | No | **On** | Direct career board API (Stripe, Airbnb, Cloudflare, Figma, Canva, etc.). |
| **Lever** | Direct ATS API | No | **On** | Direct company career postings client (Palantir, etc.). |
| **Google Jobs** | SerpApi | Optional | **On** | High-yield Google Jobs aggregation via SerpApi. |
| **Remotive** | Public API | No | **On** | Global remote-first engineering roles. |
| **LinkedIn** | JobSpy | No | **On** | Global search terms & regional listings. |
| **Indeed** | JobSpy | No | **On** | Localized boards across UAE, India, US, UK, EU. |
| **Glassdoor** | JobSpy | No | **On** | ~22 supported countries. |
| **ZipRecruiter**| JobSpy | No | **On** | US & Canada (auto-pruned when searching other regions). |
| **Naukri** | JobSpy | No | **On** | India tech listings. |
| **Adzuna** | REST API | Yes | Off | Keyed international job search API with salary data. |
| **Jooble** | REST API | Yes | Off | Keyed global job board aggregator. |

---

## ⚙️ Configuration Guide

Configuration is stored at `~/.config/auto-switch/config.json`. You can inspect or modify it at any time.

```json
{
  "locations": ["UAE", "Remote"],
  "max_jobs": 0,
  "search_terms": [
    "frontend engineer",
    "software engineer",
    "react",
    "typescript"
  ],
  "providers": {
    "remotive": true,
    "greenhouse": true,
    "lever": true,
    "ashby": true,
    "linkedin": true,
    "indeed": true,
    "instahyre": true,
    "bayt": true
  },
  "companies": {
    "greenhouse": ["airbnb", "stripe", "cloudflare", "canva", "figma"],
    "lever": ["palantir"],
    "ashby": ["openai", "linear", "posthog"]
  },
  "generation": {
    "backend": "claude",
    "selected": true
  },
  "cache": {
    "ttl_minutes": 30
  }
}
```

### Adding Target Companies (ATS Boards)
Simply add company slugs under `companies.greenhouse`, `companies.lever`, or `companies.ashby` in your config.

### Configuring Residential Proxies
If scraping high volumes on LinkedIn or Glassdoor from a restricted network, add proxies to the `jobspy` block:
```json
"jobspy": {
  "proxies": ["user:password@proxy.example.com:8080"]
}
```

---

## 🖥️ CLI / Headless Mode

Auto-Switch supports non-interactive terminal execution, making it easy to pipe output to scripts, cron jobs, or files:

```bash
# Print ranked table to terminal and exit
auto-switch --list

# Filter by a single provider
auto-switch --provider remotive --list
auto-switch --provider instahyre --list

# Filter by location and limit results
auto-switch --location "Remote, London" --max 25 --list

# Export full machine-readable JSON output
auto-switch --list --json > ranked_jobs.json

# Sort results by salary or posting date
auto-switch --sort salary --list
auto-switch --sort posted --list

# Change or re-run setup screens
auto-switch --setup
auto-switch --backend antigravity
```

---

## 🛠️ Troubleshooting & FAQ

### 1. `playwright: command not found` or PDF generation error
Playwright needs its Chromium browser binary installed to render PDFs:
```bash
uv run playwright install chromium
```

### 2. A provider returns 0 jobs or 403 Forbidden
- Some portals (e.g. LinkedIn, Glassdoor) enforce aggressive rate limits on datacenter / VPN IPs.
- For Bayt, ensure your system has `curl` installed (used for TLS fingerprint spoofing).
- For high-volume scraping, configure residential proxies in `~/.config/auto-switch/config.json`.

### 3. How do I reset or re-run my profile onboarding?
- Edit your details directly in `data/profile.md`.
- To re-select your AI generation backend or cache duration, run `auto-switch --setup`.

### 4. Running the test suite
Verify calibration and scraper integrations:
```bash
make test                              # runs all pytest tests
uv run python scripts/test_ranking.py  # runs matcher calibration checks
```

---

## 🤝 Contributing & License

Contributions are welcome! Please open an issue or submit a pull request.

This project is licensed under the [MIT License](LICENSE).
