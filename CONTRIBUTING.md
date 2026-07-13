# Contributing to NetBlackBox

## Development setup

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
python -m pip install -e ".[dev]"
pre-commit install
```

## Local checks

Run the same checks used by CI before opening a pull request:

```bash
black --check src tests
ruff check src tests
mypy src/netblackbox
pytest
```

To apply automatic formatting and safe lint fixes:

```bash
black src tests
ruff check --fix src tests
```

## Commit style

Use focused commits with Conventional Commit prefixes where practical, for example:

```text
feat: persist external probe measurements
fix: handle missing default gateway on Windows
test: cover plugin discovery failures
docs: document macOS migration
```

Keep platform-specific service installation separate from the portable monitoring core.
