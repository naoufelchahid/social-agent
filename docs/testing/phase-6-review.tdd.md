# Phase 6 Local Human Review — TDD Evidence

Source plan: `docs/IMPLEMENTATION_PLAN.md`, tasks P6.1–P6.5.

## Completed guarantees

| Task | Guarantee | Evidence | Result |
|---|---|---|---|
| P6.1 | The Rich review screen shows source provenance, LinkedIn and X renderings, deterministic warnings, and the mandatory image path; the OS viewer runs only after an explicit open action | `tests/unit/test_review.py` | PASS |
| P6.2 | Interactive review supports Accept, Edit, Regenerate text, Regenerate image, Open image, Replace image, Skip, Reject, and Save/Quit; noninteractive use requires an exact post ID and explicit action | `tests/unit/test_review.py` | PASS |
| P6.3 | Human text edits always receive deterministic validation, material edits receive a fresh semantic review, whitespace-only edits retain the prior semantic result, and replacement images pass local and semantic validation before replacing the accepted asset | `tests/unit/test_review.py` | PASS |
| P6.4 | Accept revalidates the image artifact, writes an immutable approval manifest, records approval, checks the exact Markdown queue item, and exposes the next pending job; checkbox failure preserves approval with a recoverable warning | `tests/unit/test_review.py` | PASS |
| P6.5 | Interaction coverage exercises every action plus editor failure, EOF, Ctrl-C, failed text/image revalidation, immutable manifests, and exact `human_review` resumption | `tests/unit/test_review.py` | PASS |

## RED/GREEN checkpoints

- Initial RED: `uv run pytest tests/unit/test_review.py -q` failed during collection because `HumanReviewError` and the human-review module did not exist.
- Initial GREEN: all 16 review scenarios passed after implementing the screen, action service, edits, replacement images, and approval boundary.
- Gate expansion: four additional scenarios proved semantic edit rejection, local and semantic image-replacement rejection without damage to the current image, and advancement to the next pending job.
- Final focused GREEN: all 20 review tests pass in 7.33 seconds.
- During GREEN, the first screen assertion expected panel text without Rich padding. The rendered content was correct; the test was corrected to assert the visible content rather than Rich's layout whitespace.

No checkpoint commits were created because the worktree already contains the documented uncommitted Phase 2–5 implementation; an isolated Phase 6 commit would not represent a self-contained build. This report preserves the RED/GREEN evidence.

## Current quality evidence

```text
uv run pytest tests/unit/test_review.py -q
20 passed in 7.33s

uv run pytest --cov=social_media_agent --cov-report=term-missing
172 passed, 1 skipped; 86.51% total coverage

uv run ruff format --check src tests
41 files already formatted

uv run ruff check src tests
All checks passed

uv run mypy
Success: no issues found in 18 source files

git diff --check
PASS
```

## Phase boundary

P6.1–P6.5 and the Phase 6 gate are complete. The next governed task is P7.1, wiring the sequential pipeline coordinator and CLI commands.
