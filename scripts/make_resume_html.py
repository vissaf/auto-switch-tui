#!/usr/bin/env python3
"""Render a tailored Markdown resume into an ATS-friendly, single-column HTML
resume.

Pure stdlib. The output mirrors the canonical styled template (header with
name/headline/contact links, professional summary, grouped skills, experience
with job/project blocks, education, certifications). The page is A4 with an
8 mm print margin on all sides so the companion html_to_pdf.py produces a PDF
with the same geometry.

Usage:
    python3 scripts/make_resume_html.py <input.md> <output.html>
"""

import html
import re
import sys

CSS = """
    @page {
      size: A4;
      margin: 8mm;
    }
    *, *::before, *::after {
      box-sizing: border-box;
    }
    :root {
      --ink: #0f172a;
      --accent: #1e40af;
      --accent-soft: #dbe4f6;
      --body: #1e2735;
      --muted: #475569;
      --faint: #7c8aa0;
      --rule: #dfe6f0;
    }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      color: var(--body);
      background-color: #ffffff;
      line-height: 1.4;
      font-size: 9.5pt;
      margin: 0;
      padding: 0;
      -webkit-font-smoothing: antialiased;
    }
    a {
      color: inherit;
      text-decoration: none;
    }
    header {
      text-align: center;
      margin-bottom: 12px;
      padding-bottom: 10px;
      border-bottom: 2px solid var(--accent);
    }
    h1 {
      font-size: 21pt;
      font-weight: 700;
      letter-spacing: -0.3px;
      margin: 0 0 3px 0;
      color: var(--ink);
    }
    .headline {
      font-size: 11pt;
      font-weight: 600;
      color: var(--accent);
      margin-bottom: 6px;
    }
    .contact-links {
      font-size: 8.5pt;
      color: var(--muted);
      display: flex;
      justify-content: center;
      align-items: baseline;
      gap: 7px;
      flex-wrap: wrap;
    }
    .contact-links a:hover {
      color: var(--accent);
      text-decoration: underline;
    }
    .divider {
      color: var(--accent-soft);
      font-size: 8pt;
    }
    section {
      margin-bottom: 11px;
    }
    .section-title {
      font-size: 10pt;
      font-weight: 700;
      color: var(--accent);
      text-transform: uppercase;
      letter-spacing: 1.1px;
      border-left: 3px solid var(--accent);
      border-bottom: 1px solid var(--rule);
      padding-left: 7px;
      padding-bottom: 3px;
      margin-bottom: 7px;
      page-break-after: avoid;
    }
    p {
      margin: 0;
      text-align: left;
    }
    .skills-grid {
      display: flex;
      flex-direction: column;
      gap: 3px;
    }
    .skill-item {
      font-size: 9pt;
      line-height: 1.38;
    }
    .skill-label {
      font-weight: 700;
      color: var(--ink);
    }
    .job-entry {
      margin-bottom: 9px;
    }
    .job-header {
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      gap: 12px;
      font-weight: 700;
      color: var(--ink);
      font-size: 10pt;
      page-break-after: avoid;
    }
    .job-header span:last-child {
      font-weight: 500;
      color: var(--faint);
      font-size: 8.5pt;
      white-space: nowrap;
    }
    .job-subheader {
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      gap: 12px;
      font-weight: 600;
      color: var(--accent);
      font-size: 9pt;
      margin: 1px 0 4px 0;
      page-break-after: avoid;
    }
    .job-subheader span:last-child {
      font-weight: 500;
      color: var(--faint);
      font-size: 8.5pt;
      white-space: nowrap;
    }
    .project-block {
      margin-top: 5px;
      margin-bottom: 5px;
      page-break-inside: avoid;
    }
    .project-title {
      font-weight: 700;
      color: var(--ink);
      font-size: 9pt;
      margin-bottom: 2px;
      page-break-after: avoid;
    }
    .tech-stack {
      font-weight: 500;
      color: var(--faint);
      font-size: 8.5pt;
    }
    ul {
      margin: 0;
      padding-left: 15px;
    }
    li {
      margin-bottom: 2px;
      font-size: 9pt;
      line-height: 1.32;
      text-align: left;
    }
    li::marker {
      color: var(--accent);
      font-size: 8pt;
    }
    .meta-list {
      list-style-type: square;
      padding-left: 15px;
    }
    .meta-list li {
      margin-bottom: 1px;
    }
    @media print {
      body {
        font-size: 9pt;
        line-height: 1.3;
      }
      li {
        line-height: 1.3;
      }
      a {
        color: inherit;
      }
      section {
        margin-bottom: 10px;
      }
    }
"""

EMPLOYER_RE = re.compile(r"^(.*?)\s+—\s+(.*?)\s*\(([^()]*)\)$")
PROJECT_RE = re.compile(r"^(.*?)\s*\(([^()]*)\)$")
EDU_RE = re.compile(r"^(.*?)\s+—\s+(.*?)\s*\(([^()]*)\)$")


def esc(text):
    return html.escape(text, quote=True)


def parse_employer(s):
    m = EMPLOYER_RE.match(s)
    if m:
        return {
            "employer": m.group(1).strip(),
            "city": m.group(2).strip(),
            "dates": m.group(3).strip(),
            "role": "",
            "projects": [],
            "bullets": [],
        }
    return {"employer": s, "city": "", "dates": "", "role": "", "projects": [], "bullets": []}


def parse_education(s):
    m = EDU_RE.match(s)
    if m:
        return {"degree": m.group(1).strip(), "college": m.group(2).strip(), "dates": m.group(3).strip()}
    return {"degree": s, "college": "", "dates": ""}


def split_label(s):
    if ":" in s:
        label, value = s.split(":", 1)
        return label.strip(), value.strip()
    return "", s.strip()


