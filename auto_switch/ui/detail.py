"""Job detail screen + generation busy/result modals."""

from __future__ import annotations

import os
import subprocess
import sys
import webbrowser
from pathlib import Path
from typing import Optional

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import ScrollableContainer, Vertical
from textual.screen import ModalScreen, Screen
from textual.widgets import Footer, Header, Markdown, ProgressBar, Static

from .. import generate, storage
from ..models import Job
from ..util import strip_ansi, strip_html
from .toast import ToastContainer, open_output_folder
from .widgets import format_match_markup


class DetailScreen(Screen):
    """Modern two-zone job detail screen: sticky hero card + scrollable description."""

    BINDINGS = [
        Binding("escape", "back", "Back"),
        Binding("r", "resume", "Resume"),
        Binding("c", "cover_letter", "Cover Letter"),
        Binding("s", "save", "Save"),
        Binding("o", "open_url", "Open URL"),
        Binding("q", "quit", "Quit"),
    ]

    DEFAULT_CSS = """
    DetailScreen {
        background: $background;
        layers: base toast;
    }
    #detail-container {
        height: 1fr;
    }
    #detail-hero {
        height: auto;
        background: $surface;
        padding: 1 2;
        border-bottom: solid $primary;
    }
    #detail-title {
        text-style: bold;
        color: $text;
    }
    #detail-meta {
        color: $text-muted;
        margin-bottom: 1;
    }
    #detail-badges {
        margin-bottom: 1;
    }
    #detail-llm {
        background: $panel;
        border-left: thick $accent;
        padding: 0 1;
        margin-bottom: 1;
    }
    #detail-actions {
        background: $panel;
        padding: 0 1;
        color: $text-muted;
    }
    #detail-scroll {
        height: 1fr;
        padding: 1 2;
    }
    """

    def __init__(self, cfg: dict, job, keywords):
        super().__init__()
        self.cfg = cfg
        self.job = job
        self.keywords = keywords

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="detail-container"):
            with Vertical(id="detail-hero"):
                yield Static(f"[bold]{self.job.title}[/bold]", id="detail-title")
                loc = self.job.display_location
                comp = f"[bold cyan]{self.job.company or '—'}[/bold cyan]"
                src = f"[dim]via {self.job.source}[/dim]" if self.job.source else ""
                yield Static(f"{comp}  ·  {loc}  {src}", id="detail-meta")

                # Badges row
                score = format_match_markup(self.job.compatibility)
                badges = [score]
                if self.job.salary_text:
                    badges.append(f"[bold green]{self.job.salary_text}[/bold green]")
                if self.job.posted_at:
                    badges.append(f"[dim]Posted {self.job.posted_at}[/dim]")
                if self.job.url:
                    badges.append(f"[dim]{self.job.url}[/dim]")

                skills_tag = ""
                if self.job.matched_keywords:
                    tags = " ".join(f"[reverse] {sk} [/reverse]" for sk in self.job.matched_keywords[:8])
                    skills_tag = f"\n[dim]Matched Skills:[/dim] {tags}"

                yield Static("  ·  ".join(badges) + skills_tag, id="detail-badges")

                # LLM Judge verdict
                if self.job.llm_score is not None:
                    lvl = f" ({self.job.llm_level})" if self.job.llm_level else ""
                    yield Static(
                        f"[bold accent]LLM Judge: {self.job.llm_score:.0f}%{lvl}[/bold accent] — [italic]{self.job.llm_verdict}[/italic]",
                        id="detail-llm",
                    )

                # Quick action bar
                yield Static(
                    "[bold cyan]r[/] Tailor Resume   [bold cyan]c[/] Cover Letter   [bold cyan]s[/] Save/Bookmark   [bold cyan]o[/] Open in Browser   [bold cyan]Esc[/] Back",
                    id="detail-actions",
                )

            with ScrollableContainer(id="detail-scroll"):
                clean_desc = strip_html(self.job.description).strip() or "_No description provided._"
                yield Markdown(clean_desc)
        yield ToastContainer()
        yield Footer()

    def on_mount(self) -> None:
        if self.job.source == "instahyre" and len(self.job.description or "") < 400:
            self.run_worker(self._enrich_in_background, thread=True)

    def _enrich_in_background(self) -> None:
        from ..providers.instahyre import enrich_instahyre_job_sync

        if enrich_instahyre_job_sync(self.job):
            def _update_view() -> None:
                clean_desc = strip_html(self.job.description).strip() or "_No description provided._"
                try:
                    md_widget = self.query_one("#detail-scroll Markdown", Markdown)
                    md_widget.update(clean_desc)
                except Exception:
                    pass

            self.app.call_from_thread(_update_view)

    def action_back(self) -> None:
        self.app.pop_screen()

    def action_open_url(self) -> None:
        if self.job.url:
            webbrowser.open(self.job.url)
            self.app.notify(f"Opening {self.job.company} posting in browser…")
        else:
            self.app.notify("No URL available for this posting", severity="warning")

    def action_save(self) -> None:
        now = storage.toggle_save(self.job)
        self.app.notify(f"Saved — {self.job.title}" if now else f"Removed — {self.job.title}")

    def action_resume(self) -> None:
        self._launch("resume")

    def action_cover_letter(self) -> None:
        self._launch("cover letter")

    def action_quit(self) -> None:
        self.app.exit()

    def _launch(self, kind: str, jd: Optional[Path] = None) -> None:
        launch_generation(self.app, self.cfg, self.job, kind)


