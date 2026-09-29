"""Antigravity CLI (agy) adapter: print mode with workspace mounting and inline skill injection."""

from __future__ import annotations

from pathlib import Path

from ..base import TemplatedCLIBackend, skill_path, skill_text


class AntigravityBackend(TemplatedCLIBackend):
    name = "antigravity"
    display_name = "Antigravity CLI"
    binary = "agy"

    def build_command(
        self,
        workspace: Path,
        jd_path: Path,
        kind: str,
        message: str,
        cfg: dict | None = None,
    ) -> list[str]:
        skill = skill_text(workspace, kind)
        prompt = (
            f"Working directory: {workspace}\n"
            f"Job description file: {jd_path} (read it first).\n\n"
            f"{message}\n\n"
            f"---\n## Skill instructions — follow exactly\n"
            f"(bundled skill: {skill_path(workspace, kind)})\n\n"
            f"{skill or '(skill file not found — follow the message above)'}"
        )
        timeout_sec = self.timeout(cfg)
        cmd = [
            "agy",
            "--add-dir",
            str(workspace),
            "--print-timeout",
            f"{timeout_sec}s",
            "--dangerously-skip-permissions",
        ]
        gen_cfg = (cfg or {}).get("generation", {})
        model = gen_cfg.get("model")
        if model:
            cmd.extend(["--model", str(model)])
        effort = gen_cfg.get("effort")
        if effort:
            cmd.extend(["--effort", str(effort)])
        cmd.extend(["--print", prompt])
        return cmd
