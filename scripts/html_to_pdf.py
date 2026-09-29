#!/usr/bin/env python3
"""Print an ATS-friendly HTML resume to PDF via headless Chromium (Playwright).

Renders exactly like a browser "Print to PDF": honors the page's @media print
styles and layout (including flexbox), on A4 with an 8 mm margin on all sides.
Header/footer are disabled.

Usage:
    python3 scripts/html_to_pdf.py <input.html> <output.pdf>
"""

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright


def html_to_pdf(html_path, pdf_path, margin=None):
    uri = Path(html_path).resolve().as_uri()
    out = str(Path(pdf_path).resolve())
    margins = margin or {"top": "8mm", "bottom": "8mm", "left": "8mm", "right": "8mm"}
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(uri, wait_until="networkidle")
        page.pdf(
            path=out,
            format="A4",
            margin=margins,
            print_background=True,
        )
        browser.close()


def main():
    if len(sys.argv) < 3:
        print("usage: html_to_pdf.py <input.html> <output.pdf>")
        sys.exit(1)
    html_to_pdf(sys.argv[1], sys.argv[2])
    print("wrote", sys.argv[2])


if __name__ == "__main__":
    main()
