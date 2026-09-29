---
name: resume-codebase-extraction
description: Extract an honest, git-blame-backed portfolio writeup (PORTFOLIO.md) and resume bullets (RESUME_BULLETS.md) that document the user's own verifiable engineering contribution to a codebase. Use when the user asks for a portfolio writeup, resume bullets, "what did I actually build here", contribution analysis, or codebase credit analysis — and wants claims grounded in git evidence rather than inflation or false modesty.
compatibility: any agent harness with git + file tools (opencode, Claude Code, Codex, Pi, dsh, Cursor)
---

# Resume Codebase Extraction

Produce two documents — `PORTFOLIO.md` and `RESUME_BULLETS.md` — that capture
the user's **actual, individually verifiable engineering contribution** to the
current repository, suitable for showing to senior engineers (15+ years) and
for resume use.

**Non-negotiable rule:** every claim must trace to (a) a `git blame` result,
(b) code actually read, or (c) a number the user explicitly confirmed. Never
inflate, never falsely understate, and never soften a claim silently — flag it
instead.

Work in phases. Do not skip the verification phases.

## Where the output goes

- Inside the repo being analyzed: write both files at the repo root.
- If you are running inside the `resume-builder-system` workspace, write them
  into the matching employer/project folder under
  `data/work-experiences/<employer>/<project>/` instead, so the resume-builder
  and cover-letter skills pick them up automatically.

## Phase 1 — Context gathering (ask directly, do not guess)

Use a question prompt to ask the user:

1. Git author name(s)/email(s) as they appear in commits (they may have used
   multiple aliases — contractor email, personal email, etc.).
2. Solo project or team? If team, roughly how many people?
3. Parts of the system they did NOT build (e.g., a CMS/schema in a separate
   repo, backend services owned by another team, infra owned by DevOps). These
   must be explicitly excluded from claims.
4. Total years of experience and the seniority level/company caliber being
   presented for (affects tone, not honesty).
5. Known real business metrics (traffic, page count, revenue, perf deltas) —
   only accept numbers the user explicitly confirms, or numbers derivable from
   the repo itself (route files, test files, line counts). Label derived
   numbers as derived.

## Phase 2 — Repo-wide understanding

- Read the manifest (`package.json` / equivalent), README, and top-level
  structure to learn the stack, architecture pattern, and monorepo layout.
- Identify the stack precisely: framework + version, language, styling
  approach, testing tools, CMS/backend integration, build tooling.

## Phase 3 — Team & authorship analysis (critical phase)

- Enumerate contributors and confirm real team size:
  `git log --format='%an <%ae>' | sort | uniq -c | sort -rn`
  Normalize aliases before drawing conclusions (personal vs contractor email,
  different display names for the same person).
- For the user's commits, filter `git log --author` using all known aliases:
  - First commit date, last commit date, total commits.
  - Calendar day span AND number of *distinct active days* (days with zero
    commits should be visible — do not inflate "days worked").
  - Commit volume by month/week to show a real velocity pattern (ramp-up,
    peak, taper), not a flat "X commits over Y days" claim.
- **Do not use commit-touch-counts as a proxy for ownership.** For every
  file/module claimed, run line-level authorship:
  `git blame -w --line-porcelain <file> | grep '^author ' | sort | uniq -c | sort -rn`
  This shows *current* line-level authorship (what exists today, surviving
  refactors). Classify each file into one of three tiers:
  - **Sole author** (~90%+ of lines theirs)
  - **Majority author** (largest share but others contributed meaningfully)
  - **Contributor** (touched but not majority — say "contributed to", never
    claim ownership)
- Identify 5–15 of the most substantial files/modules where the user is sole
  or majority author. **Actually read the code** — do not summarize from
  variable names. Ground the writeup in real mechanisms: what edge case is
  handled, what tradeoff the design makes, what breaks without this code.

## Phase 4 — Guardrails (apply strictly)

- Never attribute a system to the user if not sole/majority author at line
  level, even with many commits touching it. State clearly what was NOT
  architected if a file/system is shared or owned by others.
- Never invent business metrics, traffic numbers, or scale claims. Omit
  unconfirmed numbers or derive them from the repo and label as derived.
- Never claim architecture ownership of infra/CMS/backend systems excluded in
  Phase 1, even with commits touching integration points. Frame as
  "consuming/extending X, built by [team/other repo]."
- Timeline claims must be team outcomes where the team built the leverage
  (e.g., "shipped as part of an N-person team over X months") — not solo
  speed claims, unless genuinely solo.

## Phase 5 — Output: two documents

**Output style (applies to BOTH documents) — resume-ready, not a code dump:**

The output is meant to be shown to recruiters, architects, and interviewers at
*other* companies. It must NOT read like an internal engineering artifact.

- **No internal identifiers.** Never write file paths, component/function
  names, feature-flag names, environment/secret names, error codes, or ticket
  IDs in the output. A candidate cannot leak their employer's internals.
- **Describe at the architectural level.** Translate every implementation
  detail into the *behaviour* and *system-level concept* it realizes. For
  example: a specific error code and a flag name become "detects an
  availability conflict"; a batch update/delete endpoint becomes "repairs the
  cart in a single atomic operation"; a 401 handler becomes "transparent
  sign-out and re-authentication on session expiry".
- **Confident ownership language.** Where the user is sole/majority author,
  write "owned", "led", "designed", "established" — not "worked on" or
  "helped with". Frame the slice as a domain (e.g., "the cart → checkout →
  order-placement experience") rather than a list of files.
- **Read as a senior engineer describing their work**, not as marketing copy
  and not as a PR description.

**Document 1 — `PORTFOLIO.md`** (~1 page, readable by a senior/staff engineer):

- Open with stack + one-line framing of the project and team size.
- One section per system/module the user is sole/majority author on. For each:
  name the real engineering problem solved (not just what it does), the
  specific mechanism/trade-off chosen (described architecturally, no internal
  identifiers), and why. Avoid marketing adjectives ("robust", "scalable",
  "seamless") unless backed immediately by a concrete mechanism in the same
  sentence.
- Include a "collaboration model" section that states plainly what was NOT
  built/architected (CMS, backend/BFF, design system, DevOps) — framed as
  clean team boundaries, not as a list of limitations. This is what makes the
  rest credible to a 15+ YOE reader.

**Document 2 — `RESUME_BULLETS.md`:**

- A full version (5–7 bullets) and a short version (3–4 bullets).
- Each bullet: [what was built/fixed] + [specific mechanism or problem solved,
  architectural level] + [outcome, only if confirmed/derivable]. No unverified
  superlatives, no internal identifiers.
- Append a private "Notes for accuracy" section (not for the resume) listing
  exactly what must not be overclaimed in interviews, and which *work* backs
  which claim — described conceptually (e.g., "the checkout dialog system")
  rather than by path, so the user can recall specifics without leaking them.

## Phase 6 — Self-check before finalizing

Re-read both docs against the blame/timeline data and confirm every claim
traces to (a) a `git blame` result, (b) code actually read, or (c) a number
explicitly confirmed in Phase 1. Flag anything that does not meet this bar
instead of softening it silently — tell the user what is uncertain.
