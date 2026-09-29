"""Normalized job model shared by every provider and the UI."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Optional


@dataclass
class Job:
    id: str
    title: str
    company: str
    location: str
    url: str
    description: str = ""
    remote: bool = False
    salary_min: Optional[float] = None
    salary_max: Optional[float] = None
    salary_currency: Optional[str] = None
    salary_text: Optional[str] = None
    salary_annual_usd: Optional[float] = None
    source: str = ""
    posted_at: Optional[str] = None

    # ranking fields (filled by ranking.match_job)
    compatibility: float = 0.0
    matched_keywords: list = field(default_factory=list)

    # optional LLM top-up fields (filled by topup.apply_judged)
    llm_score: Optional[float] = None
    llm_verdict: str = ""
    llm_level: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Job":
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in d.items() if k in known})

    @property
    def display_location(self) -> str:
        if self.remote and not self.location:
            return "Remote"
        if self.remote and self.location:
            return f"{self.location} (Remote)"
        return self.location or "—"
