---
name: cover-letter
description: Write a tailored cover letter for the candidate described in data/profile.md, using the evidence-backed work experiences under data/work-experiences/ (RESUME_BULLETS.md / PORTFOLIO.md), matched to a job description. Use when the user asks to "write a cover letter", "draft a cover letter for this job", or "make a cover letter" for a specific role.
compatibility: any agent harness with file tools (opencode, Claude Code, Codex, Pi, dsh, Cursor)
---

# Cover Letter Writer

Write a concise, tailored cover letter for the candidate in `data/profile.md`,
grounded only in the canonical profile and evidence-backed work-experience
bullets. Output is Markdown (the PDF renderer can convert it if asked).

**The hard rule: never put a lie on the letter.** Every claim about work must
trace to a `RESUME_BULLETS.md` "Full version" or "Short version" section — never
to "Notes for accuracy" (those are private overclaim-warnings). Respect
team-vs-solo framing, never invent metrics, titles, or skills, and do not
promise experience the candidate does not have.

## Fixed locations (workspace root)

- **Workspace root:** the repository root containing this SKILL.md — resolve it
  as `SKILL.md`'s path going up two levels from `.agents/skills/cover-letter/`.
  If you are running inside the `auto_switch` TUI, the workspace it configured
  is authoritative. If neither resolves, ask the user where the workspace is.
- Canonical profile: `data/profile.md`
- Work experiences: `data/work-experiences/**/RESUME_BULLETS.md` (PORTFOLIO.md
  for depth)
- Build pipeline: `scripts/build_cover_letter.py` — takes the Markdown cover
  letter and emits a per-job folder with `.md` + `.html` + `.pdf`. It uses
  `scripts/make_cover_letter_html.py` (Markdown → styled ATS business letter HTML
  matching the resume typography) and `scripts/html_to_pdf.py` (headless
  Chromium via Playwright, A4, strictly 1 page). Run it with the workspace's
  virtualenv Python (`.venv/bin/python`) if it exists, else `python3` from the
  workspace root.
- Output: one folder per job under `output/<Company>/` containing
  `<Company>/<slug>-cover-letter.{md,html,pdf}`.

## Tone & framing (matches the resume — the extraction skill's lingo)

The letter is read by the hiring team at *another* company. It must read like a
senior engineer describing their work — not marketing copy, not an internal
engineering artifact, not a code dump.

- **No internal identifiers.** Never write file paths, component/function
  names, feature-flag names, error codes, or ticket IDs.
- **Architectural level, not feature names.** Describe the *behaviour* and
  *system-level concept* (e.g., "reconciliation and exception-handling
  workflows for bulk data review"), never internal screen names.
- **Confident ownership language** — "owned", "led", "designed", "built" — where
  the source supports it; never "worked on"/"helped with".
- **No empty stats.** Never mention line counts (LOC), blame percentages,
  commit/file/active-day counts, or `N-line` measures. These are private
  evidence, not letter copy. Use ownership and line-share evidence only to
  calibrate *impact phrasing* — "largest contributor to the shared component
  library", "sole author of …" — never as quoted numbers. A genuine confirmed
  business metric may be used; everything else is described as a mechanism.

## Step 1 — Gather inputs

1. Read the job description (pasted, or a `.md`/`.txt` file path; extract text
   from `.pdf`/`.docx` if needed with `python3 -c "import fitz; ..."` or
   `textutil`).
2. Read `data/profile.md` fully and glob/read the `RESUME_BULLETS.md` files
   under `data/work-experiences/`.

## Step 2 — Match analysis (mandatory, before writing)

This is the "compare and think" phase — do it in writing first. Save it to
`output/<Company>/match-analysis.md` under a `## Cover Letter` section (if the
file already exists with a `## Resume` section, keep that and only add/replace
`## Cover Letter`).

1. **Extract the JD's core asks**: the 2–4 requirements the hiring team cares
   most about (stack, domain, and the problem this role solves).
2. **Map each ask to evidence.** For each ask, name the strongest truthful
   evidence from `RESUME_BULLETS.md` (project + mechanism) and mark it
   `core` (direct) / `partial` (adjacent but honest, e.g. React ⇒ React Native
   transferability) / `gap` (no evidence).
3. **Apply the gap policy.** Never claim a gap as experience. For `partial`,
   lead with the nearest truthful adjacent achievement without naming the
   missing tech as something the candidate already does. If an ask is a
   hard-required `gap`, flag it in your final report to the user rather than
   implying it is covered. Calibration mirrors the profile's
   `## Experience matrix`: `core`/`strong` skills lead; `secondary`/`familiar`
   support; `adjacent`/`unfamiliar`/`foreign` must never be claimed as
   experience.
4. **Pick the 2–4 matches** for the letter body from the `core` (and strongest
   `partial`) rows of this map.

## Step 3 — Write the letter

Use this structure (identity from `data/profile.md`):

```
# Cover Letter — <Name from profile>
<contact line: email | phone | linkedin | github>

Dear Hiring Team,

## Opening
Why this role and company (1 short paragraph, referencing a concrete skill).

## Body
2–3 short paragraphs, each pairing a JD requirement with a real, evidence-backed
achievement. Use specific but honest language (team framing where the source
says team).

## Closing
Enthusiasm + call to action. Sign-off with name.
```

Keep it under ~350 words, one page. No invented numbers, and no empty stats —
never mention line counts, blame percentages, commit/file counts, or `N-line`
measures; a genuine *business* metric may be used only if the source states it
as confirmed, otherwise describe the mechanism.

## Step 4 — Build HTML + PDF into a per-job folder, then report

1. Write the letter Markdown to `output/<Company>/<slug>-cover-letter.md`
   (or `output/<slug>-cover-letter.md`).
2. Ensure the Step 2 analysis is saved to `output/<Company>/match-analysis.md`
   (section `## Cover Letter`).
3. Run the pipeline (from the workspace root):
   `.venv/bin/python scripts/build_cover_letter.py output/<Company>/<slug>-cover-letter.md`
   (if `.venv/bin/python` doesn't exist, use `python3`). This creates
   `output/<Company>/` with the three files:
   `<slug>-cover-letter.md` (source),
   `.html` (styled, single-page ATS business letter), and
   `.pdf` (printed from the HTML via headless Chromium, A4, strictly 1 page).
4. Sanity-check the PDF (system Python has `fitz`):
   `python3 -c "import fitz; d=fitz.open('output/<Company>/<slug>-cover-letter.pdf'); print(len(d), 'pages'); print(d[0].get_text()[:300])"`.
   Verify that the letter is strictly 1 page.
5. Report the folder path, the four file paths (md/html/pdf + match-analysis.md),
   page count (strictly 1 page), and a one-line note on which JD asks each body
   paragraph answers, plus any `gap` flags.

## Self-check

- Every achievement traces to a RESUME_BULLETS.md Full/Short bullet.
- No fabricated metrics/titles/dates; team framing preserved.
- No empty stats — no line counts, blame percentages, commit/file counts, or
  `N-line` measures; impact expressed qualitatively (ownership framing).
- Each body paragraph maps to a `core`/`partial` row from the match analysis;
  gaps are not presented as experience.
- Tone matches the company's own posting.
- Build pipeline completed: `.md`, `.html`, and `.pdf` exist in the per-job
  folder; PDF is verified to be strictly 1 page.
