#!/usr/bin/env python3
"""Build a complete, ATS-friendly cover letter package for one job.

Given a tailored Markdown cover letter (e.g. output/Chalhoub-Group/chalhoub-group-cover-letter.md
or output/chalhoub-group-cover-letter.md), this writes/updates a per-job folder containing:

    <Company>/<base>.md     (the Markdown source)
    <Company>/<base>.html   (styled, single-page business letter HTML)
    <Company>/<base>.pdf    (printed from HTML via Playwright, A4, single page)

Usage:
    .venv/bin/python scripts/build_cover_letter.py <cover-letter.md>
"""

import os
import re
import sys
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from make_cover_letter_html import md_to_html  # noqa: E402
from html_to_pdf import html_to_pdf  # noqa: E402


def _resolve_company_and_outdir(md_path: str) -> tuple[str, str, str]:
    """Determine (company_name, out_dir, base_filename) from input path."""
    md_abs = Path(md_path).resolve()
    parent = md_abs.parent
    base = md_abs.stem

    # If the file is already inside a company directory under output/ (e.g., output/Chalhoub-Group/)
    if parent.parent.name == "output":
        company = parent.name
        out_dir = str(parent)
        return company, out_dir, base

    # If the file is directly under output/ or elsewhere:
    # Deduce company by stripping candidate prefix and cover-letter suffixes
    cleaned = base
    # Strip prefixes like 'Jane-Doe-', 'Cover-Letter-'
    cleaned = re.sub(r"^[A-Z][a-z]+-[A-Z][a-z]+-", "", cleaned)
    cleaned = re.sub(r"^[Cc]over-[Ll]etter-?", "", cleaned)
    # Strip suffixes like '-cover-letter', '-Cover-Letter'
    cleaned = re.sub(r"-[Cc]over-[Ll]etter$", "", cleaned)
    cleaned = cleaned.strip("-")

    # Look for existing directory under parent with matching name (case-insensitive)
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
        print("usage: build_cover_letter.py <cover-letter.md>")
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

    # Convert company slug to human name for recipient display if formatted as slug
    company_display = company.replace("-", " ")
    html_content = md_to_html(md_text, company=company_display)

    with open(html_out, "w", encoding="utf-8") as f:
        f.write(html_content)

    html_to_pdf(html_out, pdf_out)

    pages = 0
    try:
        import fitz
        doc = fitz.open(pdf_out)
        pages = len(doc)
        doc.close()
    except Exception:
        # Fallback to system python3 if fitz is installed there
        try:
            import subprocess
            proc = subprocess.run(
                ["python3", "-c", f"import fitz; d=fitz.open('{pdf_out}'); print(len(d))"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if proc.returncode == 0 and proc.stdout.strip().isdigit():
                pages = int(proc.stdout.strip())
        except Exception:
            pass

    page_info = f" ({pages} page{'s' if pages != 1 else ''})" if pages else ""
    print(f"built: {out_dir}{page_info}")
    for path in (md_out, html_out, pdf_out):
        print("  ", path)

    if pages > 1:
        print(f"WARNING: Cover letter rendered to {pages} pages; expected strictly 1 page.")


if __name__ == "__main__":
    main()