def parse(md_text):
    doc = {
        "name": "",
        "headline": "",
        "contact": [],
        "summary": "",
        "skills": [],
        "jobs": [],
        "education": [],
        "certifications": [],
    }
    section = None
    job = None
    project = None

    for raw in md_text.split("\n"):
        stripped = raw.strip()
        if not stripped:
            continue
        if stripped.startswith("# "):
            doc["name"] = stripped[2:].strip()
        elif stripped.startswith("## "):
            section = stripped[3:].strip()
            job = None
            project = None
        elif stripped.startswith("### "):
            job = parse_employer(stripped[4:].strip())
            doc["jobs"].append(job)
            project = None
        elif stripped.startswith("**") and stripped.endswith("**"):
            inner = stripped[2:-2].strip()
            if section == "Professional Experience" and job is not None:
                m = PROJECT_RE.match(inner)
                if m:
                    project = {"title": m.group(1).strip(), "tech": m.group(2).strip(), "bullets": []}
                    job["projects"].append(project)
                    continue
            if job is not None:
                job["role"] = inner
            project = None
        elif stripped.startswith("- ") or stripped.startswith("* "):
            text = stripped[2:].strip()
            if section == "Skills":
                label, value = split_label(text)
                doc["skills"].append((label, value))
            elif section == "Professional Experience" and job is not None:
                if project is not None:
                    project["bullets"].append(text)
                else:
                    job["bullets"].append(text)
            elif section == "Education":
                doc["education"].append(parse_education(text))
            elif section == "Certifications":
                doc["certifications"].append(text)
        else:
            if doc["headline"] == "" and doc["name"]:
                doc["headline"] = stripped
            elif doc["headline"] and section is None and not doc["contact"]:
                doc["contact"] = [p.strip() for p in stripped.split("|") if p.strip()]
            elif section == "Professional Summary":
                doc["summary"] += (" " if doc["summary"] else "") + stripped
    return doc


def render_contact(parts):
    spans = []
    for p in parts:
        if "@" in p:
            spans.append(f'<span><a href="mailto:{esc(p)}">{esc(p)}</a></span>')
        elif "linkedin" in p or "github" in p:
            href = p if p.startswith("http") else "https://" + p
            spans.append(f'<span><a href="{esc(href)}">{esc(p)}</a></span>')
        else:
            spans.append(f"<span>{esc(p)}</span>")
    out = []
    for i, s in enumerate(spans):
        if i:
            out.append('<span class="divider">•</span>')
        out.append(s)
    return "\n      ".join(out)


def render_jobs(jobs):
    blocks = []
    for job in jobs:
        lines = ['    <div class="job-entry">']
        lines.append(
            f'      <div class="job-header"><span>{esc(job["employer"])}</span><span>{esc(job["city"])}</span></div>'
        )
        lines.append(
            f'      <div class="job-subheader"><span>{esc(job["role"])}</span><span>{esc(job["dates"])}</span></div>'
        )
        for proj in job["projects"]:
            lines.append('      <div class="project-block">')
            lines.append(
                f'        <div class="project-title">{esc(proj["title"])} <span class="tech-stack">({esc(proj["tech"])})</span></div>'
            )
            lines.append("        <ul>")
            for b in proj["bullets"]:
                lines.append(f"          <li>{esc(b)}</li>")
            lines.append("        </ul>")
            lines.append("      </div>")
        if job["bullets"]:
            lines.append("      <ul>")
            for b in job["bullets"]:
                lines.append(f"        <li>{esc(b)}</li>")
            lines.append("      </ul>")
        lines.append("    </div>")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def render_education(edus):
    blocks = []
    for e in edus:
        blocks.append(
            f'    <div class="job-header"><span>{esc(e["college"])}</span><span>{esc(e["dates"])}</span></div>\n'
            f'    <div class="job-subheader"><span>{esc(e["degree"])}</span><span></span></div>'
        )
    return "\n".join(blocks)


def md_to_html(md_text):
    d = parse(md_text)

    skills = "\n".join(
        f'      <div class="skill-item"><span class="skill-label">{esc(label)}:</span> {esc(value)}</div>'
        if label
        else f'      <div class="skill-item">{esc(value)}</div>'
        for label, value in d["skills"]
    )
    certs = "\n".join(f"      <li>{esc(c)}</li>" for c in d["certifications"])

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{esc(d['name'])} - Resume</title>
  <style>{CSS}
  </style>
</head>
<body>

  <header>
    <h1>{esc(d['name'])}</h1>
    <div class="headline">{esc(d['headline'])}</div>
    <div class="contact-links">
      {render_contact(d['contact'])}
    </div>
  </header>

  <section>
    <div class="section-title">Professional Summary</div>
    <p>
      {esc(d['summary'])}
    </p>
  </section>

  <section>
    <div class="section-title">Skills</div>
    <div class="skills-grid">
{skills}
    </div>
  </section>

  <section>
    <div class="section-title">Professional Experience</div>

{render_jobs(d['jobs'])}
  </section>

  <section>
    <div class="section-title">Education</div>
{render_education(d['education'])}
  </section>

  <section>
    <div class="section-title">Certifications</div>
    <ul class="meta-list">
{certs}
    </ul>
  </section>

</body>
</html>
"""


def main():
    if len(sys.argv) < 3:
        print("usage: make_resume_html.py <input.md> <output.html>")
        sys.exit(1)
    with open(sys.argv[1], "r", encoding="utf-8") as f:
        md_text = f.read()
    with open(sys.argv[2], "w", encoding="utf-8") as f:
        f.write(md_to_html(md_text))
    print("wrote", sys.argv[2])


if __name__ == "__main__":
    main()
