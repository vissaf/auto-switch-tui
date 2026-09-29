"""Provider base class."""

from __future__ import annotations

from abc import ABC, abstractmethod

import httpx

from ..models import Job

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
}


class Provider(ABC):
    name = "base"

    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.terms = cfg.get("search_terms") or ["frontend engineer"]
        self.companies = (cfg.get("companies") or {}).get(self.name, [])
        self.keys = cfg.get("api_keys") or {}

    @abstractmethod
    async def fetch(self, client: httpx.AsyncClient) -> list[Job]:
        raise NotImplementedError
