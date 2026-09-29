"""Tests for Textual UI components, layout, filtering, sorting, and modals."""

from __future__ import annotations

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from auto_switch.models import Job
from auto_switch.ui.app import JobHuntApp, SavedScreen
from auto_switch.ui.detail import DetailScreen
from auto_switch.ui.widgets import JobPreview, HelpScreen


def _mock_jobs() -> list[Job]:
    return [
        Job(
            id="job-1",
            title="Senior Frontend Engineer",
            company="Acme Corp",
            location="Remote",
            url="https://example.com/job1",
            description="We are looking for a Senior Frontend Engineer with React and TypeScript experience.",
            remote=True,
            salary_text="$150k - $180k",
            salary_annual_usd=165000.0,
            source="remotive",
            compatibility=88.0,
            matched_keywords=["React", "TypeScript"],
            llm_score=85.0,
            llm_verdict="Strong match for core frontend stack",
            llm_level="Senior",
        ),
        Job(
            id="job-2",
            title="Python Backend Developer",
            company="Beta LLC",
            location="New York, NY",
            url="https://example.com/job2",
            description="Backend developer needed with FastAPI and PostgreSQL skills.",
            remote=False,
            salary_text="$140k",
            salary_annual_usd=140000.0,
            source="indeed",
            compatibility=55.0,
            matched_keywords=["Python"],
        ),
    ]


@pytest.mark.anyio
async def test_job_hunt_app_mount_and_preview_toggle():
    cfg = {"locations": ["Remote"]}
    jobs = _mock_jobs()
    keywords = []

    app = JobHuntApp(cfg, jobs, keywords)
    async with app.run_test(size=(120, 30)) as pilot:
        assert app.title == "Auto Switch"
        # Table should be mounted with 2 rows
        table = app.query_one("#table")
        assert table.row_count == 2

        # Preview widget should be present and visible on wide screen
        preview = app.query_one("#preview", JobPreview)
        assert preview.display is True

        # Test toggle preview binding 'p'
        await pilot.press("p")
        await pilot.pause()
        assert preview.display is False

        # Toggle back
        await pilot.press("p")
        await pilot.pause()
        assert preview.display is True


@pytest.mark.anyio
async def test_job_hunt_app_sorting_and_chips():
    cfg = {"locations": ["Remote"]}
    jobs = _mock_jobs()
    keywords = []

    app = JobHuntApp(cfg, jobs, keywords)
    async with app.run_test(size=(120, 30)) as pilot:
        # Initial sort is compat (Match ▼)
        chip = app.query_one("#sort-chip")
        assert "Match" in chip.content

        # Press 't' for salary sort
        await pilot.press("t")
        await pilot.pause()
        assert "Salary" in chip.content
        assert app.sort_mode == "salary"

        # Press 'm' for match sort
        await pilot.press("m")
        await pilot.pause()
        assert "Match" in chip.content
        assert app.sort_mode == "compat"


@pytest.mark.anyio
async def test_job_hunt_app_filtering():
    cfg = {"locations": ["Remote"]}
    jobs = _mock_jobs()
    keywords = []

    app = JobHuntApp(cfg, jobs, keywords)
    async with app.run_test(size=(120, 30)) as pilot:
        table = app.query_one("#table")
        assert table.row_count == 2

        # Focus filter input with '/'
        await pilot.press("/")
        await pilot.pause()

        # Type 'acme'
        inp = app.query_one("#filter")
        inp.value = "acme"
        # Trigger input changed & wait for debounce
        app._apply_filter()
        await pilot.pause()

        assert len(app.ordered) == 1
        assert app.ordered[0].company == "Acme Corp"
        count_chip = app.query_one("#filter-count")
        assert "1/2" in count_chip.content


@pytest.mark.anyio
async def test_help_screen_modal():
    cfg = {"locations": ["Remote"]}
    jobs = _mock_jobs()
    keywords = []

    app = JobHuntApp(cfg, jobs, keywords)
    async with app.run_test(size=(120, 30)) as pilot:
        # Press '?' to open help modal
        await pilot.press("?")
        await pilot.pause()

        assert isinstance(app.screen, HelpScreen)

        # Press Escape to dismiss
        await pilot.press("escape")
        await pilot.pause()

        assert not isinstance(app.screen, HelpScreen)


@pytest.mark.anyio
async def test_detail_screen_renders_and_pops():
    cfg = {"locations": ["Remote"], "workspace": "/tmp"}
    jobs = _mock_jobs()
    keywords = []

    app = JobHuntApp(cfg, jobs, keywords)
    async with app.run_test(size=(120, 30)) as pilot:
        # Press enter to open detail screen
        await pilot.press("enter")
        await pilot.pause()

        assert isinstance(app.screen, DetailScreen)
        title = app.screen.query_one("#detail-title")
        assert "Senior Frontend Engineer" in title.content

        # Press escape to return to main table
        await pilot.press("escape")
        await pilot.pause()

        assert not isinstance(app.screen, DetailScreen)


@pytest.mark.anyio
async def test_saved_screen():
    cfg = {"locations": ["Remote"], "workspace": "/tmp"}
    jobs = _mock_jobs()
    keywords = []

    app = JobHuntApp(cfg, jobs, keywords)
    async with app.run_test(size=(120, 30)) as pilot:
        # Press 'v' to navigate to SavedScreen
        await pilot.press("v")
        await pilot.pause()

        assert isinstance(app.screen, SavedScreen)

        # Press escape to go back
        await pilot.press("escape")
        await pilot.pause()

        assert not isinstance(app.screen, SavedScreen)


