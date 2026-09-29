---
name: job-match-topup
description: Judge a set of job candidates against the candidate's real profile (data/profile.md) and Work experiences evidence (data/work-experiences/), and write back a judged.json with honest, calibrated match scores and one-line verdicts. Use when the user asks to "judge the top candidates", "do the LLM top-up", "re-score these jobs", or after auto-switch exported output/llm-topup/candidates.json — to override the app's keyword-based match with an LLM's evidence-grounded judgment.
compatibility: any agent harness with file tools (opencode, Claude Code, Codex, Pi, dsh, Cursor)
---

# Job Match Top-up (LLM judge)

The `auto_switch` app ranks scraped jobs with a deterministic, evidence-grounded
engine (skill tiers + coverage scoring + optional local embeddings). When its
LLM top-up flag is on, it exports the top candidates to:

- `<workspace>/output/llm-topup/candidates.json`  (machine-readable, use this)
- `<workspace>/output/llm-topup/candidates.md`    (human-readable)

Your job: judge each candidate against the candidate's **actual evidence** and
write back `<workspace>/output/llm-topup/judged.json`. The next app run ingests
`judged.json` and overrides each job's score with yours (kept in `llm_score`),
and shows your verdict in the detail view.

The workspace is the repository containing this SKILL.md (this file lives at
`.agents/skills/job-match-topup/SKILL.md`; the workspace root is two levels up).
If you're already running inside it, paths below are relative to the repo root;
otherwise resolve them from the SKILL.md location.

## Inputs you must read

1. `data/profile.md` — the canonical profile: `## Identity` (Headline,
   "Years of experience"), `## Professional summary`, `## Skills`, and the
   `## Experience matrix` proficiency tiers.
2. `data/work-experiences/**/RESUME_BULLETS.md` and `**/PORTFOLIO.md` — the
   evidence of what was actually built. **Read these; do not guess.**
3. `output/llm-topup/candidates.json` — the jobs to judge.

## The one non-negotiable rule

**Do not overclaim.** Credit a skill only if it is backed by `data/profile.md`
"Skills" or an actual `PORTFOLIO.md` / `RESUME_BULLETS.md` claim. The
"Notes for accuracy (private — do not overclaim)" sections are interview-prep
warnings — they often describe things the candidate did *not* do or that aren't
git-verified. Never use those sections as evidence for a *higher* score; use
them only to avoid crediting something that wasn't actually done.

## Step 1 — Establish the candidate anchor (from data, never assumed)

From `data/profile.md`:

- **Target level**: parse the Headline (e.g. "Senior Frontend Engineer" →
  senior; "Staff/Principal/Lead" → staff-level; "Frontend Developer" → general).
- **Years of experience**: the `## Identity` "Years of experience" field. If
  it is absent, estimate from the earliest/latest dates inside the work
  experience files. If truly unknown, treat the candidate as level-agnostic and
  **skip the level axis** (no caps) — never invent seniority.

Everything below is computed *relative to this anchor*.

## Step 2 — Two-axis scoring

Score each job 0–100 as **stack coverage × level fit**.

### Axis 1: stack coverage

How much of the JD's required stack the evidence actually covers. Derive the
candidate's proficiency tiers from the `## Experience matrix` (it overrides the
app's auto-mined tiers; skills absent from it fall back to the app's registry).
Map the tiers like this:

| Tier | Earned credit | Meaning |
|---|---|---|
| core | 100% | years of shipped evidence, owns the skill |
| strong | ~88% | heavy, verified use |
| secondary | ~72% | known, but older/domain-specific use |
| adjacent | ~66% | not used but directly transferable |
| familiar | ~45% | supporting skill, light use |
| unfamiliar | ~30% | same family, never used |
| foreign | ~0-12% | different discipline |

Example bands (recalibrate from the actual matrix — these illustrate the shape,
not a fixed persona): JD centred on the candidate's core stack → 90-100; strong
tier → 75-90; secondary/transferable framework → 60-85; unfamiliar framework →
50-70; different discipline (backend-only, native mobile, ML infra) → <45.
Hard requirements the evidence doesn't cover at all (a backend system, an ML
pipeline, a CMS the candidate never touched) pull a JD down proportionally to
how central they are in the JD.

### Axis 2: level fit (the seniority axis)

Extract the **role level** from the title + description and the **minimum
required years** the JD states ("3+ years", "5-8 years of experience",
"minimum 4 years"). Levels: junior/entry (0-2y), mid (2-5y), senior (5-8y),
staff/principal/lead (8+y, org-wide scope).

Compare with the candidate anchor and apply **hard caps**:

| Situation | Cap | Why |
|---|---|---|
| Role level below the candidate's (senior person → junior/mid role) | 55 junior, 70 mid | down-level: comp regression, no senior scope, flight risk — a mismatch even if the stack fits |
| Role at the candidate's level | full band | normal |
| Role one level above (staff/principal) | 80 unless the evidence shows org-wide scope (architecture ownership, team/platform leadership) | stretch roles need evidence, not hope |
| Required years far exceed the candidate's (e.g. 10+ vs 6) | 85 | seniority gap that stack coverage cannot close |

Rules:

- A **junior/mid role is never a 90+ match for a senior candidate**, no matter
  how perfectly the stack fits. Say so in the verdict.
- If the candidate's years are unknown, apply **no caps** — judge stack
  coverage alone.
- If the JD does not state years and the title is level-neutral, treat it as
  the candidate's level.

The final score must be consistent with both axes: never rubber-stamp the
app's `structural_score`; re-derive from evidence. But if your judgment agrees
with it, keep the number consistent so the app isn't whipsawed.

## Verdict

One short sentence (≤ 40 words) naming the *evidence* and — whenever the level
axis moved the score — the level/years mismatch, e.g. "Senior React/Next scope
fully evidenced; level aligned, no gaps." or "Stack core, but this is a junior
(1-2y) role — overqualified, capped at 55."

## Output

Write `<workspace>/output/llm-topup/judged.json` as a JSON object keyed by the
candidate's `id` (from `candidates.json`), containing only the jobs you
actually judged:

```json
{
  "greenhouse-123": {
    "score": 88,
    "level": "senior",
    "verdict": "Senior React/Next scope fully evidenced; level aligned, no gaps."
  },
  "lever-456": {
    "score": 45,
    "level": "junior",
    "verdict": "Stack core, but a junior (1-2y) role — overqualified, capped."
  }
}
```

- `score` must be an integer 0–100.
- `level` must be one of `junior`, `mid`, `senior`, `staff`, or `unknown` —
  the role's level as you classified it.
- `verdict` must be a string.
- Do not include jobs you did not judge.
