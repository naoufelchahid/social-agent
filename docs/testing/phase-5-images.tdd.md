# Phase 5 Mandatory Images — TDD Evidence

Source plan: `docs/IMPLEMENTATION_PLAN.md`, tasks P5.1–P5.5.

## Completed guarantees

| Task | Guarantee | Evidence | Result |
|---|---|---|---|
| P5.1 | A validated image brief becomes a strict schema-version-1 `stylized-concept` request for a 1536x1024 editorial technical illustration with no embedded text, logos/trademarks, or watermarks | `tests/unit/test_images.py` | PASS |
| P5.2 | A fresh Codex invocation uses `workspace-write`, `$imagegen`, a 15-minute timeout, a strict output schema, and an exact project-local `output/posts/<post-id>/image.png` target; request, prompt, raw output, and structured result are persisted | `tests/unit/test_images.py` | PASS |
| P5.3 | Local validation rejects missing, outside, symlinked, corrupt, non-PNG, and wrong-dimension files; accepted files retain size, MIME, dimensions, and SHA-256 evidence | `tests/unit/test_images.py` | PASS |
| P5.4 | A fresh read-only Codex process receives the image through `--image`, reviews relevance, unwanted text, logos, watermarks, and post consistency, and shares a maximum of two regenerations across file and semantic failures | `tests/unit/test_images.py` | PASS |
| P5.5 | `ImageArtifact` retains the final path, prompt, generator identity, dimensions, MIME, size, hash, generation attempt, and semantic review; resumption revalidates integrity and rejects later mutation | `tests/unit/test_images.py` | PASS |
| P5.5 | An explicitly opted-in live Codex `$imagegen` smoke generated, copied, reviewed, persisted, visually inspected, and reloaded a project-local 1536x1024 PNG | `tests/live/test_image_generation_live.py` | PASS |

## RED/GREEN checkpoints

- Initial RED: `uv run pytest tests/unit/test_images.py -q` failed during collection because the Phase 5 image contracts and errors did not exist.
- Initial GREEN: 13 focused mocked image tests passed.
- Semantic-invariant RED: a contradictory review with `passed=true` and `no_logos=false` was accepted.
- Semantic-invariant GREEN: `ImageSemanticReview` now requires its pass state to match all five criteria; 14 focused tests pass.
- Live-schema RED: authenticated Codex returned `invalid_json_schema` because Pydantic omitted defaulted fields from the output schema's `required` array.
- Live-schema GREEN: generation and review schemas now require every declared property; the opted-in live smoke passed in 114.46 seconds.

No checkpoint commits were created because the worktree already contains the documented uncommitted Phase 2–4 implementation; isolated Phase 5 commits would not represent a self-contained build. This report preserves the RED/GREEN evidence.

## Current quality evidence

```text
uv run pytest --cov=social_media_agent --cov-report=term-missing
152 passed, 1 skipped; 87.88% total coverage

SOCIAL_AGENT_LIVE_IMAGE_TEST=1 uv run pytest tests/live/test_image_generation_live.py -q -s
1 passed in 114.46s

uv run ruff format --check src tests
39 files already formatted

uv run ruff check src tests
All checks passed

uv run mypy
Success: no issues found in 17 source files
```

## Retained live evidence

- Post directory: `output/posts/live-smoke-8adc45482c/`
- Final image: `output/posts/live-smoke-8adc45482c/image.png`
- Artifact: `output/posts/live-smoke-8adc45482c/image-artifact.json`
- Verified properties: PNG, 1536x1024, 1,793,705 bytes, SHA-256 `958ffff08228b87ba770267198e28fd68b12e1882d9a26f1c98cb3062ce20235`.
- Semantic result: relevant, consistent, and free of unwanted text, logos, and watermarks.

The earlier failed live attempt remains under `output/posts/live-smoke-fab6ed9957/` as diagnostic evidence for the strict-schema correction; it contains no accepted image artifact.

## Phase boundary

P5.1–P5.5 and the Phase 5 gate are complete. The next governed task is P6.1, the Rich terminal human-review screen.
