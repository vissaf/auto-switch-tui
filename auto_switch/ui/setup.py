"""First-run setup screens: profile onboarding, backend selection, locations.

Each screen is a standalone Textual app run sequentially before the main TUI.
All screens use centered card layouts, high-contrast labels, and clear keyboard hints.
``--list`` mode never runs these.
"""

from __future__ import annotations

from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.widgets import (
    Button,
    Footer,
    Header,
    Input,
    Label,
    RadioSet,
    SelectionList,
    Static,
)

from .. import config as config_mod
from ..locations import REGIONS, REGION_HUBS
from ..paths import experiences_dir, profile_path

TEMPLATES_DIR = Path(__file__).resolve().parents[2] / "templates"

_SETUP_COMMON_CSS = """
Screen {
    align: center middle;
    background: $background;
}
#form-card {
    width: 78;
    height: auto;
    max-height: 90%;
    border: round $primary;
    background: $surface;
    padding: 1 2;
}
#form-scroll {
    height: auto;
    max-height: 26;
    padding: 0 1;
}
#intro {
    color: $text;
    margin-bottom: 1;
}
Label {
    color: $primary;
    text-style: bold;
    margin-top: 1;
}
Input {
    margin-bottom: 1;
}
#hint {
    color: $text-muted;
    margin-top: 1;
    text-align: center;
}
#error {
    color: $error;
    text-style: bold;
    margin-top: 1;
    text-align: center;
}
#buttons {
    align: center middle;
    margin-top: 1;
    height: auto;
}
Button {
    min-width: 20;
}
"""

# -- Profile onboarding -------------------------------------------------------

_IDENTITY_TOKENS = {
    "<Your Name>": "name",
    "<Your Target Title, e.g. Senior Frontend Engineer>": "headline",
    "<X+ years, e.g. 6+>": "years",
    "<you@example.com>": "email",
    "<+XX XXXX XXX XXX>": "phone",
    "<linkedin.com/in/your-handle>": "linkedin",
    "<github.com/your-handle>": "github",
    "<City, Country>": "location",
}


class ProfileOnboardingApp(App):
    TITLE = "First Run — Create Your Profile"
    CSS = _SETUP_COMMON_CSS
    BINDINGS = [
        Binding("ctrl+enter", "submit", "Confirm"),
        Binding("ctrl+s", "submit", "Save", show=False),
        Binding("escape", "abort", "Quit"),
    ]

    def __init__(self, workspace: str | Path):
        super().__init__()
        self.workspace = Path(workspace)
        self._done = False

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="form-card"):
            yield Static(
                "[bold]No data/profile.md found.[/bold] Create it from the "
                "template — identity facts go here; work experiences go in "
                "data/work-experiences/ later.", id="intro",
            )
            with ScrollableContainer(id="form-scroll"):
                yield Label("Name *")
                yield Input(placeholder="Jane Doe", id="name")
                yield Label("Headline")
                yield Input(placeholder="Senior Frontend Engineer", id="headline")
                yield Label("Years of experience")
                yield Input(placeholder="6+", id="years")
                yield Label("Email *")
                yield Input(placeholder="jane@example.com", id="email")
                yield Label("Phone")
                yield Input(placeholder="+91 98XXX XXXXX", id="phone")
                yield Label("LinkedIn")
                yield Input(placeholder="linkedin.com/in/jane-doe", id="linkedin")
                yield Label("GitHub")
                yield Input(placeholder="github.com/janedoe", id="github")
                yield Label("Location")
                yield Input(placeholder="Gurugram, India", id="location")
            yield Static("", id="error")
            yield Static(
                "Enter next field · Tab/Shift+Tab navigate · Ctrl+Enter / click Continue to save",
                id="hint",
            )
            with Horizontal(id="buttons"):
                yield Button("Continue →", variant="primary", id="continue")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#name", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "continue":
            self.action_submit()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.screen.focus_next()

    def action_abort(self) -> None:
        self.exit(None)

    def action_submit(self) -> None:
        if self._done:
            return
        fields = {
            "name": self.query_one("#name", Input).value.strip(),
            "email": self.query_one("#email", Input).value.strip(),
            "headline": self.query_one("#headline", Input).value.strip(),
            "years": self.query_one("#years", Input).value.strip(),
            "phone": self.query_one("#phone", Input).value.strip(),
            "linkedin": self.query_one("#linkedin", Input).value.strip(),
            "github": self.query_one("#github", Input).value.strip(),
            "location": self.query_one("#location", Input).value.strip(),
        }
        if not fields["name"] or not fields["email"]:
            self.query_one("#error", Static).update("[red]Name and Email are required.[/red]")
            return
        if not fields["years"]:
            fields["years"] = ""

        template = TEMPLATES_DIR / "profile.md"
        text = template.read_text(encoding="utf-8")
        for token, field in _IDENTITY_TOKENS.items():
            value = fields[field]
            if field == "years" and not value:
                text = text.replace(f"- Years of experience: {token}\n", "")
                continue
            text = text.replace(token, value or token)
        profile_path(self.workspace).parent.mkdir(parents=True, exist_ok=True)
        profile_path(self.workspace).write_text(text, encoding="utf-8")

        exp_dir = experiences_dir(self.workspace)
        exp_dir.mkdir(parents=True, exist_ok=True)
        readme_src = TEMPLATES_DIR / "work-experiences" / "README.md"
        if readme_src.exists() and not (exp_dir / "README.md").exists():
            (exp_dir / "README.md").write_text(readme_src.read_text(encoding="utf-8"))

        self._done = True
        self.exit(True)


