# Phase 0 Foundation — TDD Evidence

Source plan: `docs/IMPLEMENTATION_PLAN.md`, tasks P0.1–P0.5.

## User journeys

- As a local operator, I can invoke the installed CLI and understand that it creates local approved drafts.
- As a local operator, I can inspect status before any pipeline run without an error.
- As an implementer, I can resolve portable workspace paths and override them through explicit environment variables.

## RED evidence

Command:

```text
uv run --no-project --with pytest --with typer pytest tests/unit/test_cli.py tests/unit/test_config.py
```

Result: collection failed with two `ModuleNotFoundError: No module named 'social_media_agent'` errors. This was the intended failure because the planned Python package and CLI did not exist. Checkpoint: `c57b5cb`.

## GREEN evidence

| Guarantee | Test or command | Result |
|---|---|---|
| Root help describes local draft generation | `tests/unit/test_cli.py` | PASS |
| Status works before and after a state file exists | `tests/unit/test_cli.py` | PASS |
| Default paths remain worktree-relative | `tests/unit/test_config.py` | PASS |
| Relative and absolute overrides resolve correctly | `tests/unit/test_config.py` | PASS |
| Expected errors share a catchable base | `tests/unit/test_errors.py` | PASS |
| Installed entry point executes | `uv run social-agent status` | PASS |
| Code is formatted and lint-clean | `uv run ruff format --check src tests`; `uv run ruff check src tests` | PASS |
| Application code passes strict typing | `uv run mypy` | PASS |

Coverage command:

```text
uv run pytest --cov=social_media_agent --cov-report=term-missing
```

Result: 7 tests passed; 100% statement and branch coverage across measured application modules. The `__main__.py` bootstrap is intentionally omitted because its behavior is exercised through the installed console entry point. GREEN checkpoint: `e6bac0c`.

## Known gaps

The CLI currently exposes only the Phase 0 `status` shell. Queue parsing, persisted state semantics, run/resume commands, and pipeline behavior begin in Phase 1.

