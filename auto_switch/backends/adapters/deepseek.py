"""DeepSeek Harness (dsh) adapter: headless profile, skill injected inline.

`dsh --profile headless "<job>"` runs one fresh session, prints the final
answer, and exits — with the invoking directory as the workspace root. dsh is
in developer preview and its CLI is still stabilizing, so this adapter keeps
the invocation minimal and documents the assumptions.
"""

from __future__ import annotations

from pathlib import Path

from ..base import TemplatedCLIBackend, skill_path, skill_text


class DeepSeekBackend(TemplatedCLIBackend):
    name = "deepseek"
    display_name = "DeepSeek Harness"
    binary = "dsh"

    def build_command(
        self, workspace: Path, jd_path: Path, kind: str, message: str
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
        return ["dsh", "--profile", "headless", prompt]