# -- Experience-years (one-time, optional) ------------------------------------

class ExperienceYearsApp(App):
    TITLE = "Your Experience"
    CSS = _SETUP_COMMON_CSS
    BINDINGS = [
        Binding("ctrl+enter", "submit", "Confirm"),
        Binding("ctrl+s", "submit", "Save", show=False),
        Binding("escape", "skip", "Skip"),
    ]

    def __init__(self, workspace: str | Path):
        super().__init__()
        self.workspace = Path(workspace)
        self._done = False

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="form-card"):
            yield Static(
                "How many years of professional experience do you have? The "
                "job matcher uses this to down-weight junior/mid roles that "
                "don't fit your level (edit data/profile.md any time).",
                id="intro",
            )
            yield Input(placeholder="e.g. 6+", id="years")
            yield Static("", id="error")
            yield Static("Enter / Ctrl+Enter confirm · Esc skip", id="hint")
            with Horizontal(id="buttons"):
                yield Button("Save Experience", variant="primary", id="continue")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#years", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "continue":
            self.action_submit()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.action_submit()

    def action_skip(self) -> None:
        self.exit(None)

    def action_submit(self) -> None:
        if self._done:
            return
        value = self.query_one("#years", Input).value.strip()
        if not value:
            self.action_skip()
            return
        import re as _re

        path = profile_path(self.workspace)
        text = path.read_text(encoding="utf-8")
        line = f"- Years of experience: {value}\n"
        m = _re.search(r"^- Headline:.*$", text, _re.M)
        if m:
            text = text[: m.end()] + "\n" + line + text[m.end():]
        else:
            m = _re.search(r"## Identity\s*\n", text, _re.I)
            if m:
                text = text[: m.end()] + line + text[m.end():]
            else:
                text = text.rstrip() + "\n\n## Identity\n\n" + line
        path.write_text(text, encoding="utf-8")
        self._done = True
        self.exit(True)


# -- Backend + cache setup ----------------------------------------------------

