"""opencode adapter: native Agent Skills discovery via .agents/skills/."""

from __future__ import annotations

from pathlib import Path

from ..base import TemplatedCLIBackend


class OpenCodeBackend(TemplatedCLIBackend):
    name = "opencode"
    display_name = "OpenCode"
    binary = "opencode"

    def build_command(
        self, workspace: Path, jd_path: Path, kind: str, message: str
    ) -> list[str]:
        # Skills are discovered natively from <workspace>/.agents/skills/.
        return [
            "opencode", "run",
            "--dir", str(workspace),
            "-f", str(jd_path),
            "--auto",
            message,
        ]
