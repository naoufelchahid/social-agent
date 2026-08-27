# Phase 8 Legacy Removal — TDD Evidence

Source plan: `docs/IMPLEMENTATION_PLAN.md`, tasks P8.1–P8.4.

## P8.1 removal boundary

The RED checkpoint added `tests/unit/test_legacy_removal.py`. Both tests failed because the approved legacy paths still existed and Dependabot still targeted npm plus the `memory-v2` pip project.

The GREEN implementation removed:

- legacy executable roots: `src/agents`, `src/clients`, `src/evals`, `src/tests`, `src/utils`, `scripts`, `memory-v2`, and `slack-messaging`;
- generated legacy assets under `static`;
- Node, TypeScript, Jest, ESLint, LangGraph, Docker-ignore, and Yarn root files;
- obsolete npm and removed-memory-project Dependabot entries.

The local Python application, Python tests/fixtures, content templates, governed documents, `uv` lockfile, and Python GitHub Actions remain.

## Verification

```text
uv run pytest tests/unit/test_legacy_removal.py -q
2 passed

uv run ruff format --check src tests
47 files already formatted

uv run ruff check src tests
All checks passed

uv run mypy
Success: no issues found in 19 source files

uv run pytest -m "not live" tests/e2e/test_local_pipeline.py -q
1 passed

uv run pytest -m "not live" --cov=social_media_agent --cov-report=term-missing -q
184 passed, 2 deselected; 85.65% coverage
```

An `rg --files` inventory after deletion returned no TypeScript/JavaScript source, `package.json`, `yarn.lock`, or LangGraph manifest. Deletions were staged through Git and remain recoverable from repository history.

## P8.2 operational documentation/configuration boundary

The RED checkpoint extended `tests/unit/test_documentation.py` and failed because the legacy feature guide, two hosted-service env examples, VS Code/codespell settings, and Node/LangGraph ignore rules still existed.

The GREEN implementation removed those obsolete files and reduced `.gitignore` to retained Python, secrets, generated-output, notebook, and OS patterns. The local README, canonical `.env.example`, Python CI, and governed historical documents remain.

```text
uv run pytest tests/unit/test_documentation.py tests/unit/test_legacy_removal.py -q
6 passed

uv run ruff format --check src tests
47 files already formatted

uv run ruff check src tests
All checks passed

uv run mypy
Success: no issues found in 19 source files

uv run pytest -m "not live" tests/e2e/test_local_pipeline.py -q
1 passed

uv run pytest -m "not live" --cov=social_media_agent --cov-report=term-missing -q
185 passed, 2 deselected; 85.65% coverage
```

A targeted search of operational documentation/configuration returned none of the removed LangGraph, LangSmith, Supabase, Anthropic/Vertex, Arcade, Slack, cron, curation, repurposing, reflection, or image-discovery setup concepts. Negative safety language stating that the product does not publish or schedule remains intentionally.

## P8.3 retained-surface audit

The RED checkpoint extended `tests/unit/test_legacy_removal.py` with an exact tracked-root allowlist. It failed only because `.editorconfig` remained; its sole scoped rule targeted JavaScript, JSON, and YAML.

Removing that file made the tracked root exactly the local Python application and support surface: Python package metadata and `uv` lockfile, Python CI/dependency automation, tests/fixtures, content templates, output placeholder, README/license, and governed documents.

```text
uv run pytest tests/unit/test_legacy_removal.py -q
3 passed

uv run ruff format --check src tests
47 files already formatted

uv run ruff check src tests
All checks passed

uv run mypy
Success: no issues found in 19 source files

uv run pytest -m "not live" tests/e2e/test_local_pipeline.py -q
1 passed

uv run pytest -m "not live" --cov=social_media_agent --cov-report=term-missing -q
186 passed, 2 deselected; 85.65% coverage
```

## P8.4 durable removal and replacement record

The governed decision log now records that the local Python CLI is the sole product implementation. It maps the removed hosted and auxiliary workflow concepts to the retained sequential local workflow: Markdown queue, bounded extraction, Agy drafting, deterministic and independent Codex review, mandatory project-local image generation, terminal human approval, and immutable approved manifests.

The delete-zone makes reintroduction conditional on an explicit scope decision, supporting tests, and a new acceptance gate. No production code changed, so there was no production-code RED/GREEN cycle for this documentation-only task.

```text
rg -n -i --glob '!uv.lock' --glob '!*.pyc' \
  'langgraph|langsmith|supabase|anthropic|openai|vertex|arcade|slack|schedule|scheduling|publishing|cron|curation|repurposing|reflection|image.discovery' .

Only intentional historical/removal records and active negative safety boundaries remain.
```

## P8.5 acceptance-harness resilience

The final gate initially ran RED because this copied worktree's `.git` file points to a removed parent-worktree directory, making `git ls-files` unavailable. The legacy-removal regression now uses the exact tracked-root allowlist when Git metadata works and the same exact repository-root allowlist plus named local runtime entries when it does not. This preserves the removal boundary for normal worktrees and source exports without repairing or replacing the user's broken Git metadata.

GREEN focused evidence:

```text
uv run pytest tests/unit/test_documentation.py tests/unit/test_legacy_removal.py -q
7 passed
```

Final acceptance ran in a freshly created locked `uv` environment with hosted-model, hosted-service, social-platform, Firecrawl, and GitHub credentials unset:

```text
uv sync --locked --all-groups
uv run ruff format --check src tests
47 files already formatted

uv run ruff check src tests
All checks passed

uv run mypy
Success: no issues found in 19 source files

uv run pytest -m "not live" tests/e2e/test_local_pipeline.py -q
1 passed

uv run pytest -m "not live" --cov=social_media_agent --cov-report=term-missing -q
186 passed, 2 deselected; 85.65% coverage
```

`uv run social-agent --help` and `uv run social-agent status` both ran in that environment. An inventory found no TypeScript/JavaScript, Node manifest/lockfile, or LangGraph manifest; supported project metadata, configuration, README, and CI contain no required LangGraph, LangSmith, Supabase, hosted-model SDK, Node, or database dependency. Live agent tests remain intentionally opt-in and were not run by this offline gate.

## Completion

P8.1–P8.5 are complete. The implementation plan's final acceptance gate has passed.