class BackendSetupApp(App):
    TITLE = "First Run — Generation Backend"
    CSS = _SETUP_COMMON_CSS
    BINDINGS = [
        Binding("ctrl+enter", "submit", "Confirm"),
        Binding("ctrl+s", "submit", "Save", show=False),
        Binding("escape", "abort", "Quit"),
    ]

    _AGENT_LABELS = (
        ("antigravity", "Antigravity CLI (agy)"),
        ("opencode", "OpenCode CLI"),
        ("claude", "Claude Code CLI"),
        ("pi", "Pi CLI"),
        ("deepseek", "DeepSeek Harness (dsh)"),
    )

    def __init__(self, cfg: dict, detected: dict[str, bool]):
        super().__init__()
        self.cfg = cfg
        self.detected = detected
        self._done = False
        self._label_to_name: dict[str, str] = {}
        for name, label in self._AGENT_LABELS:
            status = "detected" if detected.get(name) else "not on PATH"
            self._label_to_name[f"{label} — {status}"] = name
        self._label_to_name["Direct LLM API key (no agent CLI needed)"] = "api"

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="form-card"):
            yield Static(
                "How should resumes and cover letters be generated? Pick the "
                "agent CLI you use, or a direct LLM API key.", id="intro",
            )
            with ScrollableContainer(id="form-scroll"):
                yield RadioSet(*self._label_to_name.keys(), id="backends")
                yield Label("Cache time for job fetches (minutes, 0 = no caching)")
                yield Input(value=str((self.cfg.get("cache") or {}).get("ttl_minutes", 30)), id="ttl")
                yield Label("API provider (used only if API backend is selected)")
                yield Input(
                    value=(self.cfg.get("generation", {}).get("api", {}) or {}).get("provider")
                    or "openai",
                    placeholder="openai | anthropic | google | deepseek | openrouter",
                    id="provider",
                )
                yield Label("API key (stored locally with 0600 perms; blank = use AUTO_SWITCH_API_KEY env)")
                yield Input(password=True, id="apikey")
            yield Static("", id="error")
            yield Static(
                "↑↓ / Space select option · Tab next · Ctrl+Enter / click Continue to confirm",
                id="hint",
            )
            with Horizontal(id="buttons"):
                yield Button("Continue →", variant="primary", id="continue")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#backends", RadioSet).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "continue":
            self._submit(allow_default=False)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.screen.focus_next()

    def action_abort(self) -> None:
        self.exit(None)

    def _default_backend(self) -> str:
        for name, _label in self._AGENT_LABELS:
            if self.detected.get(name):
                return name
        return "api"

    def action_submit(self) -> None:
        self._submit(allow_default=True)

    def _submit(self, allow_default: bool) -> None:
        if self._done:
            return
        radio = self.query_one("#backends", RadioSet)
        pressed = radio.pressed_button
        backend = self._label_to_name.get(str(pressed.label)) if pressed else None
        if backend is None:
            if allow_default:
                backend = self._default_backend()
            else:
                self.query_one("#error", Static).update("[red]Pick a backend first.[/red]")
                return
        ttl_raw = self.query_one("#ttl", Input).value.strip()
        try:
            ttl = int(ttl_raw)
        except ValueError:
            self.query_one("#error", Static).update("[red]Cache time must be a whole number of minutes.[/red]")
            return
        if ttl < 0:
            self.query_one("#error", Static).update("[red]Cache time must be >= 0.[/red]")
            return

        generation = self.cfg.setdefault("generation", {})
        generation["backend"] = backend
        generation["selected"] = True
        self.cfg.setdefault("cache", {})["ttl_minutes"] = ttl

        if backend == "api":
            provider = self.query_one("#provider", Input).value.strip() or "openai"
            generation.setdefault("api", {})["provider"] = provider
            key = self.query_one("#apikey", Input).value.strip()
            if key:
                config_mod.write_api_key(key)

        config_mod.save_config(self.cfg)
        self._done = True
        self.exit(True)


# -- Locations (every run) ----------------------------------------------------

class LocationsApp(App):
    TITLE = "Where are you looking for jobs?"
    CSS = _SETUP_COMMON_CSS
    BINDINGS = [
        Binding("ctrl+enter", "submit", "Fetch jobs"),
        Binding("ctrl+s", "submit", "Fetch jobs", show=False),
        Binding("escape", "abort", "Quit"),
    ]

    def __init__(self, cfg: dict):
        super().__init__()
        self.cfg = cfg
        self._done = False
        current = set(cfg.get("locations") or [])
        self.preset_locations = [r for r in REGIONS if r in current]
        self.custom_current = [c for c in (cfg.get("locations") or []) if c not in REGIONS]

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="form-card"):
            yield Static(
                "Select target areas for job hunting. Press [bold cyan]Space[/] or [bold cyan]Enter[/] to toggle checkboxes. "
                "Add custom cities below.", id="intro",
            )
            options = [
                (f"{region} — {', '.join(REGION_HUBS[region][:4])}", region, region in self.preset_locations)
                for region in REGIONS
            ]
            with ScrollableContainer(id="form-scroll"):
                yield SelectionList(*options, id="locations")
                yield Label("Custom locations (comma-separated, optional)")
                yield Input(value=", ".join(self.custom_current), id="custom", placeholder="e.g. London, Remote, Berlin")
            yield Static("", id="error")
            yield Static(
                "Space/Enter toggle · ↑↓ move · Tab next · Ctrl+Enter / click to fetch",
                id="hint",
            )
            with Horizontal(id="buttons"):
                yield Button("Fetch Jobs →", variant="primary", id="continue")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#locations", SelectionList).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "continue":
            self.action_submit()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.screen.focus_next()

    def action_abort(self) -> None:
        self.exit(None)

    def action_submit(self) -> None:
        if self._done:
            return
        selected = list(self.query_one("#locations", SelectionList).selected)
        custom_raw = self.query_one("#custom", Input).value.strip()
        custom = [c.strip() for c in custom_raw.split(",") if c.strip()]
        locations = selected + custom
        if not locations:
            self.query_one("#error", Static).update("[red]Pick at least one area (or quit with Esc).[/red]")
            return
        self.cfg["locations"] = locations
        config_mod.save_config(self.cfg)
        self._done = True
        self.exit(True)
