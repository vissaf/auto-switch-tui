#!/usr/bin/env python3
"""Render a tailored Markdown cover letter into an ATS-friendly, single-page HTML
cover letter.

Pure stdlib. The output mirrors the resume's visual identity (same typography,
palette, and header style) while adhering to professional business letter
conventions (date, recipient block, salutation, natural paragraph flow with AI
structural scaffolding stripped, formal sign-off). The page is A4 with
print margins tuned for a guaranteed single-page layout.

Usage:
    python3 scripts/make_cover_letter_html.py <input.md> <output.html> [--company <Company>]
"""

import html
import re
import sys
from datetime import datetime
from pathlib import Path

CSS = """
    @page {
      size: A4;
      margin: 12mm 16mm;
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
      line-height: 1.5;
      font-size: 9.8pt;
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
      margin-bottom: 18px;
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
      font-size: 10.5pt;
      font-weight: 600;
      color: var(--accent);
      margin-bottom: 6px;
      letter-spacing: 0.1px;
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
    .letter-container {
      max-width: 100%;
      margin: 0 auto;
    }
    .letter-meta {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      margin-bottom: 16px;
      font-size: 9.2pt;
      color: var(--muted);
    }
    .letter-date {
      font-weight: 500;
      color: var(--body);
    }
    .recipient-block {
      line-height: 1.35;
      text-align: left;
    }
    .recipient-name {
      font-weight: 600;
      color: var(--ink);
    }
    .recipient-company {
      font-weight: 500;
      color: var(--muted);
    }
    .salutation {
      font-size: 10pt;
      font-weight: 600;
      color: var(--ink);
      margin-bottom: 12px;
    }
    .letter-body {
      display: flex;
      flex-direction: column;
      gap: 10px;
    }
    .letter-para {
      margin: 0;
      text-align: justify;
      line-height: 1.48;
      font-size: 9.6pt;
      color: var(--body);
    }
    .signoff-block {
      margin-top: 18px;
      page-break-inside: avoid;
    }
    .signoff-closing {
      margin: 0 0 16px 0;
      font-size: 9.8pt;
      color: var(--body);
    }
    .signoff-name {
      font-size: 11pt;
      font-weight: 700;
      color: var(--ink);
      line-height: 1.2;
    }
    .signoff-title {
      font-size: 9pt;
      font-weight: 500;
      color: var(--accent);
      margin-top: 2px;
    }
    @media print {
      body {
        font-size: 9.5pt;
        line-height: 1.45;
      }
      .letter-para {
        font-size: 9.3pt;
        line-height: 1.44;
      }
      header {
        margin-bottom: 14px;
        padding-bottom: 8px;
      }
      .letter-meta {
        margin-bottom: 12px;
      }
      .signoff-block {
        margin-top: 14px;
      }
    }
"""

SCAFFOLD_HEADERS = {"opening", "body", "closing", "cover letter", "match analysis"}


def esc(text: str) -> str:
    return html.escape(text, quote=True)


def format_inline_markdown(text: str) -> str:
    """Format bold, italic, and links in markdown text."""
    # Links: [text](url)
    text = re.sub(
        r"\[(.*?)\]\((.*?)\)",
        lambda m: f'<a href="{esc(m.group(2))}" style="color:var(--accent);text-decoration:underline;">{esc(m.group(1))}</a>',
        text,
    )
    # Bold: **bold**
    text = re.sub(r"\*\*(.*?)\*\*", lambda m: f"<strong>{esc(m.group(1))}</strong>", text)
    # Italic: *italic* or _italic_
    text = re.sub(r"(?<!\*)\*(?!\*)(.*?)(?<!\*)\*(?!\*)", lambda m: f"<em>{esc(m.group(1))}</em>", text)
    return text


