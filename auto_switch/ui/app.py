"""Main Textual application: results table, master-detail live preview, filtering, sorting, saved jobs."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from rich.text import Text
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.screen import Screen
from textual.timer import Timer
from textual.widgets import DataTable, Footer, Header, Input, Static

import webbrowser

from .. import storage
from ..models import Job
from .detail import DetailScreen, launch_generation
from .toast import ToastContainer, ToastManager
from .widgets import HelpScreen, JobPreview


class JobHuntApp(App):
    TITLE = "Auto Switch"
    CSS = """
    Screen {
        layers: base toast;
    }
    JobHuntApp {
        background: $background;
    }
    #top-ribbon {
        height: auto;
        padding: 0 1;
        background: $surface;
        border-bottom: solid $primary;
        align: left middle;
    }
    #search-box {
        width: 1fr;
        height: auto;
        align: left middle;
    }
    #search-icon {
        width: auto;
        padding: 0 1 0 0;
        color: $primary;
        text-style: bold;
    }
    #filter {
        width: 1fr;
        border: none;
        background: transparent;
        padding: 0;
        height: 1;
    }
    #filter:focus {
        border: none;
        background: $panel;
    }
    #filter-count {
        width: auto;
        padding: 0 1;
        color: $text-muted;
        text-style: bold;
    }
    #sort-chip {
        width: auto;
        background: $panel;
        color: $accent;
        padding: 0 1;
        text-style: bold;
    }
    #main-split {
        height: 1fr;
    }
    #table {
        width: 3fr;
        height: 100%;
        border: none;
    }
    #table:focus {
        border: none;
    }
    #preview {
        width: 2fr;
        height: 100%;
    }
    """

    BINDINGS = [
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
        Binding("down", "cursor_down", "Down", show=False),
        Binding("up", "cursor_up", "Up", show=False),
        Binding("pagedown", "page_down", "PgDn"),
        Binding("pageup", "page_up", "PgUp"),
        Binding("g", "cursor_top", "Top", show=False),
        Binding("G", "cursor_bottom", "Bottom", show=False),
        Binding("enter", "select_cursor", "Detail"),
        Binding("s", "save_selected", "Save"),
        Binding("/", "focus_filter", "Filter"),
        Binding("escape", "unfocus_filter", "Unfocus", show=False),
        Binding("p", "toggle_preview", "Preview"),
        Binding("m", "sort_compat", "Match"),
        Binding("t", "sort_salary", "Salary"),
        Binding("n", "sort_posted", "Newest"),
        Binding("l", "sort_location", "Location"),
        Binding("v", "view_saved", "Saved"),
        Binding("r", "resume", "Resume", show=False),
        Binding("c", "cover_letter", "Cover Letter", show=False),
        Binding("o", "open_url", "Browser", show=False),
        Binding("?", "show_help", "Help"),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self, cfg: dict, jobs, keywords, default_sort: str = "compat"):
        super().__init__()
        self.cfg = cfg
        self.keywords = keywords
        self.all_jobs = list(jobs)
        self.jobs = list(jobs)
        self.ordered: list[Job] = []
        self.sort_mode = default_sort
        self.filter_text = ""
        self.preview_enabled = True

        pos = (
            self.cfg.get("ui", {}).get("toast_position")
            or self.cfg.get("toast_position")
            or "bottom-right"
        )
        self.toast_mgr = ToastManager(self, position=pos)

        self._filter_timer: Optional[Timer] = None
        self._preview_timer: Optional[Timer] = None
        self._columns_initialized = False

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="top-ribbon"):
            with Horizontal(id="search-box"):
                yield Static("/", id="search-icon")
                yield Input(placeholder="Search title, company, location, tech… [Esc to return to list]", id="filter")
            yield Static("0/0 jobs", id="filter-count")
            yield Static("Sort: Match ▼", id="sort-chip")
        with Horizontal(id="main-split"):
            yield DataTable(id="table", zebra_stripes=True, cursor_type="row")
            yield JobPreview(id="preview")
        yield ToastContainer()
        yield Footer()

    def on_mount(self) -> None:
        self._init_table_columns()
        self._rebuild()
        self._start_background_judge()
        self.query_one(DataTable).focus()

    def on_resize(self, event) -> None:
        try:
            preview = self.query_one("#preview", JobPreview)
            if event.size.width < 100:
                preview.display = False
            else:
                preview.display = self.preview_enabled
        except Exception:
            pass

    # ---- Table Initialization & Rebuilding ----

    def _init_table_columns(self) -> None:
        table = self.query_one(DataTable)
        if not self._columns_initialized:
            table.add_column("Rank", width=5)
            table.add_column("Match", width=7)
            table.add_column("Company", width=16)
            table.add_column("Title", width=None)
            table.add_column("Location", width=16)
            table.add_column("Salary", width=12)
            table.add_column("Source", width=8)
            self._columns_initialized = True

    def _sorted(self) -> list[Job]:
        jobs = self.jobs
        if self.sort_mode == "salary":
            return sorted(
                jobs,
                key=lambda j: (j.salary_annual_usd is not None, j.salary_annual_usd or 0, j.compatibility),
                reverse=True,
            )
        if self.sort_mode == "posted":
            return sorted(jobs, key=lambda j: (j.posted_at or "", j.compatibility), reverse=True)
        if self.sort_mode == "location":
            return sorted(jobs, key=lambda j: (j.location.lower(), -j.compatibility))
        if self.sort_mode == "company":
            return sorted(jobs, key=lambda j: (j.company.lower(), -j.compatibility))
        return sorted(jobs, key=lambda j: (j.compatibility, j.salary_annual_usd or 0), reverse=True)

    def _rebuild(self) -> None:
        table = self.query_one(DataTable)
        # Clear only rows to avoid flickering column layout recalculation
        table.clear(columns=False)
        self.ordered = self._sorted()

        for i, job in enumerate(self.ordered, 1):
            # Match score styling
            pct = f"{job.compatibility:.0f}%"
            if job.compatibility >= 80:
                match_text = Text(pct, style="bold green")
            elif job.compatibility >= 60:
                match_text = Text(pct, style="bold yellow")
            else:
                match_text = Text(pct, style="dim")

            # Salary styling
            sal_text = Text(job.salary_text or "", style="green") if job.salary_text else Text("")

            # Saved indicator in company column
            is_fav = storage.is_saved(job)
            comp_name = f"★ {job.company}" if is_fav else (job.company or "—")
            comp_text = Text(comp_name, style="bold cyan" if is_fav else "")

            table.add_row(
                str(i),
                match_text,
                comp_text,
                job.title,
                job.display_location,
                sal_text,
                job.source,
                key=job.id,
            )

        # Update summary counters and indicators
        self.query_one("#filter-count", Static).update(f"{len(self.ordered)}/{len(self.all_jobs)} jobs")
        self._update_sort_chip()

        # Update sub_title
        self.sub_title = f"{len(self.ordered)} jobs · {', '.join(self.cfg.get('locations') or ['—'])}"
        age = self.cfg.get("_cache_age")
        if age is not None:
            self.sub_title += f" · cached {age:.0f}m ago"

        # Update preview for current row
        self._schedule_preview_update()

    def _update_sort_chip(self) -> None:
        labels = {
            "compat": "Match ▼",
            "salary": "Salary ▼",
            "posted": "Newest ▼",
            "location": "Location ▼",
            "company": "Company ▼",
        }
        name = labels.get(self.sort_mode, self.sort_mode.capitalize())
        self.query_one("#sort-chip", Static).update(f"Sort: {name}")

    def _current_job(self) -> Optional[Job]:
        table = self.query_one(DataTable)
        if table.row_count == 0:
            return None
        idx = table.cursor_row
        if 0 <= idx < len(self.ordered):
            return self.ordered[idx]
        return None

    # ---- Live Preview Debouncing ----

    def _schedule_preview_update(self) -> None:
        if not self.preview_enabled:
            return
        if self._preview_timer is not None:
            self._preview_timer.stop()
        self._preview_timer = self.set_timer(0.04, self._do_preview_update)

    def _do_preview_update(self) -> None:
        try:
            preview = self.query_one("#preview", JobPreview)
            if preview.display:
                preview.update_job(self._current_job())
        except Exception:
            pass

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        self._schedule_preview_update()

    # ---- Filter Handling with Debouncing ----

    def on_input_changed(self, event: Input.Changed) -> None:
        if self._filter_timer is not None:
            self._filter_timer.stop()
        self._filter_timer = self.set_timer(0.12, self._apply_filter)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self._apply_filter()
        self.query_one(DataTable).focus()

    def _apply_filter(self) -> None:
        inp = self.query_one("#filter", Input)
        self.filter_text = inp.value.lower().strip()
        if not self.filter_text:
            self.jobs = list(self.all_jobs)
        else:
            ft = self.filter_text
            self.jobs = [
                j for j in self.all_jobs
                if ft in j.title.lower()
                or ft in j.company.lower()
                or ft in j.location.lower()
                or ft in j.source.lower()
                or any(ft in sk.lower() for sk in getattr(j, "matched_keywords", []))
            ]
        self._rebuild()

    # ---- Background LLM Judging (Textual Worker) ----

    def _judge_enabled(self) -> bool:
        matching = self.cfg.get("matching", {}) or {}
        judge_cfg = matching.get("judge", {}) or {}
        return bool(judge_cfg.get("enabled")) and bool(self.cfg.get("workspace"))

    def _start_background_judge(self) -> None:
        if not self._judge_enabled():
            return
        self.toast_mgr.show_progress(
            toast_id="judge",
            title="Ranking Top Jobs",
            detail="Evaluating candidates via LLM judge…",
        )
        self._run_judge_worker()

    @work(thread=True, exclusive=True, name="judge-worker")
    def _run_judge_worker(self) -> None:
        from ..judge import judge_top

        workspace = Path(self.cfg["workspace"])
        try:
            status = judge_top(list(self.all_jobs), self.cfg, workspace)
        except Exception as exc:  # noqa: BLE001
            status = f"match judge failed ({exc}); keeping offline scores"

        if status:
            self.call_from_thread(self._on_verdicts, status)

    def _on_verdicts(self, status: str) -> None:
        self._rebuild()
        if "failed" in status.lower():
            self.toast_mgr.fail(
                toast_id="judge",
                title="Ranking Failed",
                detail=status,
            )
        else:
            self.toast_mgr.succeed(
                toast_id="judge",
                title="Jobs Ranked Successfully",
                detail=status,
            )
        self.notify(status)

    # ---- Action Handlers ----

    def action_select_cursor(self) -> None:
        self._open_current()

    def action_cursor_down(self) -> None:
        self.query_one(DataTable).action_cursor_down()

    def action_cursor_up(self) -> None:
        self.query_one(DataTable).action_cursor_up()

    def action_page_down(self) -> None:
        self.query_one(DataTable).action_page_down()

    def action_page_up(self) -> None:
        self.query_one(DataTable).action_page_up()

    def action_cursor_top(self) -> None:
        table = self.query_one(DataTable)
        if table.row_count > 0:
            table.move_cursor(row=0)

    def action_cursor_bottom(self) -> None:
        table = self.query_one(DataTable)
        if table.row_count > 0:
            table.move_cursor(row=table.row_count - 1)

    def on_data_table_row_selected(self, event) -> None:
        self._open_current()

    def _open_current(self) -> None:
        job = self._current_job()
        if job:
            self.push_screen(DetailScreen(self.cfg, job, self.keywords))

    def action_save_selected(self) -> None:
        job = self._current_job()
        if not job:
            return
        now = storage.toggle_save(job)
        self._rebuild()
        self.notify(f"Saved — {job.title}" if now else f"Removed — {job.title}")

    def action_focus_filter(self) -> None:
        self.query_one("#filter", Input).focus()

    def action_unfocus_filter(self) -> None:
        self.query_one(DataTable).focus()

    def action_toggle_preview(self) -> None:
        self.preview_enabled = not self.preview_enabled
        preview = self.query_one("#preview", JobPreview)
        preview.display = self.preview_enabled
        table = self.query_one("#table", DataTable)
        table.styles.width = "3fr" if self.preview_enabled else "1fr"
        if self.preview_enabled:
            self._schedule_preview_update()
        self.notify("Preview enabled" if self.preview_enabled else "Preview hidden")

    def action_sort_compat(self) -> None:
        self.sort_mode = "compat"
        self._rebuild()
        self.notify("Sorted by match score")

    def action_sort_salary(self) -> None:
        self.sort_mode = "salary"
        self._rebuild()
        self.notify("Sorted by salary")

    def action_sort_posted(self) -> None:
        self.sort_mode = "posted"
        self._rebuild()
        self.notify("Sorted by newest")

    def action_sort_location(self) -> None:
        self.sort_mode = "location"
        self._rebuild()
        self.notify("Sorted by location")

    def action_view_saved(self) -> None:
        self.push_screen(SavedScreen(self.cfg, self.keywords))

    def action_open_url(self) -> None:
        job = self._current_job()
        if not job:
            return
        if job.url:
            webbrowser.open(job.url)
            self.notify(f"Opening {job.company} posting in browser…")
        else:
            self.notify("No URL available for this posting", severity="warning")

    def action_resume(self) -> None:
        job = self._current_job()
        if not job:
            return
        launch_generation(self, self.cfg, job, "resume")

    def action_cover_letter(self) -> None:
        job = self._current_job()
        if not job:
            return
        launch_generation(self, self.cfg, job, "cover letter")

    def action_show_help(self) -> None:
        self.push_screen(HelpScreen())


class SavedScreen(Screen):
    """Saved / bookmarked jobs screen with preview and direct action keys."""

    BINDINGS = [
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
        Binding("down", "cursor_down", "Down", show=False),
        Binding("up", "cursor_up", "Up", show=False),
        Binding("d", "delete", "Remove"),
        Binding("s", "delete", "Remove", show=False),
        Binding("enter", "select_cursor", "Detail"),
        Binding("p", "toggle_preview", "Preview"),
        Binding("r", "resume", "Resume", show=False),
        Binding("c", "cover_letter", "Cover Letter", show=False),
        Binding("o", "open_url", "Browser", show=False),
        Binding("escape", "back", "Back"),
        Binding("?", "show_help", "Help"),
        Binding("q", "quit", "Quit"),
    ]

    DEFAULT_CSS = """
    SavedScreen {
        background: $background;
        layers: base toast;
    }
    #saved-ribbon {
        height: auto;
        padding: 0 1;
        background: $surface;
        border-bottom: solid $primary;
    }
    #saved-split {
        height: 1fr;
    }
    #saved-table {
        width: 3fr;
        height: 100%;
        border: none;
    }
    #saved-preview {
        width: 2fr;
        height: 100%;
    }
    """

    def __init__(self, cfg: dict, keywords):
        super().__init__()
        self.cfg = cfg
        self.keywords = keywords
        self.jobs: list[Job] = []
        self.preview_enabled = True
        self._columns_initialized = False

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="saved-ribbon"):
            yield Static("★ Bookmarked & Saved Jobs", id="saved-title")
        with Horizontal(id="saved-split"):
            yield DataTable(id="saved-table", zebra_stripes=True, cursor_type="row")
            yield JobPreview(id="saved-preview")
        yield ToastContainer()
        yield Footer()

    def on_mount(self) -> None:
        self._init_columns()
        self._rebuild()
        self.query_one("#saved-table", DataTable).focus()

    def _init_columns(self) -> None:
        if not self._columns_initialized:
            table = self.query_one("#saved-table", DataTable)
            table.add_column("Company", width=16)
            table.add_column("Title", width=None)
            table.add_column("Location", width=16)
            table.add_column("Match", width=7)
            table.add_column("Salary", width=12)
            table.add_column("Source", width=8)
            self._columns_initialized = True

    def _rebuild(self) -> None:
        self.jobs = storage.load_saved()
        table = self.query_one("#saved-table", DataTable)
        table.clear(columns=False)

        for j in self.jobs:
            pct = f"{j.compatibility:.0f}%"
            match_text = Text(pct, style="bold green" if j.compatibility >= 80 else "bold yellow" if j.compatibility >= 60 else "dim")
            sal_text = Text(j.salary_text or "", style="green") if j.salary_text else Text("")
            table.add_row(
                Text(j.company or "—", style="bold cyan"),
                j.title,
                j.display_location,
                match_text,
                sal_text,
                j.source,
                key=j.id,
            )

        self._update_preview()

    def _current_job(self) -> Optional[Job]:
        table = self.query_one("#saved-table", DataTable)
        if table.row_count == 0:
            return None
        idx = table.cursor_row
        if 0 <= idx < len(self.jobs):
            return self.jobs[idx]
        return None

    def _update_preview(self) -> None:
        try:
            preview = self.query_one("#saved-preview", JobPreview)
            if preview.display:
                preview.update_job(self._current_job())
        except Exception:
            pass

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        self._update_preview()

    def action_back(self) -> None:
        self.app.pop_screen()

    def action_select_cursor(self) -> None:
        self._open()

    def action_cursor_down(self) -> None:
        self.query_one("#saved-table", DataTable).action_cursor_down()

    def action_cursor_up(self) -> None:
        self.query_one("#saved-table", DataTable).action_cursor_up()

    def on_data_table_row_selected(self, event) -> None:
        self._open()

    def _open(self) -> None:
        job = self._current_job()
        if job:
            self.app.push_screen(DetailScreen(self.cfg, job, self.keywords))

    def action_delete(self) -> None:
        job = self._current_job()
        if not job:
            return
        storage.toggle_save(job)
        self.notify(f"Removed — {job.title}")
        self._rebuild()

    def action_toggle_preview(self) -> None:
        self.preview_enabled = not self.preview_enabled
        preview = self.query_one("#saved-preview", JobPreview)
        preview.display = self.preview_enabled
        table = self.query_one("#saved-table", DataTable)
        table.styles.width = "3fr" if self.preview_enabled else "1fr"
        if self.preview_enabled:
            self._update_preview()

    def action_open_url(self) -> None:
        job = self._current_job()
        if not job:
            return
        if job.url:
            webbrowser.open(job.url)
            self.notify(f"Opening {job.company} posting in browser…")
        else:
            self.notify("No URL available for this posting", severity="warning")

    def action_resume(self) -> None:
        job = self._current_job()
        if not job:
            return
        launch_generation(self.app, self.cfg, job, "resume")

    def action_cover_letter(self) -> None:
        job = self._current_job()
        if not job:
            return
        launch_generation(self.app, self.cfg, job, "cover letter")

    def action_show_help(self) -> None:
        self.push_screen(HelpScreen())

    def action_quit(self) -> None:
        self.app.exit()
