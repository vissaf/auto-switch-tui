"""Toast notification system: non-blocking progress bars, spinners, and status alerts.

Provides configurable placement (bottom-right, top-right, bottom-left, top-left)
and non-blocking progress indication for background LLM judging and artifact generation.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Optional

from textual.app import ComposeResult
from textual.containers import Container, Vertical
from textual.events import Click
from textual.widgets import ProgressBar, Static

if TYPE_CHECKING:
    from textual.app import App

SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]


def open_output_folder(workspace: Path) -> bool:
    """Open the output folder in the OS native file explorer."""
    out_dir = Path(workspace) / "output"
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        if sys.platform == "darwin":
            subprocess.run(["open", str(out_dir)], check=False)
        elif sys.platform.startswith("linux"):
            subprocess.run(["xdg-open", str(out_dir)], check=False)
        elif os.name == "nt":
            os.startfile(str(out_dir))  # type: ignore[attr-defined]
        return True
    except Exception:
        return False


class ToastItem(Vertical):
    """An individual toast card with spinner/progress-bar, status, and timer."""

    DEFAULT_CSS = """
    ToastItem {
        width: 52;
        max-width: 90%;
        height: auto;
        background: $panel;
        border: round $primary;
        padding: 0 1;
        margin-bottom: 1;
        visibility: visible;
    }
    ToastItem.-success {
        border: round $success;
        background: $surface;
    }
    ToastItem.-error {
        border: round $error;
        background: $surface;
    }
    ToastItem.-info {
        border: round $accent;
    }
    .toast-header {
        height: 1;
        text-style: bold;
        color: $text;
    }
    .toast-detail {
        color: $text-muted;
        height: auto;
    }
    .toast-bar {
        width: 100%;
        height: 1;
        margin-top: 1;
    }
    """

    def __init__(
        self,
        toast_id: str,
        title: str,
        detail: str = "",
        state: str = "progress",
        on_click_callback: Optional[Callable[[], Any]] = None,
    ) -> None:
        super().__init__(id=f"toast-{toast_id}")
        self.toast_id = toast_id
        self.title_text = title
        self.detail_text = detail
        self.state = state
        self.on_click_callback = on_click_callback
        self.elapsed: int = 0
        self._frame_idx: int = 0
        self._tick_counter: int = 0
        self._spin_timer = None
        self._dismiss_timer = None

    def compose(self) -> ComposeResult:
        yield Static("", classes="toast-header", id="toast-title")
        yield Static(self.detail_text, classes="toast-detail", id="toast-body")
        yield ProgressBar(total=None, show_eta=False, show_percentage=False, classes="toast-bar", id="toast-progress")

    def on_mount(self) -> None:
        self._update_display()
        if self.state == "progress":
            self._spin_timer = self.set_interval(0.1, self._spin_tick)

    def _update_display(self) -> None:
        if not self.is_mounted:
            return

        title_widget = self.query_one("#toast-title", Static)
        body_widget = self.query_one("#toast-body", Static)
        bar_widget = self.query_one("#toast-progress", ProgressBar)

        if self.state == "progress":
            spin = SPINNER_FRAMES[self._frame_idx]
            title_widget.update(f"[bold accent]{spin}[/] [bold]{self.title_text}[/] [dim]({self.elapsed}s)[/]")
            bar_widget.display = True
            body_widget.update(self.detail_text)
        elif self.state == "success":
            title_widget.update(f"[bold green]✓[/] [bold green]{self.title_text}[/] [dim]({self.elapsed}s)[/]")
            bar_widget.display = False
            hint = "\n[dim italic]Click to dismiss[/dim italic]"
            body_widget.update(f"{self.detail_text}{hint}")
        elif self.state == "error":
            title_widget.update(f"[bold red]✗[/] [bold red]{self.title_text}[/] [dim]({self.elapsed}s)[/]")
            bar_widget.display = False
            hint = "\n[dim italic]Click to dismiss[/dim italic]"
            body_widget.update(f"{self.detail_text}{hint}")
        else:
            title_widget.update(f"[bold]{self.title_text}[/]")
            bar_widget.display = False
            body_widget.update(self.detail_text)

    def _spin_tick(self) -> None:
        if self.state != "progress":
            return
        self._tick_counter += 1
        self._frame_idx = (self._frame_idx + 1) % len(SPINNER_FRAMES)
        if self._tick_counter % 10 == 0:
            self.elapsed += 1
        self._update_display()

    def update_detail(self, detail: str) -> None:
        self.detail_text = detail
        if self.is_mounted:
            self.query_one("#toast-body", Static).update(detail)

    def show_progress(self, title: str = "", detail: str = "") -> None:
        self.state = "progress"
        if title:
            self.title_text = title
        if detail:
            self.detail_text = detail
        if self._dismiss_timer is not None:
            self._dismiss_timer.stop()
            self._dismiss_timer = None
        if self._spin_timer is None and self.is_mounted:
            self._spin_timer = self.set_interval(0.1, self._spin_tick)
        self.remove_class("-success")
        self.remove_class("-error")
        self._update_display()

    def succeed(
        self,
        title: str = "",
        detail: str = "",
        auto_dismiss: float = 5.0,
        on_click_callback: Optional[Callable[[], Any]] = None,
    ) -> None:
        self.state = "success"
        if title:
            self.title_text = title
        if detail:
            self.detail_text = detail
        if on_click_callback is not None:
            self.on_click_callback = on_click_callback

        if self._spin_timer is not None:
            self._spin_timer.stop()
            self._spin_timer = None

        self.remove_class("-error")
        self.add_class("-success")
        self._update_display()

        if auto_dismiss > 0:
            self._dismiss_timer = self.set_timer(auto_dismiss, self.dismiss)

    def fail(
        self,
        title: str = "",
        detail: str = "",
        auto_dismiss: float = 8.0,
    ) -> None:
        self.state = "error"
        if title:
            self.title_text = title
        if detail:
            self.detail_text = detail

        if self._spin_timer is not None:
            self._spin_timer.stop()
            self._spin_timer = None

        self.remove_class("-success")
        self.add_class("-error")
        self._update_display()

        if auto_dismiss > 0:
            self._dismiss_timer = self.set_timer(auto_dismiss, self.dismiss)

    def on_click(self, event: Click) -> None:
        event.stop()
        if self.on_click_callback is not None:
            try:
                self.on_click_callback()
            except Exception:
                pass
        if self.state in ("success", "error"):
            self.dismiss()

    def dismiss(self) -> None:
        if self._spin_timer is not None:
            self._spin_timer.stop()
            self._spin_timer = None
        if self._dismiss_timer is not None:
            self._dismiss_timer.stop()
            self._dismiss_timer = None

        parent = self.parent
        if parent is not None and hasattr(parent, "on_toast_dismissed"):
            parent.on_toast_dismissed(self.toast_id)
        self.remove()


class ToastContainer(Container):
    """Floating container that renders active toasts in the configured screen corner."""

    DEFAULT_CSS = """
    ToastContainer {
        layer: toast;
        width: 1fr;
        height: auto;
        visibility: hidden;
        layout: vertical;
    }
    ToastContainer.-pos-bottom-right {
        dock: bottom;
        align-horizontal: right;
        margin-right: 2;
        margin-bottom: 1;
    }
    ToastContainer.-pos-top-right {
        dock: top;
        align-horizontal: right;
        margin-right: 2;
        margin-top: 1;
    }
    ToastContainer.-pos-bottom-left {
        dock: bottom;
        align-horizontal: left;
        margin-left: 2;
        margin-bottom: 1;
    }
    ToastContainer.-pos-top-left {
        dock: top;
        align-horizontal: left;
        margin-left: 2;
        margin-top: 1;
    }
    """

    def __init__(self, position: str = "bottom-right", id: Optional[str] = "toast-container") -> None:
        classes = f"-pos-{position}"
        super().__init__(id=id, classes=classes)
        self.position = position

    def on_mount(self) -> None:
        toast_mgr = getattr(self.app, "toast_mgr", None)
        if toast_mgr is not None:
            self.set_position(toast_mgr.position)
            toast_mgr.register_container(self)

    def on_unmount(self) -> None:
        toast_mgr = getattr(self.app, "toast_mgr", None)
        if toast_mgr is not None:
            toast_mgr.unregister_container(self)

    def set_position(self, position: str) -> None:
        self.position = position
        for pos in ("bottom-right", "top-right", "bottom-left", "top-left"):
            self.remove_class(f"-pos-{pos}")
        self.add_class(f"-pos-{position}")

    def on_toast_dismissed(self, toast_id: str) -> None:
        toast_mgr = getattr(self.app, "toast_mgr", None)
        if toast_mgr is not None:
            toast_mgr.dismiss(toast_id, notify_containers=False)

    def sync(self, active_toasts: dict[str, dict[str, Any]]) -> None:
        """Sync mounted ToastItems with manager state."""
        existing = {item.toast_id: item for item in self.query(ToastItem)}

        # Remove stale toasts
        for tid, item in list(existing.items()):
            if tid not in active_toasts:
                item.dismiss()

        # Add or update toasts
        for tid, data in active_toasts.items():
            if tid in existing:
                item = existing[tid]
                if data["state"] == "success":
                    item.succeed(
                        title=data["title"],
                        detail=data["detail"],
                        auto_dismiss=data.get("auto_dismiss", 5.0),
                        on_click_callback=data.get("on_click"),
                    )
                elif data["state"] == "error":
                    item.fail(
                        title=data["title"],
                        detail=data["detail"],
                        auto_dismiss=data.get("auto_dismiss", 8.0),
                    )
                elif data["state"] == "progress":
                    item.show_progress(
                        title=data["title"],
                        detail=data["detail"],
                    )
            else:
                new_item = ToastItem(
                    toast_id=tid,
                    title=data["title"],
                    detail=data["detail"],
                    state=data["state"],
                    on_click_callback=data.get("on_click"),
                )
                if data["state"] == "success":
                    new_item.add_class("-success")
                elif data["state"] == "error":
                    new_item.add_class("-error")
                self.mount(new_item)


class ToastManager:
    """Application-wide manager for active toast notifications."""

    def __init__(self, app: App, position: str = "bottom-right") -> None:
        self.app = app
        self.position = position if position in ("bottom-right", "top-right", "bottom-left", "top-left") else "bottom-right"
        self._active: dict[str, dict[str, Any]] = {}
        self._containers: set[ToastContainer] = set()

    def register_container(self, container: ToastContainer) -> None:
        self._containers.add(container)
        container.set_position(self.position)
        container.sync(self._active)

    def unregister_container(self, container: ToastContainer) -> None:
        self._containers.discard(container)

    def set_position(self, position: str) -> None:
        if position in ("bottom-right", "top-right", "bottom-left", "top-left"):
            self.position = position
            for c in self._containers:
                c.set_position(position)

    def show_progress(self, toast_id: str, title: str, detail: str = "") -> None:
        """Create or update a progress toast with active spinner and elapsed counter."""
        self._active[toast_id] = {
            "title": title,
            "detail": detail,
            "state": "progress",
            "on_click": None,
        }
        self._sync()

    def succeed(
        self,
        toast_id: str,
        title: str = "",
        detail: str = "",
        auto_dismiss: float = 5.0,
        on_click: Optional[Callable[[], Any]] = None,
    ) -> None:
        """Transition toast to success state with checkmark and auto-dismiss."""
        current = self._active.get(toast_id, {})
        self._active[toast_id] = {
            "title": title or current.get("title", "Done"),
            "detail": detail or current.get("detail", ""),
            "state": "success",
            "auto_dismiss": auto_dismiss,
            "on_click": on_click,
        }
        self._sync()

    def fail(
        self,
        toast_id: str,
        title: str = "",
        detail: str = "",
        auto_dismiss: float = 8.0,
    ) -> None:
        """Transition toast to error state with failure mark and auto-dismiss."""
        current = self._active.get(toast_id, {})
        self._active[toast_id] = {
            "title": title or current.get("title", "Failed"),
            "detail": detail or current.get("detail", ""),
            "state": "error",
            "auto_dismiss": auto_dismiss,
            "on_click": None,
        }
        self._sync()

    def dismiss(self, toast_id: str, notify_containers: bool = True) -> None:
        """Dismiss and remove a toast."""
        self._active.pop(toast_id, None)
        if notify_containers:
            self._sync()

    def _sync(self) -> None:
        for c in list(self._containers):
            if c.is_mounted:
                c.sync(self._active)
