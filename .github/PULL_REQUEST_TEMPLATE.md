## What this changes and why

<!-- One or two sentences. Link the issue it fixes: "Fixes #123". -->

## How it was tested

<!-- The test that failed before this change and passes after it. -->

## Checklist

- [ ] Every commit is signed off (`git commit -s`), per [CONTRIBUTING.md](../CONTRIBUTING.md)
- [ ] `uv run pytest` passes with 100% coverage
- [ ] `uv run ruff format --check .`, `uv run ruff check .` and `uv run mypy src` pass
- [ ] A line under *Unreleased* in CHANGELOG.md
- [ ] No API keys, broker logins, passwords or account details anywhere in the change
