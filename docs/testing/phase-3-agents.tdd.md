# Phase 3 Local Agents — TDD Evidence

Source plan: `docs/IMPLEMENTATION_PLAN.md`, tasks P3.1–P3.5.

## Completed guarantees

| Task | Guarantee | Evidence | Result |
|---|---|---|---|
| P3.1 | Local commands use literal argument arrays without a shell, workspace-confined cwd, an explicit environment allowlist, captured output, fresh process sessions, bounded execution, process-group timeout cleanup, and cancellation cleanup | `tests/unit/test_commands.py` | PASS |
| P3.2 | Agy receives a controlled file-referencing prompt, returns exactly one strict JSON object, receives one formatting-repair call for malformed output, and persists prompts/raw output/draft under the post directory | `tests/unit/test_agents.py` | PASS |
| P3.3 | Draft JSON is a strict versioned contract containing one canonical concept, LinkedIn and X renderings, and one shared image brief | `tests/unit/test_agents.py` | PASS |
| P3.4 | Codex runs as a fresh ephemeral read-only invocation with a persisted JSON schema, independently validated output, and file-referenced source/brand/draft context | `tests/unit/test_agents.py` | PASS |
| P3.5 | Prompt templates are versioned, raw output remains inside the local post artifact directory, diagnostic secrets can be redacted, and success/timeout/nonzero/invalid/repair/cancellation paths are deterministic | `tests/unit/test_agents.py`, `tests/unit/test_commands.py` | PASS |

## RED/GREEN checkpoints

- P3.1 RED: `uv run pytest tests/unit/test_commands.py -q` failed at collection because `social_media_agent.commands` did not exist.
- P3.1 GREEN: all 5 focused command-runner tests passed.
- P3.2–P3.5 RED: `uv run pytest tests/unit/test_agents.py -q` failed at collection because `social_media_agent.agents` did not exist.
- P3.2–P3.5 GREEN: all 10 focused agent-adapter scenarios and all 5 command-runner scenarios passed.

## Current quality evidence

```text
uv run pytest --cov=social_media_agent --cov-report=term-missing
112 passed; 87.55% total coverage

uv run ruff format --check src tests
33 files already formatted

uv run ruff check src tests
All checks passed

uv run mypy
Success: no issues found in 15 source files

git diff --check
PASS
```

## Current phase boundary

P3.1–P3.5 and the Phase 3 local-agent gate are complete. Phase 4 begins with deterministic draft validation in P4.1.
