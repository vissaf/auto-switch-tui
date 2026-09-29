"""Generation backend protocol + templated CLI runner.

A backend turns "generate a resume / cover letter for this JD" into a concrete
invocation of either an agent CLI (adapters/) or a direct LLM API (api.py).
Every CLI adapter is a thin subclass of :class:`TemplatedCLIBackend` that only
defines the binary, how to detect it, and the command template — so new agents
are mostly config, not code.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol

from ..paths import output_dir

SKILLS_DIR = Path(__file__).resolve().parents[2] / ".agents" / "skills"

# kind -> bundled skill name (single source of truth for generation behavior).
KIND_TO_SKILL = {
    "resume": "resume-builder",
    "cover-letter": "cover-letter",
    "judge": "job-match-topup",
}

DEFAULT_TIMEOUT = 600


@dataclass
class GenerationResult:
    returncode: int
    output: str
    backend: str = ""


class Backend(Protocol):
    """Contract implemented by agent-CLI adapters and the API backend."""

    name: str
    display_name: str

    def detect(self) -> bool:
        """Whether this backend can run on this machine."""
        ...

    def generate(
        self,
        workspace: Path,
        jd_path: Path,
        kind: str,
        message: str,
        cfg: dict | None = None,
    ) -> GenerationResult:
        ...


def skill_path(workspace: Path, kind: str) -> Path:
    name = KIND_TO_SKILL.get(kind, kind)
    path = workspace / ".agents" / "skills" / name / "SKILL.md"
    if not path.exists():
        path = SKILLS_DIR / name / "SKILL.md"
    return path


def skill_text(workspace: Path, kind: str) -> str:
    path = skill_path(workspace, kind)
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _log_file(workspace: Path, kind: str, jd_path: Path) -> Path:
    logs = output_dir(workspace) / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return logs / f"generation-{kind}-{jd_path.stem}-{stamp}.log"


def write_generation_log(
    workspace: Path, kind: str, jd_path: Path, cmd: list[str], rc: int, output: str
) -> Path:
    path = _log_file(workspace, kind, jd_path)
    lines = [
        f"# generation log ({datetime.now().isoformat()})",
        f"command: {' '.join(cmd)}",
        f"returncode: {rc}",
        "",
        output or "(no output)",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


class TemplatedCLIBackend:
    """Base for agent-CLI adapters: detect + build command + run + log."""

    name = "cli"
    display_name = "CLI"
    binary = ""

    def detect(self) -> bool:
        return bool(self.binary) and shutil.which(self.binary) is not None

    def build_command(
        self,
        workspace: Path,
        jd_path: Path,
        kind: str,
        message: str,
        cfg: dict | None = None,
    ) -> list[str]:
        raise NotImplementedError

    def timeout(self, cfg: dict | None) -> int:
        return int((cfg or {}).get("generation", {}).get("timeout") or DEFAULT_TIMEOUT)

    def generate(
        self,
        workspace: Path,
        jd_path: Path,
        kind: str,
        message: str,
        cfg: dict | None = None,
    ) -> GenerationResult:
        try:
            cmd = self.build_command(workspace, jd_path, kind, message, cfg=cfg)
        except TypeError:
            cmd = self.build_command(workspace, jd_path, kind, message)
        timeout_sec = self.timeout(cfg)
        try:
            proc = subprocess.run(
                cmd,
                cwd=str(workspace),
                capture_output=True,
                text=True,
                timeout=timeout_sec,
            )
        except subprocess.TimeoutExpired:
            output = f"timed out after {timeout_sec}s"
            rc = 124
        except FileNotFoundError:
            output = f"{self.binary} not found on PATH"
            rc = 127
        else:
            output = (proc.stdout + "\n" + proc.stderr).strip()
            rc = proc.returncode
        log = write_generation_log(workspace, kind, jd_path, cmd, rc, output)
        if rc != 0:
            output += f"\n\n(log: {log})"
        return GenerationResult(rc, output, self.name)
