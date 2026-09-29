---
name: resume-builder
description: Generate an ATS-friendly, job-tailored resume for the candidate described in data/profile.md and the evidence-backed work-experience bullets under data/work-experiences/ (RESUME_BULLETS.md / PORTFOLIO.md), optionally tailored to a pasted or file-based job description. Use when the user asks to "build/generate/tailor/update my resume", "make a resume for this job", "target my resume at this JD", or "create an ATS resume" — outputting Markdown, HTML, and PDF.
compatibility: any agent harness with file tools (opencode, Claude Code, Codex, Pi, dsh, Cursor)
---

# Resume Builder

Build a clean, ATS-friendly, one-column resume from the canonical profile and
the evidence-backed work-experience bullets in this workspace, optionally
tailored to a job description. Output is a Markdown source, an ATS-friendly
styled HTML resume, and a PDF printed from that HTML (A4, 8 mm margins).

**The three hard rules that make this trustworthy *and* impressive:**

1. **Never put a lie on the resume.** Every claim must trace to a
   `RESUME_BULLETS.md` "Full version"/"Short version" section or the project's
   `PORTFOLIO.md` — never to a "Notes for accuracy" section (that content is
   private interview-prep and overclaim-warnings, explicitly *not* for the
   resume). Respect team-vs-solo framing, and never invent metrics, titles,
   tools, or skills the candidate doesn't have. **Phrasing may be rewritten
   freely for tone and JD fit; facts may not.**
2. **Match the portfolio-extraction tone** (see "Tone & framing" below):
   confident ownership language, architectural framing, zero internal
   identifiers, zero feature-list bullets.
3. **Stay ATS-parseable.** One column, standard section headings, real text (no
   tables, graphics, images, columns, text boxes, or decorative symbols), reverse
   chronological order, consistent date format.

## Fixed locations (workspace root)

- **Workspace root:** the repository root containing this SKILL.md — resolve it
  as `SKILL.md`'s path going up two levels from `.agents/skills/resume-builder/`.
  If you are running inside the `auto_switch` TUI, the workspace it configured
  is authoritative. If neither resolves, ask the user where the workspace is.
- Canonical profile: `data/profile.md` (name, headline, contact, summary,
  skills, education, certifications). Edit here to change identity-level facts.
- Work experiences: `data/work-experiences/**/RESUME_BULLETS.md` (the only
  allowed source of bullet content; `PORTFOLIO.md` is for deeper context when a
  bullet needs to be expanded accurately).
- Build pipeline: `scripts/build_resume.py` — takes the Markdown resume and
  emits a per-job folder with `.md` + `.html` + `.pdf`. It uses
  `scripts/make_resume_html.py` (Markdown → styled, single-column HTML) and
  `scripts/html_to_pdf.py` (headless Chromium via Playwright; A4, 8 mm margins).
  Run it with the workspace's virtualenv Python (`.venv/bin/python`) if it
  exists, else `python3` from the workspace root.
- Output: one folder per job under `output/<Company>/` containing
  `<Candidate-Name>-<Company>.{md,html,pdf}` — use the candidate's actual name
  from `data/profile.md` instead of a placeholder.

## Step 1 — Gather inputs

1. Confirm the job description (JD). It may be:
   - pasted directly in the user's message, or
   - a file path to a `.txt`/`.md`/`.pdf`/`.docx` (if `.pdf`/`.docx`, extract
     text with `python3 -c "import fitz; ..."` or `textutil`, as available).
   If **no JD was provided**, ask the user (via a question prompt) whether to
   (a) generate a general "master" resume, or (b) provide a JD now.
2. Ask for the target output filename/slug if not obvious. Default slug:
   `<Name>-<TargetRole>` (e.g. `Jane-Doe-Senior-Frontend-Engineer`),
   or `<Name>-<Company>` when tailoring to a specific company. `<Name>` comes
   from `data/profile.md`, never from memory.

## Step 2 — Read the source material (do not skip)

1. Read `data/profile.md` fully.
2. Glob `data/work-experiences/**/RESUME_BULLETS.md` and read every file. For
   each, note the employer, role, dates, and keep two bullet sets: **Full** and
   **Short** (and the "Context line" if present). Ignore "Notes for accuracy"
   content for resume purposes — but use it to know what NOT to claim.
