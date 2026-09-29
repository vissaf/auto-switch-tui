#!/usr/bin/env python3
"""Build a complete, ATS-friendly resume package for one job.

Given a tailored Markdown resume (e.g. output/Company/company-resume.md or
output/Jane-Doe-Company.md), this writes a per-job folder (output/<Company>/)
containing three files:

    <Company>/<base>.md     (the Markdown source)
    <Company>/<base>.html   (styled, single-column HTML)
    <Company>/<base>.pdf    (printed from the HTML, A4, 8 mm margins)

Usage:
    .venv/bin/python scripts/build_resume.py output/<Company>/<resume>.md
"""

import os
import re
import sys
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from make_resume_html import md_to_html  # noqa: E402
from html_to_pdf import html_to_pdf  # noqa: E402


def _resolve_company_and_outdir(md_path: str) -> tuple[str, str, str]:
    """Determine (company_name, out_dir, base_filename) from input path."""
    md_abs = Path(md_path).resolve()
    parent = md_abs.parent
    base = md_abs.stem

    # If the file is already inside a company directory under output/ (e.g., output/Acme-Corp/)
    if parent.parent.name == "output":
        company = parent.name
        out_dir = str(parent)
        return company, out_dir, base

    # If the file is directly under output/ or elsewhere:
    # Deduce company by stripping candidate prefix and resume suffixes
    cleaned = base
    cleaned = re.sub(r"^[A-Z][a-z]+-[A-Z][a-z]+-", "", cleaned)
    cleaned = re.sub(r"^[Rr]esume-?", "", cleaned)
    cleaned = re.sub(r"-[Rr]esume$", "", cleaned)
    cleaned = cleaned.strip("-")

    company = cleaned
    if parent.name == "output":
        for child in parent.iterdir():
            if child.is_dir() and child.name.lower() == cleaned.lower().replace("_", "-"):
                company = child.name
                break
        out_dir = str(parent / company)
    else:
        out_dir = str(parent)

    os.makedirs(out_dir, exist_ok=True)
    return company, out_dir, base


def main():
    if len(sys.argv) < 2:
        print("usage: build_resume.py <resume.md>")
        sys.exit(1)

    md_path = os.path.abspath(sys.argv[1])
    if not os.path.isfile(md_path):
        print("not found:", md_path)
        sys.exit(1)

    company, out_dir, base = _resolve_company_and_outdir(md_path)
    os.makedirs(out_dir, exist_ok=True)

    with open(md_path, "r", encoding="utf-8") as f:
        md_text = f.read()

    md_out = os.path.join(out_dir, base + ".md")
    html_out = os.path.join(out_dir, base + ".html")
    pdf_out = os.path.join(out_dir, base + ".pdf")

    if os.path.abspath(md_out) != md_path:
        with open(md_out, "w", encoding="utf-8") as f:
            f.write(md_text)

    with open(html_out, "w", encoding="utf-8") as f:
        f.write(md_to_html(md_text))
    html_to_pdf(html_out, pdf_out)

    print("built:", out_dir)
    for path in (md_out, html_out, pdf_out):
        print("  ", path)


if __name__ == "__main__":
    main()

