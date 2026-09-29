"""Shared helpers: HTML stripping, slugify, salary parsing, relevance checks."""

from __future__ import annotations

import html as _html
import re
from typing import Optional

from bs4 import BeautifulSoup

# ANSI escape sequences (CSI + OSC) — used to clean subprocess output.
_ANSI_CSI = re.compile(r"\x1b\[[0-9;:?]*[ -/]*[@-~]")
_ANSI_OSC = re.compile(r"\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)")


def strip_ansi(text: str) -> str:
    if not text:
        return ""
    return _ANSI_OSC.sub("", _ANSI_CSI.sub("", text))


# Rough annual USD conversion factors (used ONLY for sorting; always labelled
# as estimates in the UI). Refreshed periodically.
CURRENCY_RATE = {
    "USD": 1.0,
    "INR": 1 / 83.0,
    "AED": 1 / 3.67,
    "SAR": 1 / 3.75,
    "QAR": 1 / 3.64,
    "KWD": 3.26,
    "BHD": 2.65,
    "OMR": 2.60,
    "GBP": 1.27,
    "EUR": 1.09,
    "CAD": 0.73,
    "AUD": 0.66,
    "SGD": 0.74,
}

FRONTEND_TITLE_RE = re.compile(
    r"front[- ]?end|frontend|react|javascript|typescript|angular|next\.?js|"
    r"web (developer|engineer)|ui (developer|engineer)|full[- ]?stack|software engineer",
    re.IGNORECASE,
)

SYMBOL_CURRENCY = {
    "$": "USD", "US$": "USD", "USD": "USD",
    "₹": "INR", "Rs": "INR", "INR": "INR",
    "AED": "AED", "د.إ": "AED",
    "SAR": "SAR", "SR": "SAR",
    "QAR": "QAR", "QR": "QAR",
    "KWD": "KWD", "KD": "KWD",
    "BHD": "BHD",
    "OMR": "OMR",
    "£": "GBP", "GBP": "GBP",
    "€": "EUR", "EUR": "EUR",
    "C$": "CAD", "CAD": "CAD",
    "A$": "AUD", "AUD": "AUD",
    "S$": "SGD", "SGD": "SGD",
}


def strip_html(html: str) -> str:
    if not html:
        return ""
    # Some boards (Greenhouse) return HTML-escaped markup in the content field.
    html = _html.unescape(html)
    return BeautifulSoup(html, "lxml").get_text(" ", strip=True)


def slugify(text: str) -> str:
    text = re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-").lower()
    return text[:80] or "job"


def is_relevant_title(title: str) -> bool:
    return bool(FRONTEND_TITLE_RE.search(title or ""))


def _detect_currency(text: str) -> str:
    t = text.replace("\u00a0", " ")
    for sym, code in SYMBOL_CURRENCY.items():
        if sym in t:
            return code
    # check words like "USD", "AED" already handled above; fallback
    return "USD"


def _detect_period(text: str) -> str:
    t = text.lower()
    if re.search(r"/\s*month|per month|/month|p\.m\.|\bmonthly\b|/mo\b", t):
        return "month"
    if re.search(r"/\s*hour|per hour|/hr\b|\bhourly\b", t):
        return "hour"
    if re.search(r"/\s*day|per day|\bdaily\b", t):
        return "day"
    return "year"


def parse_salary(text: str) -> Optional[dict]:
    """Best-effort salary extraction -> {currency, min, max, annual_usd, text}.

    Returns None when no numbers are found. `annual_usd` is a rough estimate
    used only for sorting; the original string is always shown to the user.
    Intended for short salary strings (not free-form job descriptions).
    """
    if not text:
        return None
    t = text.replace("\u00a0", " ")
    low = t.lower()

    currency = _detect_currency(t)
    period = _detect_period(t)

    amounts = []
    for m in re.finditer(r"(\d[\d,]*(?:\.\d+)?)\s*([kKmM])?", t):
        num = float(m.group(1).replace(",", ""))
        suffix = (m.group(2) or "").lower()
        if suffix == "k":
            num *= 1000
        elif suffix == "m":
            num *= 1_000_000
        if "lakh" in low or "lpa" in low:
            num *= 100_000
        elif "crore" in low:
            num *= 10_000_000
        amounts.append(num)

    if not amounts:
        return None

    lo, hi = min(amounts), max(amounts)
    if period == "month":
        lo, hi = lo * 12, hi * 12
    elif period == "hour":
        lo, hi = lo * 2080, hi * 2080
    elif period == "day":
        lo, hi = lo * 260, hi * 260

    rate = CURRENCY_RATE.get(currency, 1.0)
    annual_usd = hi * rate

    return {
        "currency": currency,
        "min": round(lo, 0),
        "max": round(hi, 0),
        "annual_usd": round(annual_usd, 0),
        "text": text.strip(),
    }
