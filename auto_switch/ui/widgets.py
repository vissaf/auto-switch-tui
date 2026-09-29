"""Reusable Textual UI widgets for auto_switch: JobPreview and HelpScreen."""

from __future__ import annotations

from typing import Optional

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import ScrollableContainer, Vertical
from textual.screen import ModalScreen
from textual.widget import Widget
from textual.widgets import Markdown, Static

from ..models import Job
from ..util import strip_html


def format_match_markup(score: float) -> str:
    """Format compatibility score with semantic color markup."""
    pct = f"{score:.0f}%"
    if score >= 80:
        return f"[bold green]● {pct} Match[/bold green]"
    if score >= 60:
        return f"[bold yellow]● {pct} Match[/bold yellow]"
    return f"[dim]○ {pct} Match[/dim]"


class JobPreview(Widget):
    """Right-hand live preview pane for the currently selected job in the table."""

    DEFAULT_CSS = """
    JobPreview {
        height: 1fr;
        border-left: solid $primary;
        padding: 0 1;
        background: $surface;
    }
    #preview-container {
        height: 1fr;
    }
    #preview-header {
        height: auto;
        padding: 1 0 0 0;
        border-bottom: solid $primary-muted;
    }
    #preview-title {
        text-style: bold;
        color: $text;
    }
    #preview-meta {
        color: $text-muted;
        margin-bottom: 1;
    }
    #preview-badges {
        height: auto;
        margin-bottom: 1;
    }
    #preview-llm-card {
        background: $panel;
        border-left: thick $accent;
        padding: 0 1;
        margin-bottom: 1;
    }
    #preview-scroll {
        height: 1fr;
        margin-top: 1;
    }
    #preview-actions-hint {
        height: auto;
        dock: bottom;
        background: $panel;
        color: $text-muted;
        padding: 0 1;
        border-top: solid $primary-muted;
    }
    #preview-empty {
        height: 100%;
        content-align: center middle;
        color: $text-muted;
    }
    """

    def __init__(self, id: Optional[str] = None):
        super().__init__(id=id)
        self.current_job: Optional[Job] = None

    def compose(self) -> ComposeResult:
        with Vertical(id="preview-container"):
            yield Static("Select a job to view details", id="preview-empty")
            with Vertical(id="preview-content"):
                yield Static("", id="preview-title")
                yield Static("", id="preview-meta")
                yield Static("", id="preview-badges")
                yield Static("", id="preview-llm-card")
                with ScrollableContainer(id="preview-scroll"):
                    yield Markdown("", id="preview-markdown")
            yield Static(
                "[bold cyan]↵[/] Full detail  [bold cyan]r[/] Resume  [bold cyan]c[/] Cover letter  [bold cyan]o[/] Browser  [bold cyan]s[/] Save",
                id="preview-actions-hint",
            )

    def on_mount(self) -> None:
        self._update_view()

    def update_job(self, job: Optional[Job]) -> None:
        self.current_job = job
        self._update_view()

    def _update_view(self) -> None:
        if not self.is_mounted:
            return

        empty = self.query_one("#preview-empty", Static)
        content = self.query_one("#preview-content", Vertical)
        actions = self.query_one("#preview-actions-hint", Static)

        if not self.current_job:
            empty.display = True
            content.display = False
            actions.display = False
            return

        empty.display = False
        content.display = True
        actions.display = True

        j = self.current_job

        # Title
        self.query_one("#preview-title", Static).update(f"[bold]{j.title}[/bold]")

        # Metadata line
        loc = j.display_location
        comp = f"[bold cyan]{j.company or '—'}[/bold cyan]"
        src = f"[dim]via {j.source}[/dim]" if j.source else ""
        self.query_one("#preview-meta", Static).update(f"{comp} · {loc}  {src}")

        # Badges & Score
        score_text = format_match_markup(j.compatibility)
        badges = [score_text]
        if j.salary_text:
            badges.append(f"[bold green]{j.salary_text}[/bold green]")
        if j.posted_at:
            badges.append(f"[dim]Posted {j.posted_at}[/dim]")

        skills_text = ""
        if j.matched_keywords:
            skills = " ".join(f"[reverse] {sk} [/reverse]" for sk in j.matched_keywords[:6])
            skills_text = f"\n[dim]Matched:[/dim] {skills}"

        self.query_one("#preview-badges", Static).update(" · ".join(badges) + skills_text)

        # LLM Card
        llm_card = self.query_one("#preview-llm-card", Static)
        if j.llm_score is not None:
            level_tag = f" ({j.llm_level})" if j.llm_level else ""
            llm_card.display = True
            llm_card.update(
                f"[bold accent]LLM Judge: {j.llm_score:.0f}%{level_tag}[/bold accent]\n"
                f"[italic]{j.llm_verdict}[/italic]"
            )
        else:
            llm_card.display = False

        # Description
        clean_desc = strip_html(j.description).strip() or "_No description provided._"
        self.query_one("#preview-markdown", Markdown).update(clean_desc)


class HelpScreen(ModalScreen):
    """Full-screen modal showing all keyboard shortcuts organized by category."""

    BINDINGS = [
        Binding("escape", "dismiss", "Close"),
        Binding("enter", "dismiss", "Close"),
        Binding("?", "dismiss", "Close"),
        Binding("q", "dismiss", "Close"),
    ]

    DEFAULT_CSS = """
    HelpScreen {
        align: center middle;
        background: rgba(0, 0, 0, 0.7);
    }
    #help-box {
        width: 80;
        height: auto;
        max-height: 85%;
        border: round $primary;
        background: $surface;
        padding: 1 2;
    }
    #help-title {
        text-align: center;
        text-style: bold;
        color: $primary;
        margin-bottom: 1;
    }
    #help-scroll {
        height: auto;
        max-height: 24;
    }
    #help-close-hint {
        text-align: center;
        color: $text-muted;
        margin-top: 1;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="help-box"):
            yield Static("Keyboard Shortcuts & Navigation", id="help-title")
            with ScrollableContainer(id="help-scroll"):
                yield Markdown(self._content())
            yield Static("Press [bold cyan]Esc[/], [bold cyan]?[/], or [bold cyan]Enter[/] to close", id="help-close-hint")

    def _content(self) -> str:
        return """
### Navigation
| Key | Action |
| :--- | :--- |
| `j` / `↓` | Move down one row |
| `k` / `↑` | Move up one row |
| `PgDn` / `PgUp` | Page down / up |
| `Enter` | Open full job details |

---

### Search & Filtering
| Key | Action |
| :--- | :--- |
| `/` | Focus search filter bar |
| `Esc` | Unfocus search / return cursor to table |
| `Ctrl+U` | Clear search input |

---

### Sorting
| Key | Action |
| :--- | :--- |
| `m` | Sort by Compatibility / Match Score (highest first) |
| `t` | Sort by Salary (highest first) |
| `n` | Sort by Posted date (newest first) |
| `l` | Sort by Location |

---

### Actions & Generation
| Key | Action |
| :--- | :--- |
| `r` | Generate ATS tailored resume with configured backend |
| `c` | Generate tailored cover letter |
| `s` | Save / Bookmark job (toggles saved state) |
| `o` | Open job posting in default browser |

---

### Views & Layout
| Key | Action |
| :--- | :--- |
| `p` | Toggle live side-by-side preview pane |
| `v` | View saved / bookmarked jobs screen |
| `?` | Show this shortcut help guide |
| `q` | Quit application |
"""

    def action_dismiss(self) -> None:
        self.dismiss(None)