def render_contact(parts: list[str]) -> str:
    spans = []
    for p in parts:
        p_clean = p.strip()
        if not p_clean:
            continue
        if "@" in p_clean and not p_clean.startswith("http"):
            spans.append(f'<span><a href="mailto:{esc(p_clean)}">{esc(p_clean)}</a></span>')
        elif "linkedin.com" in p_clean or "github.com" in p_clean:
            href = p_clean if p_clean.startswith("http") else "https://" + p_clean
            spans.append(f'<span><a href="{esc(href)}">{esc(p_clean)}</a></span>')
        else:
            spans.append(f"<span>{esc(p_clean)}</span>")
    out = []
    for i, s in enumerate(spans):
        if i:
            out.append('<span class="divider">•</span>')
        out.append(s)
    return "\n      ".join(out)


def _load_profile_identity() -> dict:
    """Read identity defaults (name, headline, contact) from data/profile.md if found."""
    here = Path(__file__).resolve()
    # Find data/profile.md by checking workspace ancestors
    for parent in [here.parent.parent, here.parent]:
        p = parent / "data" / "profile.md"
        if p.is_file():
            try:
                content = p.read_text(encoding="utf-8")
                name_match = re.search(r"^\s*-\s*Name:\s*(.+)$", content, re.M)
                headline_match = re.search(r"^\s*-\s*Headline:\s*(.+)$", content, re.M)
                return {
                    "name": name_match.group(1).strip() if name_match else "",
                    "headline": headline_match.group(1).strip() if headline_match else "",
                }
            except Exception:
                pass
    return {"name": "", "headline": ""}


def parse_cover_letter(md_text: str, default_company: str = "", default_date: str = "") -> dict:
    profile_defaults = _load_profile_identity()
    doc = {
        "name": profile_defaults.get("name", ""),
        "headline": profile_defaults.get("headline", ""),
        "contact": [],
        "date": default_date,
        "recipient_name": "Hiring Team",
        "recipient_company": default_company,
        "salutation": "",
        "paragraphs": [],
        "closing": "Sincerely,",
        "signer": "",
    }

    raw_lines = md_text.split("\n")
    i = 0
    total = len(raw_lines)

    # 1. Parse Header
    while i < total:
        line = raw_lines[i].strip()
        i += 1
        if not line:
            continue

        if line.startswith("# "):
            header_val = line[2:].strip()
            # If '# Cover Letter — Candidate Name' or '# Candidate Name'
            m = re.match(r"^Cover Letter\s*[—–-]\s*(.*)$", header_val, re.IGNORECASE)
            if m:
                doc["name"] = m.group(1).strip()
            else:
                doc["name"] = header_val
            break

    # 2. Look for Headline or Contact line
    while i < total:
        line = raw_lines[i].strip()
        i += 1
        if not line:
            continue

        if "|" in line:
            # Contact line (email | phone | linkedin | ...)
            doc["contact"] = [p.strip() for p in line.split("|") if p.strip()]
            break
        elif not doc["headline"] and not line.startswith("#") and not line.lower().startswith("dear"):
            # Candidate headline / title under name
            doc["headline"] = line
        else:
            i -= 1
            break

    # If no headline found yet, use profile headline
    if not doc["headline"] and profile_defaults.get("headline"):
        doc["headline"] = profile_defaults["headline"]

    # 3. Parse Date, Salutation, Body Paragraphs, and Signoff
    current_para = []

    def flush_para():
        if current_para:
            text = " ".join(current_para).strip()
            if text:
                doc["paragraphs"].append(text)
            current_para.clear()

    while i < total:
        line = raw_lines[i].strip()
        i += 1
        if not line:
            flush_para()
            continue

        # Check for structural scaffolding headings: ## Opening, ## Body, ## Closing, etc.
        if line.startswith("## ") or line.startswith("### "):
            heading_text = re.sub(r"^#+\s*", "", line).strip().lower()
            flush_para()
            # If it's a known scaffolding heading, ignore it
            if heading_text in SCAFFOLD_HEADERS:
                continue
            # If it's another heading, keep as a subhead paragraph if desired
            continue

        # Check for Salutation: e.g. "Dear Hiring Team," or "Dear Hiring Manager,"
        if re.match(r"^Dear\s+.*?,?$", line, re.IGNORECASE) and not doc["salutation"]:
            flush_para()
            doc["salutation"] = line.rstrip(",") + ","
            continue

        # Check for Signoff: e.g. "Sincerely," or "Warm regards," or "Best regards,"
        signoff_match = re.match(r"^(Sincerely|Best regards|Warm regards|Regards|Respectfully),?$", line, re.IGNORECASE)
        if signoff_match:
            flush_para()
            doc["closing"] = signoff_match.group(1) + ","
            # Look ahead for signer name on subsequent non-empty line
            while i < total:
                next_line = raw_lines[i].strip()
                i += 1
                if next_line:
                    doc["signer"] = next_line
                    break
            continue

        current_para.append(line)

    flush_para()

    # Check if the last paragraph is just the candidate's name (signoff name)
    if doc["paragraphs"] and not doc["signer"]:
        last_p = doc["paragraphs"][-1].strip()
        # If last paragraph matches doc["name"] or is very short (1-3 words, no punctuation at end)
        if last_p == doc["name"] or (len(last_p.split()) <= 4 and not last_p.endswith(".")):
            doc["signer"] = last_p
            doc["paragraphs"].pop()

    if not doc["signer"]:
        doc["signer"] = doc["name"]

    # Deduce default company if not set
    if not doc["recipient_company"]:
        # Try to infer company from salutation or opening paragraph
        if doc["paragraphs"]:
            first_p = doc["paragraphs"][0]
            m = re.search(r"at\s+([A-Z][A-Za-z0-9\s&–-]+?)(?:\.|\,|\s+for|\s+where|\s+as)", first_p)
            if m:
                cand = m.group(1).strip()
                if len(cand) < 40 and not cand.lower().startswith("the "):
                    doc["recipient_company"] = cand

    # Default date if not provided
    if not doc["date"]:
        doc["date"] = datetime.now().strftime("%B %d, %Y")

    return doc


