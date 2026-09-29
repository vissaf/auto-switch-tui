.PHONY: setup run list test smoke lint format clean

setup:
	uv venv
	uv pip install -e ".[dev]"
	uv tool install --force --editable .
	uv run playwright install chromium
	@echo "Done! You can now run 'auto-switch' directly in any terminal window."

run:
	uv run auto-switch $(ARGS)

list:
	uv run auto-switch --list $(ARGS)

test:
	uv run pytest tests/ -q

lint:
	uv run ruff check .

format:
	uv run ruff format .

smoke:
	uv run auto-switch --list --provider remotive --no-cache

clean:
	rm -rf .venv
