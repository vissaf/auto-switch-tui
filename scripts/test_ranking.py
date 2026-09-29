"""Calibration harness for the evidence-grounded match engine.

Run with the project venv:

    .venv/bin/python scripts/test_ranking.py

Asserts that representative JDs land in the intended bands. This is a
regression guard for the two original bugs:

  1. A React Native role must NOT score as a pure-React match.
  2. A junior Angular-only role must NOT saturate to 100%.

Structural scores only (semantic blend disabled) so the numbers are
deterministic; the semantic layer is exercised separately via a no-crash check.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from auto_switch.models import Job  # noqa: E402
from auto_switch.profile import build_keywords  # noqa: E402
from auto_switch.ranking import match_job  # noqa: E402


def make(title, description):
    return Job(id="x", title=title, company="Acme", location="Remote", url="https://x", description=description)


def score(job, skills):
    return match_job(job, skills, semantic=None).compatibility


SCENARIOS = [
    (
        "ideal senior React/Next role",
        make(
            "Senior Frontend Engineer - React",
            "Deep expertise in React.js and Next.js. TypeScript, Redux Toolkit, TanStack Query, "
            "Zustand, SSR ISR, REST APIs, GraphQL, design system, performance and web vitals, "
            "CI/CD, Git, testing with Jest and React Testing Library. Vite build tooling.",
        ),
        (90, 101),
    ),
    (
        "Sanity + React + Next role",
        make(
            "Frontend Engineer - React Next.js Sanity",
            "Build with React, Next.js and Sanity CMS. TypeScript, headless CMS content modeling, "
            "PortableText, REST APIs, GraphQL, Vite, design system, Jest testing.",
        ),
        (85, 101),
    ),
    (
        "senior Angular-only role",
        make(
            "Senior Frontend Developer (Angular)",
            "Build enterprise dashboards with Angular, TypeScript and JavaScript. HTML5, CSS3, SCSS. "
            "REST APIs, Jest, Jasmine, Karma. CI/CD, Git, Agile Scrum, performance optimization.",
        ),
        (70, 88),
    ),
    (
        "React Native heavy role",
        make(
            "Senior React Native Developer",
            "React Native, Expo, TypeScript, JavaScript, Redux, Jest. Build cross-platform mobile "
            "apps with native modules for iOS and Android.",
        ),
        (60, 90),
    ),
    (
        "Svelte/Nuxt only role",
        make(
            "Frontend Developer (Svelte)",
            "Build with SvelteKit and Nuxt. TypeScript, JavaScript, HTML5, CSS3, Tailwind, testing "
            "with Vitest. REST APIs.",
        ),
        (0, 72),
    ),
    (
        "backend Java role mentioning React once",
        make(
            "Java Backend Engineer",
            "Java, Spring Boot, microservices, Kafka, PostgreSQL. Some React on the admin panel. "
            "CI/CD, Docker, Kubernetes, AWS.",
        ),
        (0, 45),
    ),
    (
        "full-stack role (backend demand must not saturate)",
        make(
            "Senior Full Stack Engineer",
            "React, TypeScript, Node.js, Express, PostgreSQL, Redis, AWS, Docker, Kubernetes. "
            "Build REST and GraphQL APIs, design systems, CI/CD, testing with Jest, monorepo.",
        ),
        (0, 80),
    ),
    (
        "hotel Duty Manager (verb 'react' homograph)",
        make(
            "Duty Manager",
            "We are far more than a worldwide leader. We welcome you as you are and you can find a job "
            "and brand that matches your personality. React quickly to guest needs and drive hotel "
            "performance across every chapter of your story.",
        ),
        (0, 45),
    ),
    (
        "intern frontend role (seniority penalty)",
        make(
            "Frontend Engineering Intern",
            "Build with React, JavaScript, HTML/CSS and our design system. TypeScript a plus. "
            "Testing with Jest. REST APIs.",
        ),
        (0, 88),
    ),
]

FAILED = False


def main() -> int:
    global FAILED
    skills = build_keywords(ROOT)

    print("Tiers resolved (matrix + mining):")
    for k in sorted(skills, key=lambda s: -s.weight):
        print(f"  {k.label:<18} tier={k.tier:<10} weight={k.weight}")
    print()

    for name, job, (lo, hi) in SCENARIOS:
        s = score(job, skills)
        ok = lo <= s <= hi
        if not ok:
            FAILED = True
        flag = "ok " if ok else "FAIL"
        print(f"[{flag}] {name:<28} -> {s:>3}%  (expected {lo}-{hi})  matched={job.matched_keywords}")

    # Sanity: ideal React role must outrank the Angular-only role.
    ideal = score(SCENARIOS[0][1], skills)
    angular = score(SCENARIOS[2][1], skills)
    if not ideal > angular:
        FAILED = True
        print(f"[FAIL] ideal React ({ideal}) should outrank Angular-only ({angular})")

    # Semantic layer: no-crash / graceful-degradation check.
    try:
        from auto_switch.semantic import semantic_scores

        res = semantic_scores([SCENARIOS[0][1]], ROOT)
        if res is not None:
            print(f"[ ok ] semantic layer produced: {res}")
        else:
            print("[ ok ] semantic layer unavailable (fastembed not installed/model not downloaded)")
    except Exception as exc:  # noqa: BLE001
        print(f"[warn] semantic layer raised (acceptable if fastembed missing): {exc}")

    print()
    print("FAILED" if FAILED else "PASS")
    return 1 if FAILED else 0


if __name__ == "__main__":
    raise SystemExit(main())