def launch_generation(app: App, cfg: dict, job: Job, kind: str, use_modal: bool = False) -> None:
    """Trigger resume or cover-letter generation with non-blocking toast progress."""
    workspace = cfg.get("workspace", ".")
    jd = storage.export_jd(job, workspace)
    toast_mgr = getattr(app, "toast_mgr", None)
    toast_id = f"gen-{job.id}-{kind.replace(' ', '-')}"
    title_kind = kind.title()

    backend_info = ""
    try:
        from ..backends import resolve_backend
        b = resolve_backend(cfg)
        backend_info = f"{b.display_name} ({b.name})"
    except Exception:
        pass

    if use_modal:
        def _finish_modal(res) -> None:
            app.pop_screen()
            success = (res.returncode == 0)
            title = "Generation Succeeded" if success else "Generation Failed"
            app.push_screen(ResultModal(res.output or "(no output captured)", title, success, Path(workspace)))

        def _worker_modal() -> None:
            if kind == "resume":
                res = generate.generate_resume(cfg, job, jd)
            else:
                res = generate.generate_cover_letter(cfg, job, jd)
            app.call_from_thread(_finish_modal, res)

        app.push_screen(
            BusyModal(
                title=f"Generating {title_kind}",
                job_title=job.title,
                company=job.company,
                jd_name=jd.name,
                backend_name=backend_info,
            )
        )
        app.run_worker(_worker_modal, thread=True, exclusive=True)
        return

    # Non-blocking Toast flow
    if toast_mgr is not None:
        toast_detail = f"{job.company} · {job.title}"
        if backend_info:
            toast_detail += f" via {backend_info}"
        toast_mgr.show_progress(
            toast_id=toast_id,
            title=f"Generating {title_kind}",
            detail=toast_detail,
        )
    app.notify(f"Started generating {kind} for {job.company}…")

    def _finish(res) -> None:
        success = (res.returncode == 0)
        if success:
            detail_msg = f"{job.company} — saved to output/ folder"
            if toast_mgr is not None:
                toast_mgr.succeed(
                    toast_id=toast_id,
                    title=f"{title_kind} Generated",
                    detail=detail_msg,
                    on_click=lambda: open_output_folder(Path(workspace)),
                )
            app.notify(f"{title_kind} generated for {job.company}! Check output/ folder.")
        else:
            err = res.output.strip().splitlines()[-1] if res.output else f"rc={res.returncode}"
            if toast_mgr is not None:
                toast_mgr.fail(
                    toast_id=toast_id,
                    title=f"{title_kind} Failed",
                    detail=f"{job.company} — {err[:60]}",
                )
            app.notify(f"{title_kind} generation failed ({job.company})", severity="error")

    def _worker() -> None:
        if kind == "resume":
            res = generate.generate_resume(cfg, job, jd)
        else:
            res = generate.generate_cover_letter(cfg, job, jd)
        app.call_from_thread(_finish, res)

    app.run_worker(_worker, thread=True, exclusive=True)


