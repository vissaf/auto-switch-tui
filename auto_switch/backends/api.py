"""Direct LLM API backend: no agent CLI required.

The bundled SKILL.md becomes the system prompt; this module assembles the
evidence context (JD + profile + work-experience bullets) in Python, asks the
model for structured output (match analysis + document markdown), then runs
the deterministic build pipeline itself. Judgment in the LLM, orchestration
in code — so the pipeline is testable and provider-agnostic.

Key resolution order: the environment variable named by
``generation.api.key_env`` (default ``AUTO_SWITCH_API_KEY``), then the
machine-local ``~/.config/auto-switch/api_key`` file (written by onboarding,
chmod 600).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import httpx

from ..config import API_KEY_FILE
from ..paths import experiences_dir, profile_path
from ..util import slugify
from .base import GenerationResult, skill_text, write_generation_log

_DEFAULT_MODELS = {
    "openai": "gpt-4o-mini",
    "anthropic": "claude-sonnet-4-5",
    "google": "gemini-2.5-flash",
    "deepseek": "deepseek-chat",
}

_BASE_URLS = {
    "openai": "https://api.openai.com/v1",
    "deepseek": "https://api.deepseek.com",
    "openrouter": "https://openrouter.ai/api/v1",
}

_MAX_CONTEXT_CHARS = 60_000
_MAX_FILE_CHARS = 8_000


class APIBackend:
    name = "api"
    display_name = "Direct LLM API"

    def __init__(self) -> None:
        self._cfg: dict = {}

    def detect(self) -> bool:
        return bool(self._resolve_key({}))

    # -- key / config ------------------------------------------------------

    def _resolve_key(self, cfg: dict) -> str:
        api_cfg = cfg.get("generation", {}).get("api", {}) or {}
        key_env = api_cfg.get("key_env") or "AUTO_SWITCH_API_KEY"
        key = os.environ.get(key_env, "")
        if not key and API_KEY_FILE.exists():
            try:
                key = API_KEY_FILE.read_text(encoding="utf-8").strip()
            except Exception:
                key = ""
        return key

    def _provider(self, cfg: dict) -> str:
        return (cfg.get("generation", {}).get("api", {}) or {}).get("provider") or "openai"

    def _model(self, cfg: dict) -> str:
        api_cfg = cfg.get("generation", {}).get("api", {}) or {}
        return api_cfg.get("model") or _DEFAULT_MODELS.get(self._provider(cfg), "gpt-4o-mini")

    def _base_url(self, cfg: dict) -> str:
        api_cfg = cfg.get("generation", {}).get("api", {}) or {}
        return api_cfg.get("base_url") or _BASE_URLS.get(self._provider(cfg), _BASE_URLS["openai"])

    # -- context assembly --------------------------------------------------

    def _evidence_context(self, workspace: Path) -> str:
        parts: list[str] = []
        profile = profile_path(workspace)
        if profile.exists():
            parts.append(profile.read_text(encoding="utf-8")[:_MAX_FILE_CHARS])
        exp_dir = experiences_dir(workspace)
        if exp_dir.exists():
            for name in ("RESUME_BULLETS.md", "PORTFOLIO.md"):
                for f in sorted(exp_dir.glob(f"**/{name}")):
                    try:
                        text = f.read_text(encoding="utf-8")
                    except Exception:
                        continue
                    parts.append(f"\n--- {f.relative_to(workspace)} ---\n{text[:_MAX_FILE_CHARS]}")
        context = "\n".join(parts)
        return context[:_MAX_CONTEXT_CHARS]

    def _skill_text(self, workspace: Path, kind: str) -> str:
        return skill_text(workspace, kind)

    # -- LLM call ----------------------------------------------------------

    def _chat(self, cfg: dict, system: str, user: str) -> str:
        provider = self._provider(cfg)
        key = self._resolve_key(cfg)
        if not key:
            raise RuntimeError(
                "No API key: set AUTO_SWITCH_API_KEY or choose an agent backend "
                "(--backend opencode|claude|pi|deepseek)."
            )
        if provider == "anthropic":
            return self._call_anthropic(cfg, key, system, user)
        if provider == "google":
            return self._call_google(cfg, key, system, user)
        return self._call_openai_compatible(cfg, key, system, user)

    def _call_openai_compatible(self, cfg: dict, key: str, system: str, user: str) -> str:
        url = f"{self._base_url(cfg).rstrip('/')}/chat/completions"
        payload = {
            "model": self._model(cfg),
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "response_format": {"type": "json_object"},
        }
        resp = httpx.post(
            url,
            json=payload,
            headers={"Authorization": f"Bearer {key}"},
            timeout=180,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

    def _call_anthropic(self, cfg: dict, key: str, system: str, user: str) -> str:
        resp = httpx.post(
            "https://api.anthropic.com/v1/messages",
            json={
                "model": self._model(cfg),
                "max_tokens": 8192,
                "system": system,
                "messages": [{"role": "user", "content": user}],
            },
            headers={
                "x-api-key": key,
                "anthropic-version": "2023-06-01",
            },
            timeout=180,
        )
        resp.raise_for_status()
        return "".join(b.get("text", "") for b in resp.json().get("content", []))

    def _call_google(self, cfg: dict, key: str, system: str, user: str) -> str:
        model = self._model(cfg)
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model}:generateContent?key={key}"
        )
        resp = httpx.post(
            url,
            json={"contents": [{"parts": [{"text": f"{system}\n\n{user}"}]}]},
            timeout=180,
        )
        resp.raise_for_status()
        candidates = resp.json().get("candidates") or []
        return "".join(
            p.get("text", "") for c in candidates for p in c.get("content", {}).get("parts", [])
        )

    def _parse_json_response(self, raw: str) -> dict:
        text = raw.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines).strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end > start:
                return json.loads(text[start : end + 1])
        raise ValueError("model did not return valid JSON")

    # -- generation entry points ------------------------------------------

    def judge_verdicts(
        self, workspace: Path, candidates: list[dict], cfg: dict | None = None
    ) -> dict[str, dict]:
        """Score a batch of job candidates against the evidence in one LLM call.

        Returns ``{job_id: {"score": float, "verdict": str}}``. Raises on
        transport/model errors — callers fall back to the offline scores.
        """
        self._cfg = cfg or {}
        skill = self._skill_text(workspace, "judge")
        system = (
            f"{skill}\n\n"
            f"Workspace root: {workspace}\n"
            "Respond with a single JSON object that maps each job id to an "
            'object with exactly two fields: "score" (an integer 0-100, '
            'evidence-grounded per the skill calibration) and "verdict" '
            '(a one-line justification). No other fields, no surrounding text.'
        )
        user = (
            "Judge each candidate below against the candidate evidence. "
            "Follow the skill calibration exactly; never overclaim.\n\n"
            f"Candidates:\n\n{json.dumps(candidates, indent=2)}\n\n"
            f"Candidate evidence:\n\n{self._evidence_context(workspace)}"
        )
        raw = self._chat(self._cfg, system, user)
        payload = self._parse_json_response(raw)
        verdicts: dict[str, dict] = {}
        for job_id, entry in payload.items():
            if not isinstance(entry, dict) or "score" not in entry:
                continue
            try:
                score = float(entry["score"])
            except (TypeError, ValueError):
                continue
            verdicts[str(job_id)] = {
                "score": round(max(0.0, min(100.0, score)), 0),
                "verdict": str(entry.get("verdict") or "").strip(),
            }
        return verdicts

    def generate(
        self, workspace: Path, jd_path: Path, kind: str, message: str, cfg: dict | None = None
    ) -> GenerationResult:
        self._cfg = cfg or {}
        skill = self._skill_text(workspace, kind)
        system = (
            f"{skill}\n\n"
            f"Workspace root: {workspace}\n"
            f"Working directory for all writes: {workspace}\n"
            f"Output directory: {workspace}/output\n"
            f"Respond with a single JSON object with exactly two string fields: "
            f'"match_analysis" (markdown, the mandatory pre-writing analysis per '
            f'the skill) and "document_markdown" (the resume or letter markdown). '
            f"No other fields, no surrounding text."
        )
        jd_text = jd_path.read_text(encoding="utf-8") if jd_path.exists() else ""
        user = (
            f"{message}\n\n"
            f"Job description ({jd_path}):\n\n{jd_text[:20_000]}\n\n"
            f"Candidate evidence:\n\n{self._evidence_context(workspace)}"
        )
        try:
            raw = self._chat(self._cfg, system, user)
            payload = self._parse_json_response(raw)
        except Exception as exc:
            return GenerationResult(1, f"API generation failed: {exc}", self.name)

        analysis = str(payload.get("match_analysis") or "").strip()
        document = str(payload.get("document_markdown") or "").strip()
        if not document:
            return GenerationResult(1, "API generation failed: empty document returned", self.name)

        try:
            written = self._write_outputs(workspace, jd_path, kind, message, analysis, document)
        except Exception as exc:
            return GenerationResult(1, f"Writing outputs failed: {exc}", self.name)
        return GenerationResult(0, written, self.name)

    def _company_from(self, message: str) -> str:
        for token in message.split():
            if token.startswith("at") and len(token) > 2:
                return token[2:].strip(".,")
        return ""

    def _write_outputs(
        self, workspace: Path, jd_path: Path, kind: str, message: str,
        analysis: str, document: str,
    ) -> str:
        import re

        out = workspace / "output"
        out.mkdir(parents=True, exist_ok=True)
        company = self._company_from(message) or jd_path.stem.split("-")[0] or "job"
        company_dir = out / company
        company_dir.mkdir(parents=True, exist_ok=True)
        ma_path = company_dir / "match-analysis.md"
        section = "Resume" if kind == "resume" else "Cover Letter"
        existing = ma_path.read_text(encoding="utf-8") if ma_path.exists() else ""
        kept = re.sub(rf"^## {section}\b.*?(?=^## |\Z)", "", existing, flags=re.M | re.S).strip()
        new_ma = kept + f"\n\n## {section}\n\n{analysis}\n" if kept else f"# Match Analysis\n\n## {section}\n\n{analysis}\n"
        ma_path.write_text(new_ma, encoding="utf-8")

        if kind == "resume":
            md_path = company_dir / f"{slugify(company)}-resume.md"
            md_path.write_text(document, encoding="utf-8")
            build = workspace / "scripts" / "build_resume.py"
            proc = subprocess.run(
                [sys.executable, str(build), str(md_path)],
                cwd=str(workspace),
                capture_output=True,
                text=True,
                timeout=300,
            )
            write_generation_log(
                workspace, kind, jd_path,
                [sys.executable, str(build), str(md_path)], proc.returncode,
                (proc.stdout + "\n" + proc.stderr).strip(),
            )
            if proc.returncode != 0:
                return f"resume written to {md_path}, but PDF build failed: {proc.stderr[-500:]}"
            pages = self._pdf_pages(company_dir, "*resume*.pdf") or self._pdf_pages(company_dir)
            page_note = f" ({pages} page{'s' if pages != 1 else ''})" if pages else ""
            return (
                f"Wrote {md_path} + match analysis{page_note}.\n"
                f"Build: {(proc.stdout or proc.stderr).strip()[:300]}"
            )

        md_path = company_dir / f"{slugify(company)}-cover-letter.md"
        md_path.write_text(document, encoding="utf-8")
        build = workspace / "scripts" / "build_cover_letter.py"
        proc = subprocess.run(
            [sys.executable, str(build), str(md_path)],
            cwd=str(workspace),
            capture_output=True,
            text=True,
            timeout=300,
        )
        write_generation_log(
            workspace, kind, jd_path,
            [sys.executable, str(build), str(md_path)], proc.returncode,
            (proc.stdout + "\n" + proc.stderr).strip(),
        )
        if proc.returncode != 0:
            return f"cover letter written to {md_path}, but PDF build failed: {proc.stderr[-500:]}"
        pages = self._pdf_pages(company_dir, "*cover-letter*.pdf")
        page_note = f" ({pages} page{'s' if pages != 1 else ''})" if pages else ""
        return (
            f"Wrote {md_path} + match analysis{page_note}.\n"
            f"Build: {(proc.stdout or proc.stderr).strip()[:300]}"
        )

    @staticmethod
    def _pdf_pages(company_dir: Path, pattern: str = "*.pdf") -> int:
        pdfs = sorted(company_dir.glob(pattern))
        if not pdfs:
            return 0
        try:
            import fitz  # pymupdf, optional — used only for verification

            doc = fitz.open(pdfs[0])
            pages = len(doc)
            doc.close()
            return pages
        except Exception:
            try:
                proc = subprocess.run(
                    ["python3", "-c", f"import fitz; d=fitz.open('{pdfs[0]}'); print(len(d))"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if proc.returncode == 0 and proc.stdout.strip().isdigit():
                    return int(proc.stdout.strip())
            except Exception:
                pass
            return 0