3. Build the employer list in reverse-chronological order from the profile and
   the work-experience files. Derive it from the data every run; do not
   hardcode anything.

## Step 2.5 — Match analysis (mandatory, before drafting a single bullet)

This is the "compare and think" phase. Do it in full, **in writing, before you
write any resume content** — it is what turns the resume from "keyword-sprinkled"
into genuinely tailored. Save it to `output/<Company>/match-analysis.md`
(section `## Resume`) so it can be audited.

1. **Write the JD needs profile.** Read the whole JD and list, explicitly:
   - **Must-have stack** and **preferred stack** (framework, tools, domains).
   - The **3–5 problems** this hire is being brought in to solve (from
     responsibilities + company/product context), ranked by importance.
   - **Seniority signals**: ownership, greenfield architecture, mentoring,
     performance, accessibility, design systems.
   - **Domain vocabulary**: the exact terminology the JD uses (banking,
     e-commerce, "component governance", "design system", "performance budget").
2. **Build the evidence map.** For *each* JD need, find the strongest matching
   evidence in `data/work-experiences/**/RESUME_BULLETS.md` (use `PORTFOLIO.md`
   for depth). Record a table:
   `| JD need | Evidence (file · project · mechanism) | tier: core / partial / gap |`.
   - **core** = direct, strongly evidenced.
   - **partial** = adjacent but truthful (e.g. React ⇒ React Native
     transferability, Angular at a junior tier, Sanity CMS ⇒ other headless CMS).
   - **gap** = no real evidence.
3. **Apply the gap policy.** For each `partial`/`gap`:
   - Cover a `partial` by surfacing the *nearest truthful* adjacent experience;
     never claim the missing tech itself.
   - A `gap` is **never** invented away. If it is central to the role (a
     required framework or a hard requirement with zero evidence), flag it in
     the final report to the user — do not paper over it on the resume.
   - The calibration mirrors the app's matcher: framework-agnostic but honest.
     Use the profile's `## Experience matrix` tiers to calibrate: `core`/`strong`
     skills are fair game to lead with, `secondary`/`familiar` support claims,
     `adjacent`/`unfamiliar`/`foreign` must never be claimed as experience.
4. **Choose spearheads from this map.** Name the 1–2 **spearhead** projects:
   they get the **Full** bullets, the most bullet slots, and top placement.
   Every spearhead choice must cite a `core` evidence row.
5. Save the analysis: `output/<Company>/match-analysis.md` with a `## Resume`
   section (needs profile + evidence map + gap flags + spearhead rationale).

## Step 3 — Tailor (this is the core step, not an afterthought)

**If a JD is present**, do this — the goal is to make the resume read like it
was *written for this role*, not to sprinkle keywords. Work from the Step 2.5
match analysis:

1. **Work from the Step 2.5 analysis** — do not re-derive the needs profile or
   relevance map here; it is already written down. (If Step 2.5 was skipped or
   is incomplete, go back and complete it first.)
2. **Set spearhead placement.** Spearhead projects (chosen in Step 2.5) get the
   **Full** bullets, the most bullet slots, and top placement within their
   employer. Older/less-relevant employers get **Short** bullets (fewer, lower
   down).
