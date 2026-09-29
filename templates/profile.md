# <Your Name> — Canonical Profile (single source of truth for resume generation)

This file holds the personal / identity details that are constant across every
generated resume. Edit here, and the `resume-builder` skill picks up changes
automatically. Work-experience content lives in `data/work-experiences/` and is
merged in at generation time — do not duplicate it here.

## Identity

- Name: <Your Name>
- Headline: <Your Target Title, e.g. Senior Frontend Engineer>
- Years of experience: <X+ years, e.g. 6+>
- Email: <you@example.com>
- Phone: <+XX XXXX XXX XXX>
- LinkedIn: <linkedin.com/in/your-handle>
- GitHub: <github.com/your-handle>
- Location: <City, Country>

## Professional summary (base — tailored per job description)

<2-4 lines: years of experience, core stack, the domains you actually worked
in. Keep every claim backed by data/work-experiences/.>

## Skills

- <Category>: <skills, comma-separated>
- Tooling & Testing: <...>
- AI-Assisted Development: <...>
- Other: <...>

## Experience matrix

Proficiency tiers used by the job matcher (`auto_switch`). Tiers: `core`,
`strong`, `secondary`, `familiar` (skills you hold) or `adjacent` (transferable
framework you have not used), `unfamiliar` (adjacent stack, not used), `foreign`
(different discipline). This section overrides the auto-mined tiers; skills not
listed here fall back to corpus mining.

> Note: the matcher's skill registry (`auto_switch/profile.py` → `SKILLS`) is
> calibrated for frontend roles. If your stack differs, add your own skills
> there (label, aliases, weight, default tier) so JD demand can be matched.

| Skill | Tier |
|-------|------|
| <your skill 1> | core |
| <your skill 2> | strong |

## Education

- <Degree> — <Institution> (<YYYY – YYYY>)

## Certifications & awards

- <Certification>

## Optional extras (not on resume by default)

- <Anything you want stored but not on the resume by default>