@pytest.mark.anyio
async def test_job_preview_widget():
    from textual.app import App

    class TestApp(App):
        def compose(self):
            yield JobPreview(id="preview")

    app = TestApp()
    async with app.run_test():
        preview = app.query_one("#preview", JobPreview)
        jobs = _mock_jobs()
        preview.update_job(jobs[0])

        assert preview.current_job == jobs[0]
        assert preview.current_job.title == "Senior Frontend Engineer"

        # Test clearing
        preview.update_job(None)
        assert preview.current_job is None


@pytest.mark.anyio
async def test_responsive_preview_collapse():
    cfg = {"locations": ["Remote"]}
    jobs = _mock_jobs()
    keywords = []

    app = JobHuntApp(cfg, jobs, keywords)
    async with app.run_test(size=(80, 24)) as pilot:
        from textual.geometry import Size
        from textual.events import Resize
        app.on_resize(Resize(Size(80, 24), Size(80, 24)))
        await pilot.pause()

        preview = app.query_one("#preview", JobPreview)
        assert preview.display is False


@pytest.mark.anyio
async def test_job_hunt_app_preview_commands(monkeypatch):
    cfg = {"locations": ["Remote"], "workspace": "/tmp"}
    jobs = _mock_jobs()
    keywords = []

    opened_urls = []
    monkeypatch.setattr("webbrowser.open", lambda url: opened_urls.append(url))

    launched = []
    monkeypatch.setattr(
        "auto_switch.ui.app.launch_generation",
        lambda app, cfg, job, kind: launched.append((job.id, kind)),
    )

    app = JobHuntApp(cfg, jobs, keywords)
    async with app.run_test(size=(120, 30)) as pilot:
        # Press 'o' to open current job's browser link
        await pilot.press("o")
        await pilot.pause()
        assert opened_urls == ["https://example.com/job1"]

        # Press 'r' to generate resume for current job
        await pilot.press("r")
        await pilot.pause()
        assert ("job-1", "resume") in launched

        # Press 'c' to generate cover letter for current job
        await pilot.press("c")
        await pilot.pause()
        assert ("job-1", "cover letter") in launched


@pytest.mark.anyio
async def test_saved_screen_preview_commands(monkeypatch):
    cfg = {"locations": ["Remote"], "workspace": "/tmp"}
    jobs = _mock_jobs()
    keywords = []

    monkeypatch.setattr("auto_switch.storage.load_saved", lambda: list(jobs))

    opened_urls = []
    monkeypatch.setattr("webbrowser.open", lambda url: opened_urls.append(url))

    launched = []
    monkeypatch.setattr(
        "auto_switch.ui.app.launch_generation",
        lambda app, cfg, job, kind: launched.append((job.id, kind)),
    )

    app = JobHuntApp(cfg, jobs, keywords)
    async with app.run_test(size=(120, 30)) as pilot:
        # Go to SavedScreen
        await pilot.press("v")
        await pilot.pause()
        assert isinstance(app.screen, SavedScreen)

        # Press 'o' to open in browser
        await pilot.press("o")
        await pilot.pause()
        assert opened_urls == ["https://example.com/job1"]

        # Press 'r' to generate resume
        await pilot.press("r")
        await pilot.pause()
        assert ("job-1", "resume") in launched

        # Press 'c' to generate cover letter
        await pilot.press("c")
        await pilot.pause()
        assert ("job-1", "cover letter") in launched


@pytest.mark.anyio
async def test_launch_generation_toast(monkeypatch, tmp_path):
    from unittest.mock import MagicMock
    from textual.app import App, ComposeResult
    from auto_switch.ui.detail import launch_generation
    from auto_switch.ui.toast import ToastContainer, ToastItem, ToastManager

    cfg = {"locations": ["Remote"], "workspace": str(tmp_path)}
    jobs = _mock_jobs()

    monkeypatch.setattr("auto_switch.storage.export_jd", lambda job, ws: tmp_path / "test.md")
    monkeypatch.setattr("auto_switch.generate.generate_resume", lambda *args: MagicMock(returncode=0, output="OK"))

    class TestApp(App):
        def __init__(self):
            super().__init__()
            self.toast_mgr = ToastManager(self, position="bottom-right")

        def compose(self) -> ComposeResult:
            yield ToastContainer()

    app = TestApp()
    async with app.run_test() as pilot:
        launch_generation(app, cfg, jobs[0], "resume")
        await pilot.pause()
        toast = app.query_one(ToastItem)
        assert toast.state == "success"
        assert "Generated" in toast.title_text


@pytest.mark.anyio
async def test_launch_generation_modal(monkeypatch, tmp_path):
    from unittest.mock import MagicMock
    from textual.app import App
    from auto_switch.ui.detail import ResultModal, launch_generation

    cfg = {"locations": ["Remote"], "workspace": str(tmp_path)}
    jobs = _mock_jobs()

    monkeypatch.setattr("auto_switch.storage.export_jd", lambda job, ws: tmp_path / "test.md")
    monkeypatch.setattr("auto_switch.generate.generate_resume", lambda *args: MagicMock(returncode=0, output="OK"))

    class TestApp(App):
        pass

    app = TestApp()
    async with app.run_test() as pilot:
        launch_generation(app, cfg, jobs[0], "resume", use_modal=True)
        await pilot.pause()
        assert isinstance(app.screen, ResultModal)
