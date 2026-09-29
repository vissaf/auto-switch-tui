"""Tests for cover letter HTML and PDF build scripts."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from make_cover_letter_html import (  # noqa: E402
    parse_cover_letter,
    md_to_html,
    format_inline_markdown,
    render_contact,
)
from build_cover_letter import _resolve_company_and_outdir  # noqa: E402


SAMPLE_MD = """# Cover Letter — Test Candidate
candidate@example.com | +1 555 123 4567 | linkedin.com/in/test-candidate | github.com/testcandidate

Dear Hiring Team,

## Opening
I am writing to express my enthusiasm for the Senior Frontend Engineer role at Acme Corp.

## Body
In my previous role, I owned the checkout pipeline and delivered **99.99% reliability**.
Visit [my portfolio](https://example.com) for details.

I also led the migration to Next.js and *Tailwind CSS*.

## Closing
I would love the opportunity to discuss how my skills align with Acme Corp.

Sincerely,
Test Candidate
"""


def test_parse_cover_letter_removes_scaffolding_headers():
    doc = parse_cover_letter(SAMPLE_MD, default_company="Acme Corp")
    assert doc["name"] == "Test Candidate"
    assert "candidate@example.com" in doc["contact"][0]
    assert doc["salutation"] == "Dear Hiring Team,"
    assert doc["closing"] == "Sincerely,"
    assert doc["signer"] == "Test Candidate"

    # Verify scaffolding headings (Opening, Body, Closing) are not in paragraphs
    joined_paras = " ".join(doc["paragraphs"])
    assert "## Opening" not in joined_paras
    assert "Opening" not in [p.strip() for p in doc["paragraphs"]]
    assert "Body" not in [p.strip() for p in doc["paragraphs"]]
    assert "Closing" not in [p.strip() for p in doc["paragraphs"]]

    # Verify actual paragraph contents are preserved
    assert "enthusiasm for the Senior Frontend Engineer role" in joined_paras
    assert "99.99% reliability" in joined_paras


def test_md_to_html_renders_clean_html():
    html_out = md_to_html(SAMPLE_MD, company="Acme Corp", date="September 8, 2026")
    assert "<!DOCTYPE html>" in html_out
    assert "Test Candidate - Cover Letter" in html_out
    assert "mailto:candidate@example.com" in html_out
    assert "https://linkedin.com/in/test-candidate" in html_out
    assert "Acme Corp" in html_out
    assert "September 8, 2026" in html_out
    assert "Dear Hiring Team," in html_out
    assert "<strong>99.99% reliability</strong>" in html_out
    assert 'href="https://example.com"' in html_out
    assert "<em>Tailwind CSS</em>" in html_out
    assert "Sincerely," in html_out

    # Confirm no scaffold headers in the generated HTML
    assert "## Opening" not in html_out
    assert "## Body" not in html_out
    assert "## Closing" not in html_out


def test_format_inline_markdown():
    text = "Built with **React** and *Next.js*, see [demo](https://demo.com)."
    formatted = format_inline_markdown(text)
    assert "<strong>React</strong>" in formatted
    assert "<em>Next.js</em>" in formatted
    assert '<a href="https://demo.com"' in formatted


def test_render_contact_links():
    parts = ["test@test.com", "linkedin.com/in/test", "+12345678"]
    rendered = render_contact(parts)
    assert 'href="mailto:test@test.com"' in rendered
    assert 'href="https://linkedin.com/in/test"' in rendered
    assert "+12345678" in rendered
    assert "divider" in rendered


def test_resolve_company_and_outdir_in_company_dir(tmp_path):
    output_dir = tmp_path / "output"
    company_dir = output_dir / "Acme-Corp"
    company_dir.mkdir(parents=True)
    md_file = company_dir / "acme-corp-cover-letter.md"
    md_file.write_text(SAMPLE_MD)

    company, out_dir, base = _resolve_company_and_outdir(str(md_file))
    assert company == "Acme-Corp"
    assert out_dir == str(company_dir)
    assert base == "acme-corp-cover-letter"


def test_resolve_company_and_outdir_in_output_root(tmp_path):
    output_dir = tmp_path / "output"
    company_dir = output_dir / "Acme-Corp"
    company_dir.mkdir(parents=True)
    md_file = output_dir / "acme-corp-cover-letter.md"
    md_file.write_text(SAMPLE_MD)

    company, out_dir, base = _resolve_company_and_outdir(str(md_file))
    assert company == "Acme-Corp"
    assert out_dir == str(company_dir)
    assert base == "acme-corp-cover-letter"
