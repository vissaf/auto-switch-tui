"""Pi adapter (pi.dev): print mode + explicit skill loading + project trust."""

from __future__ import annotations

from pathlib import Path

from ..base import TemplatedCLIBackend, skill_path


class PiBackend(TemplatedCLIBackend):
    name = "pi"
    display_name = "Pi"
    binary = "pi"

    def build_command(
        self, workspace: Path, jd_path: Path, kind: str, message: str
    ) -> list[str]:
        # -a/--approve: trust project-local files (skills) in headless mode.
        # --skill: load the bundled SKILL.md explicitly (repeatable).
        # @<file>: attach the JD as a file argument.
        return [
            "pi",
            "-a",
            "-p",
            "--skill", str(skill_path(workspace, kind)),
            f"@{jd_path}",
            message,
        ]
