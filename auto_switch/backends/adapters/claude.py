"""Claude Code adapter: skill text injected inline (print mode)."""

from __future__ import annotations

from pathlib import Path

from ..base import TemplatedCLIBackend, skill_path, skill_text


class ClaudeBackend(TemplatedCLIBackend):
    name = "claude"
    display_name = "Claude Code"
    binary = "claude"

    def build_command(
        self, workspace: Path, jd_path: Path, kind: str, message: str
    ) -> list[str]:
        skill = skill_text(workspace, kind)
        prompt = (
            f"Working directory: {workspace}\n"
            f"Job description file: {jd_path} (read it with your Read tool).\n\n"
            f"{message}\n\n"
            f"---\n## Skill instructions — follow exactly\n"
            f"(bundled skill: {skill_path(workspace, kind)})\n\n"
            f"{skill or '(skill file not found — follow the message above)'}"
        )
        return ["claude", "-p", "--dangerously-skip-permissions", prompt]
