# Work Experiences — evidence format

One folder per employer, one folder per project inside it. The
`resume-builder` and `cover-letter` skills only ever claim what is written
here, so keep these files honest and specific.

```
data/work-experiences/
└── 01. <Employer>/
    └── <Project Name>/
        ├── RESUME_BULLETS.md   # required — the only bullet source
        └── PORTFOLIO.md        # optional — deeper context for expansions
```

## RESUME_BULLETS.md

Two bullet sets — **Full version** (5–7 bullets) and **Short version** (3–4
bullets). Each bullet: `[what was built/fixed] + [specific mechanism or problem
solved, at the architectural level] + [outcome, only if confirmed]`. No
internal identifiers (file paths, feature-flag names, error codes), no empty
stats (line counts, blame %, commit counts).

A private **"Notes for accuracy"** section may be appended — it is *never* used
on the resume; it only tells generators what NOT to overclaim.

The quickest way to produce these files is the bundled
`resume-codebase-extraction` skill (git-blame-backed). If your agent supports
the `skill` tool, just ask: "extract my contribution from this codebase using
the resume-codebase-extraction skill".

## PORTFOLIO.md

~1 page for a senior/staff engineer: stack + team size, one section per system
you are sole/majority author of, and a "collaboration model" section stating
plainly what was NOT built by you. Written at the architectural level — no
internal identifiers.