3. **Position the summary against the JD's mission.** 4–6 lines — a full
   professional definition, not a teaser. Fixed shape: (a) who you are — years,
   core stack, the domains you actually worked in that overlap their problems;
   (b) 1–2 headline achievements with confirmed outcomes/scale from the
   evidence (e.g. "owned the cart → checkout → order-placement experience of a
   40+ locale multi-market storefront"); (c) leadership/ownership signals —
   led-end-to-end scope, founding-engineer/architecture ownership, specs or
   standards other engineers built against; (d) differentiators (design
   systems, Core Web Vitals, test discipline, AI-agent workflow authorship).
   Lead with the overlap; do not paste the profile summary verbatim if it
   doesn't speak to this role.
4. **Select and order bullets by relevance.** Per employer, lead with the bullet
   that answers the JD's #1 need. Drop bullets that don't serve this JD, even if
   they're impressive on their own — relevance beats volume. Keep the resume to
   ~1.5 pages for ≤10 yrs (never pad to fill; trim older/weaker projects to one
   bullet or cut them entirely — spearheads keep Full bullets and the space they
   save), up to 2 pages otherwise, unless the user says otherwise.
5. **Surface AI-assisted / agent-workflow work as a first-class differentiator.**
   If any source bullet describes authoring specs, skills, prompt templates, or
   code-generation tooling that directed an AI coding agent (not merely *using*
   an AI assistant), surface it — a dedicated bullet and, if strong, a summary
   clause — even when the JD doesn't explicitly ask for AI skills. In the current
   market this is a credibility signal for senior ICs and an edge over peers.
   Constraint: frame it accurately. The candidate *authored the specs/tooling
   that directed the agent*; never claim they built the AI product or an
   "orchestration engine" (check the source's Notes for accuracy for the exact
   boundary).
6. **Surface leadership signals honestly.** ATS "management/leadership" scores
   and human readers alike reward ownership language that the evidence already
   supports: "led … end to end", "founding engineer", "sole-authored the
   operating spec governing a 5-person team", "established the test baseline",
   "architected the transport layer used by every feature module". Put at least
   one such signal in the summary and let spearhead bullets carry them; never
   inflate to people-management ("managed a team of N") unless a source states
   it.
7. **Re-frame bullets into the JD's language (allowed — with constraints).**
   Rewrite phrasing so each selected bullet speaks to a JD need: surface the
   mechanism the JD cares about, use the JD's terminology where it's truthful
   ("component governance", "design system", "performance budget", "real-time
   validation"). Constraints:
   - Every factual claim (tool, scale, mechanism, outcome, ownership tier) must
     trace to the source Full/Short bullets or `PORTFOLIO.md`.
   - Never introduce a tool, metric, scope, or ownership level not in the
     source. Never upgrade "contributed to" into "owned".
   - Preserve team-vs-solo framing ("founding engineer on a 3-person team",
     "as part of an N-person team").
   - Strip every empty stat (line counts, blame %, commit/file/active-day
     counts, `N-line` measures) when copying a source bullet; restate the
     ownership and mechanism as a human credibility signal per "Tone & framing".
   - When condensing, cut detail — never downgrade the ownership verb and never
     fall back to naming features.
8. **Skills section.** Reorder groups so the JD-critical group leads, and within
   each group put JD-matching skills first. Never add a skill the candidate
   doesn't have; never remove true skills (they still help keyword coverage).
9. **Headline.** Keep the profile's headline unless the JD's target title is a
   reasonable match for the candidate's real level (e.g. "Senior Frontend
   Engineer" / "Frontend Engineer"). Never inflate (no "Staff"/"Lead" unless the
   evidence supports it).

**If no JD** (general master resume): build the summary with the same 4–6-line
shape (who → headline achievements → leadership signals → differentiators),
keep skills in profile order, and use the strongest **Full** bullets
per employer that together summarize the career (2–4 bullets each, seniority
scaled). Aim for a tight, complete one-to-two-page master.

## Tone & framing (non-negotiable — this is what makes it impressive)

This is the extraction skill's "Output style" lingo, applied to the resume. The
resume is read by recruiters and hiring managers at *other* companies. It must
read like a senior engineer describing their work — not a feature changelog,
not marketing copy, not an internal engineering artifact, and not a code dump.

- **No internal identifiers.** Never write file paths, component/function
  names, feature-flag names, environment/secret names, error codes, or ticket
  IDs. A candidate cannot leak their employer's internals.
- **Describe at the architectural level, not at the feature/line level.**
  Translate every implementation detail into the *behaviour* and *system-level
  concept* it realizes. Example: "Tracking Log, Sale Difference, and Issue Queue
  features" becomes "reconciliation and exception-handling workflows for bulk
  data review"; a batch update/delete endpoint becomes "repairs the cart in a
  single atomic operation"; a 401 handler becomes "transparent sign-out and
  re-authentication on session expiry".
- **Confident ownership language.** Where the evidence supports it, write
  "owned", "led", "designed", "architected", "built", "drove" — never "worked
  on", "helped with", "assisted with", "involved in", "participated in".
  Contributor-tier work stays honest ("contributed to") but is rarely worth a
  bullet.
- **Frame slices as domains, not lists.** Describe "the cart → checkout →
  order-placement experience", "the encrypted API transport layer used by every
  feature module" — not a stack of screens/pages you touched.
- **Every bullet = [what was built] + [the specific problem/mechanism it solves]
  + [outcome, only if confirmed].** A bullet that merely names what exists
  ("built X, Y, Z pages") is a failed bullet.
- **Achiever, not doer — lead with the change in the world.** Professional CV
  reviewers consistently flag mechanism-only sentences as task-based ("what I
  did" not "what changed because I did it"). Two real anti-examples flagged by
  such a review, and their corrected shape:
  - ✗ "Shipped login-aware pricing across booking surfaces and a performance
    pass removing a duplicate API call via server-side response caching" — two
    tasks in a row, no consequence.
    ✓ "Cut a redundant booking API call by serving login-aware pricing from a
    server-side response cache, trimming load on the booking path" — same facts,
    the outcome now leads.
  - ✗ "Extended the shared webview-to-native bridge — the contracts through
    which every module reaches native capabilities (header, share tray, back
    button, login handshake)" — pure definition of a thing.
    ✓ (unless the JD needs webview depth, cut it; a bridge-extension line with
    no outcome is not worth a slot. If kept: "Hardened the bridge every module
    relies on for native capabilities, keeping embedded flows release-safe
    across app versions".)
  - If the source carries a confirmed number (complexity/duplication deltas,
    pages shipped, locales supported, latency), lead the bullet with it.
    Otherwise close with the qualitative outcome the mechanism guarantees
    ("malformed entries never break a live page", "submissions are never
    silently lost") — never an invented metric.
- **Vary the ownership verbs.** "Created" and "Designed" as bullet openers read
  monotonous and passive to reviewers. Never open a bullet with "Created";
  spread openers across led / owned / drove / unified / hardened / established /
  engineered / consolidated / rebuilt / introduced, matched to the evidence's
  ownership tier — and never let one verb lead more than 1–2 bullets.
- **No empty stats — no git forensics on the resume.** Blame percentages,
  commit counts, and line counts are evidence for *you* — never resume copy.
  Strip any of these the moment you see one in a source bullet and restate the
  same fact as a human credibility signal instead:
  - **Banned:** line counts / LOC (`~21,500-line`, `~4,300 lines`, `~985-line`),
    line-share percentages (`53.6% of ~21,500 lines`, `77% of lines`), commit
    counts (`39 of 191 commits`, `706 commits`), active-day counts (`33 distinct
    active days`), file counts (`~10 files`, `184 test files`), and any
    `N-line`/`N-page`-style measure.
  - **Instead, write:** "largest single contributor to a shared component
    library", "sole author of its server-paginated data table", "founding
    engineer", "sole author of the AI-agent operating spec and code-generation
    tooling used by a 5-person team". The number of lines is never the point;
    the ownership and the problem solved are.
  - A genuine, confirmed *business* outcome (traffic, revenue, latency,
    error-rate deltas) may stay — but only if the source states it as confirmed,
    never a repo measurement.
- **No unbacked adjectives.** "Robust", "scalable", "seamless" are forbidden
  unless the same sentence carries the concrete mechanism that earns them.

## Step 4 — Write the Markdown resume

Use this exact structure (it is what the PDF renderer expects and what ATS
parsers handle best). Fill every `<...>` from `data/profile.md` — never invent
contact details:

```
# <Name from profile>
<Headline from profile>
[<Location> | ]<Email> | <Phone> | <LinkedIn> | <GitHub>

## Professional Summary
<4-6 lines>

## Skills
- Frontend: ...
- Tooling & Testing: ...
- AI-Assisted Development: ...
- Other: ...

## Professional Experience

### <Employer> — <City> (<Mon YYYY – Present/Mon YYYY>)
**<Role>**
- <bullet>
- <bullet>

### <Older employer> — <City> (<dates>)
**<Role>**
- <bullet>

... (one `###` per employer, newest first) ...

## Education
- <degree>

## Certifications
- <cert>
- <cert>
```

Conventions:
- Heading levels: `#` name, `##` sections, `###` employer lines. Title on the
  line right after `###` as a `**bold**` paragraph. Optional project
  sub-headings use a bold line with a trailing parenthesized tech stack
  (`**Lead Perfection — enterprise sales platform (React 19 | TypeScript)**`);
  the HTML renderer turns these into project-title + tech-stack blocks with
  their own bullets.
- Contact line: include `<Location> |` as the leading segment **only if** the
  profile's `## Identity` section defines a Location — read it at generation
  time, never hardcode it; when the profile has no Location under Identity,
  omit it entirely (the resume mirrors the profile).
- Bullets start with `- `. Dates as `Mon YYYY – Mon YYYY` (or `Present`).
- Each bullet follows the formula from "Tone & framing": ownership verb →
  what was built → the specific problem/mechanism → outcome (if confirmed).
  No internal feature names, no blame percentages, no "worked on/helped".
- Keep it **one column, text only**. No tables, no `---` rules, no emoji, no
  multi-column layouts, no header/footer fields.
- Spell out acronyms on first use where a JD might contain them (e.g. "Server-
  Side Rendering (SSR)") only if it aids a keyword match.

## Step 5 — Build HTML + PDF into a per-job folder, then report

1. Write the Markdown to `output/<slug>.md` (e.g.
   `output/<Candidate-Name>-<Company>.md`).
2. Ensure the Step 2.5 match analysis is saved to
   `output/<Company>/match-analysis.md` (section `## Resume`; see the note on
   shared files below).
3. Run the pipeline (from the workspace root):
   `.venv/bin/python scripts/build_resume.py output/<slug>.md`
   (if `.venv/bin/python` doesn't exist, use `python3`). This creates
   `output/<Company>/` with the three files:
   `<Company>/<slug>.md` (source),
   `.html` (styled, ATS-friendly, single-column), and `.pdf` (printed from the
   HTML via headless Chromium, A4 with 8 mm margins).
4. Sanity-check the PDF (system Python has `fitz`):
   `python3 -c "import fitz; d=fitz.open('output/<Company>/<slug>.pdf'); print(len(d), 'pages'); print(d[0].get_text())"`.
5. Report the folder path, the four file paths (md/html/pdf + match-analysis.md),
   the page count, and a one-line note on how the resume was tailored (which JD
   needs drove the spearhead/skill/bullet ordering, and any gap flags).

> **Shared `match-analysis.md`:** the cover-letter skill writes to the same file
> under a `## Cover Letter` section. If the file exists, keep other sections and
> only replace your own `## Resume` section.

## Self-check before finalizing

- **Match analysis done:** `output/<Company>/match-analysis.md` exists and every
  top-3 JD need maps to a `core`/`partial`/`gap` row; gaps are flagged, not
  hidden.
- **Traceability:** every claim traces to a `RESUME_BULLETS.md` Full/Short
  section or `PORTFOLIO.md`. Flag and drop anything pulled from "Notes for
  accuracy" or invented. No fabricated metrics, titles, or dates; team-framing
  preserved.
- **Per-bullet provenance:** each drafted bullet can be pointed back to its
  source project (file + project). If you cannot name the source, remove the
  bullet.
- **Tone:** no "worked on / helped with / assisted". No internal feature or
  screen names, file paths, or identifiers. No empty stats — no line counts
  (LOC), no blame percentages, no commit/file/active-day counts, no `N-line`
  measures. Every bullet carries a mechanism, not just a feature name or a stat.
- **Achiever test:** every bullet leads with or closes on a change-in-the-world
  (confirmed metric or qualitative outcome), not just a task; openers vary (no
  "Created" openers, no verb leading more than 1–2 bullets); summary is 4–6
  lines and carries at least one evidence-backed leadership signal.
- **Contact line:** mirrors `data/profile.md` — location segment present only
  if the profile's `## Identity` defines one.
- **JD fit (spearhead test):** would a hiring manager for *this* role see their
  #1 problem being solved in the first screen of page 1? If not, re-order or
  re-frame until the top of the resume answers the JD.
- **Skills:** all real (from `data/profile.md`); ordering, not invention.
- **Format:** one column, standard headings, no graphics/tables; PDF renders
  cleanly (text extractable, page count ≤ 2 unless the user asks for more).
