#!/usr/bin/env python3
"""Render a single-column, ATS-friendly Markdown resume to PDF.

Zero formatting dependencies — uses PyMuPDF (fitz) only. Deliberately plain:
one column, standard Helvetica, no tables, no graphics, no columns, no
headers/footers with data that a parser could choke on. Everything is real
selectable text (the most ATS-safe kind of PDF).

Usage:
    python3 scripts/make_resume_pdf.py <input.md> [output.pdf]
"""

import re
import sys

import fitz

FONT = "helv"
FONT_BOLD = "hebo"
PAGE = "letter"  # 612 x 792 pt
MARGIN_L = 54.0
MARGIN_R = 54.0
MARGIN_T = 46.0
MARGIN_B = 46.0

SIZES = {
    "h1": 16.0,
    "h2": 11.5,
    "h3": 10.5,
    "body": 10.0,
}
LINE_GAP = 1.35
BULLET_INDENT = 14.0


def text_width(text, font, size):
    return fitz.get_text_length(text, fontname=font, fontsize=size)


def split_inline(text, base_font):
    """Split markdown inline text into (segment, font) runs, handling **bold**."""
    runs = []
    for part in re.split(r"(\*\*[^*]+\*\*)", text):
        if not part:
            continue
        if part.startswith("**") and part.endswith("**"):
            runs.append((part[2:-2], FONT_BOLD))
        else:
            runs.append((part, base_font))
    return runs


def tokenize(text, base_font):
    """Return list of (word, font) tokens. Whitespace is collapsed and re-added
    as a single space between words at render time, so bold boundaries can
    never swallow an inter-word space."""
    tokens = []
    for seg, font in split_inline(text, base_font):
        for word in re.findall(r"\S+", seg):
            tokens.append((word, font))
    return tokens


def wrap_tokens(tokens, size, max_w):
    space_w = text_width(" ", FONT, size)
    lines = []
    cur = []
    cur_w = 0.0
    for word, font in tokens:
        w = text_width(word, font, size)
        add = w if not cur else space_w + w
        if cur and cur_w + add > max_w:
            lines.append(cur)
            cur = [(word, font)]
            cur_w = w
        else:
            cur.append((word, font))
            cur_w += add
    if cur:
        lines.append(cur)
    return lines


class Writer:
    def __init__(self):
        self.doc = fitz.open()
        self.width, self.height = fitz.paper_size(PAGE)
        self.content_w = self.width - MARGIN_L - MARGIN_R
        self.new_page()

    def new_page(self):
        self.page = self.doc.new_page(width=self.width, height=self.height)
        self.y = MARGIN_T

    def ensure(self, needed):
        if self.y + needed > self.height - MARGIN_B:
            self.new_page()

    def blank(self, pts):
        self.ensure(pts)
        self.y += pts

    def rule(self):
        self.ensure(8)
        self.y += 2
        self.page.draw_line(
            fitz.Point(MARGIN_L, self.y),
            fitz.Point(self.width - MARGIN_R, self.y),
            color=(0.6, 0.6, 0.6),
            width=0.5,
        )
        self.y += 6

    def render_line(self, line, size, indent):
        self.ensure(size * LINE_GAP)
        x = MARGIN_L + indent
        space_w = text_width(" ", FONT, size)
        for j, (word, font) in enumerate(line):
            if j > 0:
                x += space_w
            self.page.insert_text(
                fitz.Point(x, self.y), word, fontname=font, fontsize=size
            )
            x += text_width(word, font, size)
        self.y += size * LINE_GAP

    def write_wrapped(self, tokens, size, indent=0.0):
        if not tokens:
            return
        for line in wrap_tokens(tokens, size, self.content_w - indent):
            self.render_line(line, size, indent)

    def bullet(self, text, size):
        tokens = tokenize(text, FONT)
        if not tokens:
            return
        lines = wrap_tokens(tokens, size, self.content_w - BULLET_INDENT)
        for i, line in enumerate(lines):
            self.ensure(size * LINE_GAP)
            if i == 0:
                self.page.insert_text(
                    fitz.Point(MARGIN_L, self.y), "\u2022 ", fontname=FONT, fontsize=size
                )
            self.render_line(line, size, BULLET_INDENT)

    def heading(self, text, level):
        size = SIZES.get(level, SIZES["body"])
        self.blank(size * (0.9 if level == "h1" else 1.4))
        self.write_wrapped(tokenize(text, FONT_BOLD), size)
        self.blank(2)

    def paragraph(self, text, size=None):
        size = size or SIZES["body"]
        self.write_wrapped(tokenize(text, FONT), size)

    def render(self, md_path, out_path):
        with open(md_path, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()

        for line in lines:
            stripped = line.strip()
            if not stripped:
                self.blank(3)
                continue
            if stripped == "---":
                self.rule()
                continue
            if stripped.startswith("### "):
                self.heading(stripped[4:], "h3")
            elif stripped.startswith("## "):
                self.heading(stripped[3:], "h2")
            elif stripped.startswith("# "):
                self.heading(stripped[2:], "h1")
            elif stripped.startswith(("- ", "* ")) or stripped.startswith("\u2022 "):
                self.bullet(stripped[2:], SIZES["body"])
            else:
                self.paragraph(stripped)

        self.doc.save(out_path, garbage=4, deflate=True)
        self.doc.close()


def main():
    if len(sys.argv) < 2:
        print("usage: make_resume_pdf.py <input.md> [output.pdf]")
        sys.exit(1)
    md_path = sys.argv[1]
    out_path = sys.argv[2] if len(sys.argv) > 2 else md_path.rsplit(".", 1)[0] + ".pdf"
    Writer().render(md_path, out_path)
    print("wrote", out_path)


if __name__ == "__main__":
    main()