def md_to_html(md_text: str, company: str = "", date: str = "") -> str:
    d = parse_cover_letter(md_text, default_company=company, default_date=date)

    # Format body paragraphs
    body_html = []
    for p in d["paragraphs"]:
        formatted = format_inline_markdown(p)
        body_html.append(f'      <p class="letter-para">{formatted}</p>')
    body_content = "\n".join(body_html)

    contact_html = render_contact(d["contact"])
    salutation = d["salutation"] or "Dear Hiring Team,"

    recipient_html = f'<div class="recipient-name">{esc(d["recipient_name"])}</div>'
    if d["recipient_company"]:
        recipient_html += f'\n        <div class="recipient-company">{esc(d["recipient_company"])}</div>'

    headline_html = f'<div class="headline">{esc(d["headline"])}</div>' if d["headline"] else ""
    signoff_title_html = f'<div class="signoff-title">{esc(d["headline"])}</div>' if d["headline"] else ""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{esc(d['name'])} - Cover Letter</title>
  <style>{CSS}
  </style>
</head>
<body>

  <header>
    <h1>{esc(d['name'])}</h1>
    {headline_html}
    <div class="contact-links">
      {contact_html}
    </div>
  </header>

  <div class="letter-container">
    <div class="letter-meta">
      <div class="recipient-block">
        {recipient_html}
      </div>
      <div class="letter-date">{esc(d['date'])}</div>
    </div>

    <div class="salutation">{esc(salutation)}</div>

    <div class="letter-body">
{body_content}
    </div>

    <div class="signoff-block">
      <div class="signoff-closing">{esc(d['closing'])}</div>
      <div class="signoff-name">{esc(d['signer'])}</div>
      {signoff_title_html}
    </div>
  </div>

</body>
</html>
"""


def main():
    if len(sys.argv) < 3:
        print("usage: make_cover_letter_html.py <input.md> <output.html> [--company <Company>]")
        sys.exit(1)

    in_path = sys.argv[1]
    out_path = sys.argv[2]
    company = ""
    if "--company" in sys.argv:
        idx = sys.argv.index("--company")
        if idx + 1 < len(sys.argv):
            company = sys.argv[idx + 1]

    with open(in_path, "r", encoding="utf-8") as f:
        md_text = f.read()

    html_text = md_to_html(md_text, company=company)

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html_text)

    print("wrote", out_path)


if __name__ == "__main__":
    main()