class BusyModal(ModalScreen):
    """Clean modal overlay with live elapsed counter and generation status."""

    DEFAULT_CSS = """
    BusyModal {
        align: center middle;
        background: rgba(0, 0, 0, 0.75);
    }
    #busy {
        width: 65;
        height: auto;
        border: round $primary;
        background: $surface;
        padding: 1 2;
    }
    #busy-title {
        text-style: bold;
        color: $primary;
        margin-bottom: 1;
    }
    #busy-target {
        color: $text;
        margin-bottom: 1;
    }
    #busy-bar {
        width: 100%;
        margin-bottom: 1;
    }
    #busy-status {
        color: $text-muted;
        text-align: center;
    }
    """

    def __init__(self, title: str, job_title: str, company: str, jd_name: str, backend_name: str = ""):
        super().__init__()
        self.title_text = title
        self.job_title = job_title
        self.company = company
        self.jd_name = jd_name
        self.backend_name = backend_name
        self._elapsed = 0
        self._timer = None

    def compose(self) -> ComposeResult:
        target_info = f"Target: [bold cyan]{self.company}[/bold cyan] — {self.job_title}\nFile: [dim]{self.jd_name}[/dim]"
        if self.backend_name:
            target_info += f"\nBackend: [green]{self.backend_name}[/green]"
        with Vertical(id="busy"):
            yield Static(f"[bold]{self.title_text}[/bold]", id="busy-title")
            yield Static(target_info, id="busy-target")
            yield ProgressBar(total=None, show_eta=False, id="busy-bar")
            yield Static("Working… (0s)", id="busy-status")

    def on_mount(self) -> None:
        self._timer = self.set_interval(1, self._tick)

    def _tick(self) -> None:
        self._elapsed += 1
        self.query_one("#busy-status", Static).update(f"Running agent backend… ({self._elapsed}s)")

    def on_unmount(self) -> None:
        if self._timer is not None:
            self._timer.stop()


class ResultModal(ModalScreen):
    """Result modal showing generation status, artifact shortcuts, and scrollable logs."""

    BINDINGS = [
        Binding("escape", "dismiss", "Close"),
        Binding("enter", "dismiss", "Close"),
        Binding("o", "open_folder", "Open Folder"),
    ]

    DEFAULT_CSS = """
    ResultModal {
        align: center middle;
        background: rgba(0, 0, 0, 0.75);
    }
    #result {
        width: 80;
        height: auto;
        max-height: 85%;
        border: round $primary;
        background: $surface;
        padding: 1 2;
    }
    #result-title {
        text-style: bold;
        margin-bottom: 1;
    }
    #result-scroll {
        height: auto;
        max-height: 20;
        background: $panel;
        border: solid $primary-muted;
        padding: 0 1;
        margin: 1 0;
    }
    #result-hints {
        color: $text-muted;
        text-align: center;
    }
    """

    def __init__(self, text: str, title: str, success: bool, workspace: Path):
        super().__init__()
        self.text = text
        self.title_text = title
        self.success = success
        self.workspace = workspace

    def compose(self) -> ComposeResult:
        with Vertical(id="result"):
            color = "green" if self.success else "red"
            icon = "✓" if self.success else "✗"
            yield Static(f"[bold {color}]{icon} {self.title_text}[/bold {color}]", id="result-title")

            with ScrollableContainer(id="result-scroll"):
                yield Static(self._body(), markup=False)

            yield Static("Press [bold cyan]o[/] to open output folder  ·  [bold cyan]Esc / Enter[/] to close", id="result-hints")

    def _body(self) -> str:
        clean = strip_ansi(self.text or "")
        if len(clean) > 20000:
            clean = clean[:20000] + "\n\n… (output truncated)"
        return clean or "(no output)"

    def action_dismiss(self) -> None:
        self.dismiss(None)

    def action_open_folder(self) -> None:
        out_dir = self.workspace / "output"
        out_dir.mkdir(parents=True, exist_ok=True)
        try:
            if sys.platform == "darwin":
                subprocess.run(["open", str(out_dir)], check=False)
            elif sys.platform.startswith("linux"):
                subprocess.run(["xdg-open", str(out_dir)], check=False)
            elif os.name == "nt":
                os.startfile(str(out_dir))  # type: ignore[attr-defined]
            self.app.notify(f"Opened {out_dir}")
        except Exception as e:
            self.app.notify(f"Could not open folder: {e}", severity="error")
