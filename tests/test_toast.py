"""Comprehensive unit tests for the Toast notification system."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from textual.app import App, ComposeResult

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from auto_switch.models import Job
from auto_switch.ui.app import JobHuntApp, SavedScreen
from auto_switch.ui.detail import DetailScreen
from auto_switch.ui.toast import (
    SPINNER_FRAMES,
    ToastContainer,
    ToastItem,
    ToastManager,
    open_output_folder,
)


def _mock_jobs() -> list[Job]:
    return [
        Job(
            id="job-1",
            title="Senior Frontend Engineer",
            company="Acme Corp",
            location="Remote",
            url="https://example.com/job1",
            description="Looking for Senior Frontend Engineer.",
            remote=True,
            salary_text="$150k",
            salary_annual_usd=150000.0,
            source="remotive",
            compatibility=88.0,
            matched_keywords=["React"],
        ),
    ]


@pytest.mark.anyio
async def test_toast_manager_lifecycle():
    class TestApp(App):
        def __init__(self):
            super().__init__()
            self.toast_mgr = ToastManager(self, position="bottom-right")

        def compose(self) -> ComposeResult:
            yield ToastContainer()

    app = TestApp()
    async with app.run_test() as pilot:
        mgr = app.toast_mgr

        # 1. Show progress
        mgr.show_progress("judge", "Ranking Top Jobs", "Evaluating candidates…")
        await pilot.pause()

        toast = app.query_one(ToastItem)
        assert toast.toast_id == "judge"
        assert toast.state == "progress"
        assert "Ranking Top Jobs" in toast.title_text

        # 2. Transition to success
        mgr.succeed("judge", "Jobs Ranked Successfully", "12 new verdicts applied")
        await pilot.pause()

        assert toast.state == "success"
        assert "Jobs Ranked Successfully" in toast.title_text
        assert "-success" in toast.classes

        # 3. Transition to error
        mgr.fail("judge", "Ranking Failed", "Connection timeout")
        await pilot.pause()

        assert toast.state == "error"
        assert "Ranking Failed" in toast.title_text
        assert "-error" in toast.classes

        # 4. Dismissal
        mgr.dismiss("judge")
        await pilot.pause()
        assert len(app.query(ToastItem)) == 0


@pytest.mark.anyio
async def test_toast_item_spinner_and_ticks():
    class TestApp(App):
        def compose(self) -> ComposeResult:
            yield ToastItem(
                toast_id="test-spin",
                title="Processing",
                detail="Working hard…",
                state="progress",
            )

    app = TestApp()
    async with app.run_test() as pilot:
        item = app.query_one(ToastItem)
        assert item.state == "progress"
        assert item._spin_timer is not None

        # Pause to allow spinner interval timer ticks
        await pilot.pause(0.25)
        assert item._tick_counter > 0
        assert item._frame_idx in range(len(SPINNER_FRAMES))

        # Check progress bar is displayed
        bar = item.query_one("#toast-progress")
        assert bar.display is True


@pytest.mark.anyio
async def test_toast_item_click_and_auto_dismiss():
    clicked = []

    class TestApp(App):
        def compose(self) -> ComposeResult:
            yield ToastItem(
                toast_id="test-click",
                title="Done",
                detail="Click me",
                state="success",
                on_click_callback=lambda: clicked.append(True),
            )

    app = TestApp()
    async with app.run_test() as pilot:
        item = app.query_one(ToastItem)
        await pilot.click(item)
        await pilot.pause()

        assert clicked == [True]


@pytest.mark.anyio
async def test_toast_container_positions():
    class TestApp(App):
        def __init__(self):
            super().__init__()
            self.toast_mgr = ToastManager(self, position="bottom-right")

        def compose(self) -> ComposeResult:
            yield ToastContainer(position="bottom-right")

    app = TestApp()
    async with app.run_test() as pilot:
        container = app.query_one(ToastContainer)
        assert "-pos-bottom-right" in container.classes

        # Test changing position via manager
        for pos in ("top-right", "bottom-left", "top-left", "bottom-right"):
            app.toast_mgr.set_position(pos)
            await pilot.pause()
            assert f"-pos-{pos}" in container.classes


@pytest.mark.anyio
async def test_toast_multi_screen_sync():
    jobs = _mock_jobs()
    cfg = {"locations": ["Remote"], "workspace": "/tmp", "toast_position": "top-right"}

    app = JobHuntApp(cfg, jobs, [])
    async with app.run_test(size=(120, 30)) as pilot:
        # Show a progress toast on main screen
        app.toast_mgr.show_progress("sync-test", "Background Task", "Running across screens…")
        await pilot.pause()

        assert len(app.screen.query(ToastItem)) == 1

        # Navigate to DetailScreen
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, DetailScreen)
        assert len(app.screen.query(ToastItem)) == 1
        assert app.screen.query_one(ToastItem).toast_id == "sync-test"

        # Update toast while on DetailScreen
        app.toast_mgr.succeed("sync-test", "Task Finished", "All good")
        await pilot.pause()
        assert app.screen.query_one(ToastItem).state == "success"

        # Pop back to main table
        await pilot.press("escape")
        await pilot.pause()
        assert not isinstance(app.screen, DetailScreen)
        assert len(app.screen.query(ToastItem)) == 1
        assert app.screen.query_one(ToastItem).state == "success"

        # Navigate to SavedScreen
        await pilot.press("v")
        await pilot.pause()
        assert isinstance(app.screen, SavedScreen)
        assert len(app.screen.query(ToastItem)) == 1

        # Return to main table
        await pilot.press("escape")
        await pilot.pause()
        assert not isinstance(app.screen, SavedScreen)


@pytest.mark.anyio
async def test_background_judge_toast_integration(monkeypatch):
    jobs = _mock_jobs()
    cfg = {
        "locations": ["Remote"],
        "workspace": "/tmp",
        "matching": {"judge": {"enabled": True}},
    }

    # Simulate judge_top returning 1 new verdict
    monkeypatch.setattr(
        "auto_switch.judge.judge_top",
        lambda *args: "match judge: 1/1 new verdicts via api",
    )

    app = JobHuntApp(cfg, jobs, [])
    async with app.run_test(size=(120, 30)) as pilot:
        # Trigger background judge
        app._start_background_judge()
        await pilot.pause(0.1)

        # Confirm toast is in progress
        toast = app.query_one(ToastItem)
        assert toast.toast_id == "judge"

        # Deliver verdict
        app._on_verdicts("match judge: 1/1 new verdicts via api")
        await pilot.pause()

        assert toast.state == "success"
        assert "Jobs Ranked Successfully" in toast.title_text
        assert "1/1 new verdicts" in toast.detail_text


def test_open_output_folder(tmp_path, monkeypatch):
    # Mock subprocess.run
    called = []
    monkeypatch.setattr("subprocess.run", lambda cmd, **kwargs: called.append(cmd))
    monkeypatch.setattr("sys.platform", "darwin")

    ok = open_output_folder(tmp_path)
    assert ok is True
    assert len(called) == 1
    assert "open" in called[0]
