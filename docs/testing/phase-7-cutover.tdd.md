# Phase 7 End-to-End Cutover — TDD Evidence

Source plan: `docs/IMPLEMENTATION_PLAN.md`, tasks P7.1–P7.4.

## P7.1 completed guarantees

| Guarantee | Evidence | Result |
|---|---|---|
| Queue jobs execute strictly one at a time in Markdown order | `tests/unit/test_pipeline.py::test_run_is_sequential_and_continues_after_failure_and_rejection` | PASS |
| Extraction failure and human rejection do not prevent later jobs from running | `tests/unit/test_pipeline.py::test_run_is_sequential_and_continues_after_failure_and_rejection` | PASS |
| Skip leaves a job pending but selects it only once in the current run | `tests/unit/test_pipeline.py::test_skip_is_pending_but_selected_only_once_in_the_same_run` | PASS |
| Interrupted work resumes at the exact recorded stage without repeating earlier stages | `tests/unit/test_pipeline.py::test_resume_restores_interrupted_stage_without_repeating_prior_work` | PASS |
| Failed work is excluded from ordinary resume until `retry-failed` restores its recorded stage | `tests/unit/test_state.py::test_failed_job_requires_explicit_retry_before_resume`, `tests/unit/test_cli.py::test_retry_failed_restores_the_recorded_stage` | PASS |
| The Typer surface exposes `run`, `resume`, `status`, `retry-failed`, and `review` | `tests/unit/test_cli.py::test_phase_7_exposes_complete_local_command_surface` | PASS |

## P7.1 RED/GREEN checkpoints

- RED commit `724dc49`: focused tests failed during collection because `social_media_agent.pipeline` did not exist.
- GREEN commit `62f4f21`: the sequential coordinator, production workflow adapter, and complete CLI command surface passed the focused suite.
- Retry-boundary RED commit `1b6f795`: a failed job was incorrectly returned by ordinary resume selection.
- Retry-boundary GREEN commit `3288a1f`: failed jobs became inactive until explicitly restored by `retry-failed`.

## P7.1 verification

```text
uv run pytest tests/unit/test_state.py tests/unit/test_cli.py tests/unit/test_pipeline.py -q
27 passed

uv run pytest --cov=social_media_agent --cov-report=term-missing -q
176 passed, 1 skipped; 83.25% coverage (before the two retry-boundary tests)

uv run ruff format --check src tests
PASS

uv run ruff check src tests
All checks passed

uv run mypy
Success: no issues found in 19 source files

git diff --check
PASS
```

## Phase 7 completion

- P7.1–P7.4 are complete. The automated gate and one manually approved live URL both pass.

## P7.2 completed guarantees

| Guarantee | Evidence | Result |
|---|---|---|
| A complete offline URL proceeds through fixture Firecrawl evidence, fake Agy drafting, fake Codex text/image review, a generated 1536×1024 PNG, explicit local acceptance, immutable manifest creation, and checkbox synchronization | `tests/e2e/test_local_pipeline.py::test_complete_offline_workflow_approves_once_with_real_artifacts` | PASS |
| Re-running an approved queue does not invoke agents or duplicate work | Same end-to-end test and its persisted fake-agent call log | PASS |
| A live URL can be opted in explicitly and reaches `human_review` with a project-local image without accepting on the user's behalf | `tests/live/test_pipeline_live.py` | SKIPPED by default |

The first end-to-end execution reached fake Codex image generation and failed because the fixture attempted to make an already-relative path relative to an absolute workspace. Fixing the fixture path completed the workflow; no production exception or bypass was added.

```text
uv run pytest tests/e2e/test_local_pipeline.py tests/live/test_pipeline_live.py -q
1 passed, 1 skipped

uv run pytest --cov=social_media_agent --cov-report=term-missing -q
179 passed, 2 skipped; 85.64% coverage
```

P7.2 GREEN checkpoint: `b50b59f`.

## P7.3 completed guarantees

| Guarantee | Evidence | Result |
|---|---|---|
| README setup and usage match the local `uv`/Typer workflow, Agy/Codex prerequisites, optional Firecrawl path, human review boundary, resumption commands, and artifact layout | `tests/unit/test_documentation.py::test_readme_documents_the_complete_local_cli_boundary` | PASS |
| `.env.example` contains only supported extraction and workspace overrides | `tests/unit/test_documentation.py::test_environment_example_contains_only_supported_local_inputs` | PASS |
| Default GitHub Actions use locked `uv` environments for formatting, lint, strict typing, offline coverage, and mocked end-to-end execution without live agents | `tests/unit/test_documentation.py::test_default_ci_is_uv_only_and_never_runs_live_agents` | PASS |

- RED commit `ad9f8d5`: all three documentation contracts failed against the legacy guide, absent `.env.example`, and Node workflows.
- GREEN commit `1c4c20b`: all three contracts pass after the local Python cutover.
- Official repository tags were inspected before choosing current action majors: `actions/checkout@v7` and `astral-sh/setup-uv@v9`.

## P7.4 acceptance evidence to date

```text
uv sync --locked --all-groups
Resolved 70 packages; checked 67 packages

uv run ruff format --check src tests
47 files already formatted

uv run ruff check src tests
All checks passed

uv run mypy
Success: no issues found in 19 source files

uv run pytest -m "not live" --cov=social_media_agent --cov-report=term-missing -q
182 passed, 2 deselected; 85.65% coverage

uv run pytest -m "not live" tests/e2e/test_local_pipeline.py -q
1 passed

codex login status
Logged in using ChatGPT

agy --print "Reply with exactly OK"
OK

df -BG .
84G available
```

The first opted-in live run used `https://github.com/langchain-ai/social-media-agent`. It proved safe failure for missing exact Agy read permissions, semantic grounding rejection, bounded rewrites, and validation exhaustion; no image approval, checkbox mutation, publication, or scheduling occurred.

The accepted live run used `https://github.com/astral-sh/uv` (post `30e283a9b3f70e35`). It completed GitHub extraction, Agy drafting plus one grounded rewrite, deterministic and independent Codex text validation, real Codex image generation, local file validation, independent image review, and terminal human review. The user inspected the final copy and image and explicitly replied `accept`; the application then persisted `approved-manifest.json` and synchronized the matching checkbox. It never published or scheduled the content.

The live gate found three contract gaps and one test-isolation issue. Writer prompts now prohibit unlisted workspace reads, require integer `schema_version = 1`, Codex reviewer schemas require every property for strict structured output, and the empty-status CLI test uses a temporary workspace. Focused agent and CLI tests, Ruff, strict mypy, the mocked end-to-end test, and the complete offline coverage suite all pass after these changes.
