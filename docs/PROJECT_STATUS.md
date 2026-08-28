# Project Status and Session Handoff

Last updated: 2026-08-26

## Current checkpoint

- Branch: `refactor/python-local-pipeline`
- Worktree: `/home/naoufel/projects/social-media-agent-python-refactor`
- Milestone: Phase 8 — Legacy removal and final simplification
- Active task: None
- State: P8.1–P8.5 complete; implementation plan complete
- Plan review: approved by the user on 2026-08-25
- Blockers: The product plan has none. The checkout's `.git` file references a removed parent worktree, so Git status/diff commands need metadata repair before future Git operations.
- Next task: No implementation-plan task remains. Repair the external Git worktree metadata before the next repository-history operation.
- First next-session read: `docs/IMPLEMENTATION_PLAN.md`, `docs/PROJECT_STATUS.md`, `docs/DECISIONS.md`, and `docs/testing/phase-8-removal.tdd.md`.

## Progress

| Phase | State | Completed tasks | Gate evidence |
|---|---|---|---|
| 0. Foundation | Complete | P0.1–P0.5 | 7 tests; 100% coverage; Ruff and mypy pass |
| 1. Queue/state | Complete | P1.1–P1.5 | 44 tests; 92.41% coverage; Ruff and mypy pass |
| 2. Extraction | Complete | P2.1–P2.7 | 97 tests; 88.16% coverage; Ruff and mypy pass |
| 3. Local agents | Complete | P3.1–P3.5 | 112 tests; 87.55% coverage; Ruff and mypy pass |
| 4. Text validation | Complete | P4.1–P4.5 | 138 tests; 88.21% coverage; Ruff and mypy pass |
| 5. Images | Complete | P5.1–P5.5 | 152 default tests pass, 1 live skipped; opted-in live smoke passes; 87.88% coverage; Ruff and mypy pass |
| 6. Human review | Complete | P6.1–P6.5 | 172 default tests pass, 1 live skipped; 20 focused review tests; 86.51% coverage; Ruff and mypy pass |
| 7. Cutover | Complete | P7.1–P7.4 | 182 offline tests pass, 2 live deselected; 85.65% coverage; mocked end-to-end and one manually approved live URL pass; Ruff and mypy pass |
| 8. Legacy removal | Complete | P8.1–P8.5 | Fresh locked `uv` environment; 186 offline tests pass, 2 live deselected; 85.65% coverage; mocked end-to-end, Ruff, mypy, CLI smoke, and removed-surface checks pass |

## Session log

### 2026-08-25 — Planning baseline

- Added the canonical implementation plan, session instructions, status checkpoint, and decision history.
- Verified that the clean worktree starts at commit `d3f416d` and the existing application is still TypeScript/LangGraph-based.
- Tests run: none; documentation-only planning change.
- Changed paths: `AGENTS.md`, `docs/IMPLEMENTATION_PLAN.md`, `docs/PROJECT_STATUS.md`, `docs/DECISIONS.md`.
- Uncommitted state: the four planning/governance documents above.
- Next exact action: implement P0.1 without deleting legacy code.

### 2026-08-25 — Plan approval

- The user approved `docs/IMPLEMENTATION_PLAN.md` without requested changes.
- The plan is the implementation baseline; scope changes require an explicit decision-log entry.
- Next exact action remains P0.1.

### 2026-08-25 — Phase 0 complete

- Replaced the root Python metadata with a `uv`/Hatchling project and locked the approved runtime/development dependencies.
- Added the typed package shell, configuration loader, error hierarchy, logging, installed Typer entry point, content templates, and ignored output workspace.
- RED: `c57b5cb` proved the package interfaces were absent for the intended reason.
- GREEN: `e6bac0c` implements the foundation; 7 tests pass with 100% measured coverage.
- Verification: `uv run pytest --cov=social_media_agent --cov-report=term-missing`, `uv run ruff format --check src tests`, `uv run ruff check src tests`, `uv run mypy`, and `uv run social-agent status` all pass.
- Evidence: `docs/testing/phase-0-foundation.tdd.md`.
- Uncommitted paths after this update: `docs/PROJECT_STATUS.md`, `docs/testing/phase-0-foundation.tdd.md`.
- Next exact action: implement P1.1 via RED tests for queue parsing.

### 2026-08-25 — Phase 1 durable-state checkpoint

- Added Markdown queue parsing, canonical URL identities, and stable post IDs.
- Added strict job/state models, atomic state replacement, explicit transitions, deterministic resume ordering, exact failed/interrupted stage restoration, and a single-writer advisory lock.
- Added workspace-confined atomic text/JSON artifact storage and useful `status`/`resume` CLI output.
- RED checkpoints: `04ba6b1`, `c784689`, and `0f4b164`; GREEN checkpoints: `6978adc` and `ee1abeb`.
- Verification: 37 tests pass at 93.14% coverage; Ruff formatting/lint and strict mypy pass.
- Evidence: `docs/testing/phase-1-state.tdd.md`.
- Uncommitted paths after this update: `docs/PROJECT_STATUS.md`, `docs/testing/phase-1-state.tdd.md`.
- Next exact action: finish P1.5 with signal-interruption RED/GREEN tests; do not start extraction first.

### 2026-08-25 — Phase 1 complete

- Added cooperative SIGINT/SIGTERM capture that never raises during an atomic write.
- Added parameterized proof that extracting, drafting, text validation, image generation, image validation, and human review all record `interrupted` and resume their exact prior stage once.
- RED checkpoint: `5d3df93`; GREEN checkpoint: `929acb7`.
- Verification: 44 tests pass at 92.41% coverage; Ruff formatting/lint and strict mypy pass.
- Updated `docs/testing/phase-1-state.tdd.md` with the completed gate.
- Uncommitted paths after this update: `docs/PROJECT_STATUS.md`, `docs/testing/phase-1-state.tdd.md`.
- Next exact action: begin P2.1 with extractor protocol and routing RED tests.

### 2026-08-25 — Phase 2 extraction contract (P2.1)

- Added strict, versioned `ExtractedSource` provenance with typed source families and extraction methods.
- Added one runtime-checkable async extractor protocol, canonical extraction requests, exact-host source classification, and a dispatcher that prefers a configured Firecrawl extractor or selects the matching source fallback.
- Kept Firecrawl exception categorization and fallback-on-error out of P2.1; those are the explicit P2.2 boundary.
- RED: `uv run pytest tests/unit/test_extraction.py -q` failed during collection because the extraction error and contract were absent.
- GREEN: 11 focused extraction tests pass.
- Verification: 55 tests pass at 93.90% coverage; Ruff formatting/lint and strict mypy pass.
- Evidence: `docs/testing/phase-2-extraction.tdd.md`.
- Uncommitted paths after this update: `src/social_media_agent/errors.py`, `src/social_media_agent/models.py`, `src/social_media_agent/extraction.py`, `tests/unit/test_extraction.py`, `docs/PROJECT_STATUS.md`, and `docs/testing/phase-2-extraction.tdd.md`.
- Next exact action: implement P2.2 via RED tests around a mocked Firecrawl adapter and categorized fallback reasons.

### 2026-08-25 — Firecrawl-first fallback policy (P2.2)

- Added a bounded async adapter over the synchronous Firecrawl SDK with Markdown-only, main-content scrape options.
- Mapped usable Firecrawl documents into the common provenance contract, including canonical URL, title, author, publication time, status, and extraction method.
- Categorized timeout, HTTP 408, rate limit, malformed response, unusable content, and other service failures into stable reasons without persisting exception text.
- Annotated fallback artifacts with whether Firecrawl was attempted and why the fallback ran; missing configuration skips Firecrawl and records that fact.
- RED: `uv run pytest tests/unit/test_firecrawl.py -q` failed during collection because the Firecrawl adapter and fallback error did not exist.
- GREEN: 9 focused Firecrawl tests and all 20 extraction tests pass.
- Verification: 64 tests pass at 91.95% coverage; Ruff formatting/lint and strict mypy pass.
- Evidence: `docs/testing/phase-2-extraction.tdd.md`.
- Uncommitted paths after this update: `src/social_media_agent/errors.py`, `src/social_media_agent/models.py`, `src/social_media_agent/extraction.py`, `tests/unit/test_extraction.py`, `tests/unit/test_firecrawl.py`, `docs/PROJECT_STATUS.md`, and `docs/testing/phase-2-extraction.tdd.md`.
- Next exact action: implement P2.3 via RED tests for bounded `httpx` streaming and `trafilatura` extraction.

### 2026-08-25 — General-page fallback (P2.3)

- Added a general-page extractor with explicit timeout, redirect, and streamed response-size bounds.
- Extracted readable main content and available title, author, and publication date through Trafilatura while retaining final canonical URL and bounded HTTP provenance.
- Converted timeout, redirect exhaustion, HTTP status, request, oversized-body, and unreadable-page failures into stable extraction errors without leaking upstream response details.
- RED: `uv run pytest tests/unit/test_general_extraction.py -q` failed during collection because `GeneralPageExtractor` did not exist.
- GREEN: all 7 focused general-page fallback tests pass.
- Verification: 71 tests pass at 90.80% coverage; Ruff formatting/lint and strict mypy pass; `git diff --check` passes.
- Evidence: `docs/testing/phase-2-extraction.tdd.md`.
- Uncommitted paths after this update: `src/social_media_agent/errors.py`, `src/social_media_agent/models.py`, `src/social_media_agent/extraction.py`, `tests/unit/test_extraction.py`, `tests/unit/test_firecrawl.py`, `tests/unit/test_general_extraction.py`, `docs/PROJECT_STATUS.md`, and `docs/testing/phase-2-extraction.tdd.md`.
- Next exact action: implement P2.4 via RED tests for GitHub REST repository metadata, README, and bounded root manifests without cloning.

### 2026-08-25 — GitHub REST fallback (P2.4)

- Added bounded GitHub REST reads for required repository metadata, optional raw README content, and a deterministic allowlist of small root project manifests.
- Added optional bearer authentication while keeping public requests unauthenticated and excluding tokens from extracted artifacts and errors.
- Limited API redirects, time, response bytes, manifest count, and manifest size; no clone, archive, recursive tree, or arbitrary download operation is used.
- Accepted repositories without a README or root contents while rejecting malformed required metadata and HTTP failures with stable non-sensitive errors.
- RED: `uv run pytest tests/unit/test_github_extraction.py -q` failed during collection because `GitHubRepositoryExtractor` did not exist.
- GREEN: all 7 focused GitHub fallback tests pass.
- Verification: 78 tests pass at 90.17% coverage; Ruff formatting/lint and strict mypy pass; `git diff --check` passes.
- Evidence: `docs/testing/phase-2-extraction.tdd.md`.
- Uncommitted paths after this update: `src/social_media_agent/errors.py`, `src/social_media_agent/models.py`, `src/social_media_agent/extraction.py`, `tests/unit/test_extraction.py`, `tests/unit/test_firecrawl.py`, `tests/unit/test_general_extraction.py`, `tests/unit/test_github_extraction.py`, `docs/PROJECT_STATUS.md`, and `docs/testing/phase-2-extraction.tdd.md`.
- Next exact action: implement P2.5 via RED tests for public Reddit post JSON with bounded top-level comments and readable-HTML fallback when JSON is unavailable.

### 2026-08-25 — Reddit public fallback (P2.5)

- Added public Reddit `.json` extraction using `raw_json=1`, top sorting, depth one, and a requested comment limit.
- Independently capped valid top-level `t1` comments, ignored nested replies and `more` placeholders, and retained post/comment provenance without credentials.
- Added bounded readable-HTML recovery through old Reddit for HTTP, timeout, redirect, request, oversized, malformed, and unusable JSON conditions.
- Rejected non-post URLs before network access and collapsed dual JSON/HTML failure into one stable non-sensitive extraction error.
- RED: `uv run pytest tests/unit/test_reddit_extraction.py -q` failed during collection because `RedditPostExtractor` did not exist.
- GREEN: all 7 focused Reddit fallback tests pass.
- Verification: 85 tests pass at 88.44% coverage; Ruff formatting/lint and strict mypy pass; `git diff --check` passes.
- Evidence: `docs/testing/phase-2-extraction.tdd.md`.
- Uncommitted paths after this update: `src/social_media_agent/errors.py`, `src/social_media_agent/models.py`, `src/social_media_agent/extraction.py`, `tests/unit/test_extraction.py`, `tests/unit/test_firecrawl.py`, `tests/unit/test_general_extraction.py`, `tests/unit/test_github_extraction.py`, `tests/unit/test_reddit_extraction.py`, `docs/PROJECT_STATUS.md`, and `docs/testing/phase-2-extraction.tdd.md`.
- Next exact action: implement P2.6 via RED tests for YouTube video-ID parsing, public metadata, transcript retrieval, and precise unavailable-transcript failures.

### 2026-08-25 — YouTube transcript fallback (P2.6)

- Added video-ID parsing for watch, short-link, Shorts, embed, and live URL forms with one canonical watch URL.
- Added bounded credential-free oEmbed metadata retrieval before transcript work.
- Adapted the synchronous `youtube-transcript-api` fetch call through a bounded worker thread and retained language/generation provenance.
- Added a precise transcript-unavailable error for disabled, empty, malformed, or timed-out transcripts rather than fabricating source content.
- RED: `uv run pytest tests/unit/test_youtube_extraction.py -q` failed during collection because the YouTube extractor, video-ID parser, and transcript-unavailable error did not exist.
- GREEN: all 10 focused YouTube fallback tests pass.
- Verification: 95 tests pass at 88.21% coverage; Ruff formatting/lint and strict mypy pass.
- Evidence: `docs/testing/phase-2-extraction.tdd.md`.
- Uncommitted paths after this update: `src/social_media_agent/errors.py`, `src/social_media_agent/models.py`, `src/social_media_agent/extraction.py`, `tests/unit/test_extraction.py`, `tests/unit/test_firecrawl.py`, `tests/unit/test_general_extraction.py`, `tests/unit/test_github_extraction.py`, `tests/unit/test_reddit_extraction.py`, `tests/unit/test_youtube_extraction.py`, `docs/PROJECT_STATUS.md`, and `docs/testing/phase-2-extraction.tdd.md`.
- Next exact action: implement P2.7 via RED tests for shared sanitization, source-text caps, provenance retention, and untrusted quoted-evidence rendering.

### 2026-08-25 — Phase 2 extraction gate complete (P2.7)

- Added one dispatcher-owned source-safety boundary that removes unsafe control characters, caps persisted content, and records original/sanitized/stored lengths plus truncation state.
- Preserved extractor and Firecrawl fallback provenance while applying shared processing to both primary and source-specific fallback results.
- Added a downstream evidence renderer that explicitly marks source material as untrusted data and block-quotes every title, author, and content line so instruction-shaped text remains quoted.
- RED: focused extraction tests failed during collection because `render_untrusted_evidence` did not exist.
- GREEN: all 13 extraction contract tests and 9 Firecrawl policy tests pass.
- Verification: 97 tests pass at 88.16% coverage; Ruff formatting/lint and strict mypy pass.
- Evidence: `docs/testing/phase-2-extraction.tdd.md`.
- Uncommitted paths after this update: `src/social_media_agent/errors.py`, `src/social_media_agent/models.py`, `src/social_media_agent/extraction.py`, `tests/unit/test_extraction.py`, `tests/unit/test_firecrawl.py`, `tests/unit/test_general_extraction.py`, `tests/unit/test_github_extraction.py`, `tests/unit/test_reddit_extraction.py`, `tests/unit/test_youtube_extraction.py`, `docs/PROJECT_STATUS.md`, and `docs/testing/phase-2-extraction.tdd.md`.
- Next exact action: implement P3.1 via RED tests for the secure local subprocess runner.

### 2026-08-25 — Secure subprocess runner (P3.1)

- Added typed command results and literal argument-array execution through asyncio's shell-free subprocess API.
- Added workspace-confined working directories and an explicit inherited/override environment allowlist for local agent authentication and runtime essentials.
- Added captured UTF-8 output, fresh process sessions, configurable timeouts, and process-group TERM/KILL escalation for timeout and task cancellation.
- RED: `uv run pytest tests/unit/test_commands.py -q` failed during collection because the command module did not exist.
- GREEN: all 5 focused runner tests pass, including real descendant cleanup.
- Verification: focused tests, Ruff formatting/lint, and strict mypy pass.
- Evidence: `docs/testing/phase-3-agents.tdd.md`.
- Uncommitted paths added by this task: `src/social_media_agent/commands.py`, `tests/unit/test_commands.py`, `src/social_media_agent/errors.py`, `docs/PROJECT_STATUS.md`, and `docs/testing/phase-3-agents.tdd.md`.
- Next exact action: implement P3.2–P3.4 through RED tests for strict draft JSON generation/repair and Codex review.

### 2026-08-25 — Phase 3 local-agent gate complete (P3.2–P3.5)

- Added strict versioned `DraftPackage` and `AgentReview` contracts with fail-closed extra-field handling.
- Added `AgyWriter` using `agy --print <prompt>` with controlled prompts that reference persisted source/brand files, exactly-one-object extraction, one file-referenced repair call, and persisted draft/raw evidence.
- Added `CodexReviewer` using a fresh `codex exec --ephemeral --sandbox read-only --output-schema ... -C ...` invocation with persisted schema/prompt/raw/review artifacts.
- Confirmed those flags against the installed Codex CLI; confirmed the installed Agy CLI supports the required `--print` interface.
- Kept command diagnostics generic and output-free, added configured-secret redaction for diagnostic text, and retained raw output only under each local post directory.
- RED: focused agent tests failed during collection because the adapters did not exist.
- GREEN: all 10 agent-adapter scenarios and all 5 command-runner scenarios pass, covering success, timeout, nonzero exit, invalid JSON, one repair, and cancellation.
- Verification: 112 tests pass at 87.55% coverage; Ruff formatting/lint, strict mypy, and `git diff --check` pass.
- Evidence: `docs/testing/phase-3-agents.tdd.md`.
- Uncommitted paths after this update: `src/social_media_agent/agents.py`, `src/social_media_agent/commands.py`, `src/social_media_agent/errors.py`, `src/social_media_agent/models.py`, `src/social_media_agent/extraction.py`, `tests/unit/test_agents.py`, `tests/unit/test_commands.py`, all Phase 2 extraction tests, `docs/PROJECT_STATUS.md`, `docs/DECISIONS.md`, `docs/testing/phase-2-extraction.tdd.md`, and `docs/testing/phase-3-agents.tdd.md`.
- Next exact action: implement P4.1 via RED tests for deterministic text validation.

### 2026-08-25 — Deterministic text validation (P4.1)

- Added strict, versioned `ValidationReport`, typed issue codes, safe suggested fixes, and deterministic metrics identifying the exact `text-validation-v1` policy.
- Added checks for whitespace-only required fields, scheme/`www`/bare-domain URLs in renderings, agent response markup in any generated field, configured forbidden phrases, identical and near-duplicate platform renderings, and clear source-language mismatch.
- Made language matching conservative: explicit natural-language metadata or a configured override wins, ambiguous detection does not fail, and GitHub's programming-language metadata is not treated as content language.
- RED: `uv run pytest tests/unit/test_validation.py -q` failed during collection because `social_media_agent.validation` did not exist.
- GREEN: all 9 focused validation tests pass.
- Verification: 121 tests pass at 87.91% coverage; Ruff formatting/lint, strict mypy, and `git diff --check` pass. Evidence: `docs/testing/phase-4-validation.tdd.md`.
- Uncommitted paths added by this task: `src/social_media_agent/validation.py`, `tests/unit/test_validation.py`, `docs/testing/phase-4-validation.tdd.md`; updated `src/social_media_agent/models.py` and `docs/PROJECT_STATUS.md`.
- Next exact action: implement P4.2 via RED tests for X/LinkedIn length and formatting policy.

### 2026-08-25 — Platform text rules (P4.2)

- Added a hard 260-Unicode-character X limit with exact 260/261 boundary coverage.
- Added advisory LinkedIn warnings outside the 600–1,300 target range and when blank-line paragraph spacing is absent; warnings do not fail an otherwise valid draft.
- Added a hard LinkedIn post limit with exact 3,000/3,001 boundary coverage. The 3,000-character limit was verified against LinkedIn's official Help documentation on 2026-08-25.
- RED: four focused platform-policy tests ran and failed because the typed length/spacing codes and checks did not exist.
- GREEN: all 13 focused validation tests pass.
- Verification: 125 tests pass at 88.08% coverage; Ruff formatting/lint, strict mypy, and `git diff --check` pass. Evidence: `docs/testing/phase-4-validation.tdd.md`.
- Uncommitted paths added by this task: `src/social_media_agent/validation.py`, `src/social_media_agent/models.py`, `tests/unit/test_validation.py`, `docs/testing/phase-4-validation.tdd.md`, and `docs/PROJECT_STATUS.md` (alongside the prior documented uncommitted work).
- Next exact action: implement P4.3 tests for the complete independent Codex semantic-review policy.

### 2026-08-25 — Independent semantic-review policy (P4.3)

- Added explicit offline coverage proving the Codex prompt evaluates grounding, relevance, brand alignment, unsupported claims, platform adaptation, concept equivalence, and image-brief relevance.
- Proved the reviewer treats source, brand, and draft files as data, does not embed untrusted source bodies in the invocation prompt, accepts a structured semantic rejection, and persists that rejection as local evidence.
- No production change was necessary: the Phase 3 reviewer already satisfied P4.3, so this task added characterization coverage rather than manufacturing a RED state.
- Verification: 11 focused agent tests pass; 126 total tests pass at 88.08% coverage; Ruff formatting/lint, strict mypy, and `git diff --check` pass.
- Evidence: `docs/testing/phase-4-validation.tdd.md`.
- Uncommitted path added by this task: `tests/unit/test_agents.py`; updated `docs/testing/phase-4-validation.tdd.md` and `docs/PROJECT_STATUS.md` alongside the prior documented uncommitted work.
- Next exact action: implement P4.4 via RED tests for the bounded validation/rewrite loop.

### 2026-08-25 — Bounded text-validation rewrite loop (P4.4)

- Added a sequential validation loop that persists the current draft and deterministic report before each next action, skips semantic review on deterministic hard failures, and invokes a fresh semantic review only for deterministic-valid drafts.
- Added a single two-rewrite budget shared across deterministic and semantic failures, with structured file-based feedback passed to a fresh Agy invocation and exact attempt-numbered draft, feedback, raw-output, report, and semantic-review artifacts.
- Added terminal success and failure evidence; exhaustion after two rewrites raises a typed local error after persisting all three validation attempts and any semantic reviews.
- Added actionable suggested fixes for X and LinkedIn hard length violations.
- RED: focused tests failed during collection because the loop and exhaustion error were absent; an incremental regression then exposed the empty platform-length suggested fix.
- GREEN: all 30 focused tests pass.
- Verification: 132 tests pass at 88.19% coverage; Ruff formatting/lint, strict mypy, and `git diff --check` pass.
- Evidence: `docs/testing/phase-4-validation.tdd.md`.
- Uncommitted paths added by this task: `tests/unit/test_validation_loop.py`; updated `src/social_media_agent/agents.py`, `src/social_media_agent/errors.py`, `src/social_media_agent/validation.py`, `tests/unit/test_agents.py`, `tests/unit/test_validation.py`, `docs/testing/phase-4-validation.tdd.md`, and `docs/PROJECT_STATUS.md` alongside prior documented work.
- Next exact action: complete P4.5 adversarial fixture coverage and Phase 4 gate evidence.

### 2026-08-25 — Phase 4 adversarial gate complete (P4.5)

- Added fixture-backed adversarial coverage for prompt-injection markup, a bare domain obfuscated with a zero-width format character, exact X and LinkedIn hard-limit violations, a fabricated performance claim, and disagreement between platform renderings.
- Hardened URL detection by removing invisible Unicode format characters in the inspection-only view; persisted draft text remains unchanged.
- Proved persisted artifacts identify writer prompt `writer-v1`, reviewer prompt `reviewer-v1`, semantic schema version 1, and deterministic policy `text-validation-v1`.
- RED: the zero-width-hidden-domain fixture bypassed the original URL regex for the intended reason.
- GREEN: all 36 focused Phase 4 tests pass.
- Verification: 138 tests pass at 88.21% coverage; Ruff formatting/lint, strict mypy, and `git diff --check` pass.
- Evidence: `docs/testing/phase-4-validation.tdd.md`.
- Uncommitted path added by this task: `tests/fixtures/validation/adversarial.json`; updated `src/social_media_agent/validation.py`, `tests/unit/test_validation.py`, `tests/unit/test_agents.py`, `tests/unit/test_validation_loop.py`, `docs/testing/phase-4-validation.tdd.md`, and `docs/PROJECT_STATUS.md` alongside prior documented work.
- Next exact action: implement P5.1 via RED tests for the image-generation production schema.

### 2026-08-25 — Mandatory Codex image gate complete (P5.1–P5.5)

- Added strict versioned image request, generation-result, file-metadata, semantic-review, and final-artifact contracts.
- Added the imagegen production prompt with a 1536x1024 editorial technical illustration default and explicit no-text, no-logo/trademark, and no-watermark constraints.
- Added fresh workspace-write Codex generation using `$imagegen`, exact project-local copy requirements, a 15-minute timeout, strict structured output, and attempt-specific local evidence.
- Added confinement, symlink, existence, nonzero-size, decodability, PNG, exact-dimension, and SHA-256 verification.
- Added a fresh read-only Codex review with the image attached, five fail-closed semantic criteria, targeted feedback, and up to two regenerations across local or semantic failures.
- Added immutable `ImageArtifact` persistence and resume-time integrity revalidation.
- RED: the initial suite lacked all image contracts; a contradictory semantic pass exposed a model invariant gap; the first live run exposed Codex's requirement that every output-schema property be required.
- GREEN: 14 focused mocked image tests pass. The explicitly opted-in live smoke passed in 114.46 seconds and retained a validated project-local image at `output/posts/live-smoke-8adc45482c/image.png`.
- Verification: 152 default tests pass with 1 live test skipped at 87.88% coverage; Ruff formatting/lint, strict mypy, and `git diff --check` pass.
- Evidence: `docs/testing/phase-5-images.tdd.md`.
- Uncommitted paths added by this phase: `src/social_media_agent/images.py`, `tests/unit/test_images.py`, `tests/live/test_image_generation_live.py`, and `docs/testing/phase-5-images.tdd.md`; updated `src/social_media_agent/errors.py`, `src/social_media_agent/models.py`, `pyproject.toml`, and `docs/PROJECT_STATUS.md` alongside prior documented work.
- Next exact action: implement P6.1 via RED tests for the Rich human-review screen.

### 2026-08-25 — Local human-review gate complete (P6.1–P6.5)

- Added a Rich terminal review screen showing provenance, LinkedIn and X renderings, validation warnings, and the mandatory local image path; the system viewer is launched only by an explicit action using argument-array, shell-free execution.
- Added Accept, Edit in `$EDITOR`, Regenerate text/image with persisted feedback, Open/Replace image, Skip, Reject, and Save/Quit, with exact post ID and action required for noninteractive review.
- Revalidated every human text edit deterministically, invoked a fresh semantic reviewer for material text changes, retained the semantic result for whitespace-only changes, and prevented text edits from silently invalidating the approved image brief.
- Copied replacement images atomically into the post directory and required the same exact PNG dimensions plus a fresh semantic image review before replacing the current artifact.
- Added immutable approved manifests, exact Markdown checkbox synchronization, next-pending selection evidence, and approval-preserving sync warnings.
- RED: the focused review suite failed during collection because the human-review error and module did not exist.
- GREEN: all 20 focused human-review scenarios pass.
- Verification: 172 default tests pass with 1 live test skipped at 86.51% coverage; Ruff formatting/lint, strict mypy, and `git diff --check` pass.
- Evidence: `docs/testing/phase-6-review.tdd.md`.
- Uncommitted paths added by this phase: `src/social_media_agent/review.py`, `tests/unit/test_review.py`, and `docs/testing/phase-6-review.tdd.md`; updated `src/social_media_agent/artifacts.py`, `src/social_media_agent/errors.py`, `src/social_media_agent/models.py`, `src/social_media_agent/queue.py`, `docs/DECISIONS.md`, and `docs/PROJECT_STATUS.md` alongside prior documented work.
- Next exact action: implement P7.1 via RED tests for the sequential pipeline coordinator and complete CLI commands, continuing after failed/rejected jobs while ensuring a skipped job is not selected again in the same run.

### 2026-08-25 — Sequential pipeline and CLI cutover (P7.1)

- Added the sequential coordinator and production workflow adapter that compose extraction, Agy drafting, deterministic and Codex review, Codex image generation/validation, and local human review through durable stage boundaries.
- Added `run --input`, executable `resume`, read-only `status`, `retry-failed [POST_ID]`, and `review POST_ID`, with a writer lock and cooperative signal capture around mutating CLI workflows.
- Processed queue entries strictly in Markdown order, continued after failure and rejection, retained Skip as pending without same-run reselection, and restored interrupted work at its exact operation.
- Kept failed jobs behind explicit retry rather than allowing ordinary resume to retry them implicitly.
- RED/GREEN commits: `724dc49` / `62f4f21`; retry-boundary RED/GREEN commits: `1b6f795` / `3288a1f`.
- Verification: 27 focused coordinator/state/CLI tests pass; the full pre-boundary suite passed 176 tests with 1 live skip and 83.25% coverage; Ruff formatting/lint, strict mypy, and `git diff --check` pass.
- Evidence: `docs/testing/phase-7-cutover.tdd.md`.
- Changed paths for P7.1: `src/social_media_agent/pipeline.py`, `src/social_media_agent/cli.py`, `src/social_media_agent/state.py`, `tests/unit/test_pipeline.py`, `tests/unit/test_cli.py`, `tests/unit/test_state.py`, `docs/testing/phase-7-cutover.tdd.md`, and `docs/PROJECT_STATUS.md`.
- Next exact action: implement P7.2 with a fixture-backed complete workflow using fake Firecrawl/Agy/Codex executables and a generated test PNG.

### 2026-08-25 — Offline end-to-end workflow gate (P7.2)

- Added a fixture-backed full workflow that uses primary-path fake Firecrawl evidence and real local subprocesses named `agy` and `codex`.
- The fake Codex executable generates a real 1536×1024 PNG, allowing the production path confinement, decoding, MIME, dimension, digest, and semantic contracts to run unchanged.
- Proved explicit local acceptance writes the immutable manifest and checkbox, then proved a second run invokes no agents and creates no duplicate work.
- Added an opt-in live workflow marker controlled by `SOCIAL_AGENT_LIVE_PIPELINE_URL`; it uses real extraction/Agy/Codex/image generation and stops at `human_review` without accepting for the user.
- Verification: the focused offline workflow passes and live workflow skips by default; the full gate passes 179 tests with 2 live skips at 85.64% coverage; Ruff formatting/lint, strict mypy, and `git diff --check` pass.
- GREEN checkpoint: `b50b59f`. Evidence: `docs/testing/phase-7-cutover.tdd.md`.
- Changed paths: `tests/e2e/test_local_pipeline.py`, `tests/fixtures/e2e/fake_local_agent.py`, `tests/live/test_pipeline_live.py`, `docs/testing/phase-7-cutover.tdd.md`, and `docs/PROJECT_STATUS.md`.
- Next exact action: implement P7.3 by rewriting README, environment example, and CI around the local Python CLI.

### 2026-08-25 — Local README, environment, and CI cutover (P7.3)

- Replaced the legacy setup guide with a command-first local Python guide covering `uv`, Agy/Codex readiness, optional Firecrawl/GitHub configuration, queue and brand formats, terminal review, exact resume/retry behavior, artifact inspection, safety boundaries, and offline/live testing.
- Added the canonical `.env.example` with only supported optional extraction keys and workspace path overrides.
- Replaced all Node workflow jobs with current `uv`-managed formatting, lint, strict typing, default offline coverage, and mocked end-to-end jobs; no CI job invokes live agents.
- RED/GREEN commits: `ad9f8d5` / `1c4c20b`; all 3 focused documentation contracts pass.
- Skill influence: `ecc:article-writing` kept the README anchored in executable commands and concrete artifacts, with each section serving one setup or operating task.
- Changed paths: `README.md`, `.env.example`, `.github/workflows/ci.yml`, `.github/workflows/unit-tests.yml`, `.github/workflows/integration-tests.yml`, `tests/unit/test_documentation.py`, `docs/testing/phase-7-cutover.tdd.md`, and `docs/PROJECT_STATUS.md`.
- Next exact action: run P7.4 automated acceptance and complete one manually approved live URL.

### 2026-08-25 — Automated acceptance pass; live permission blocker (P7.4)

- Passed locked dependency sync, formatting, lint, strict typing, CLI help/status, mocked end-to-end, and 182 offline tests at 85.64% coverage; Codex reports a valid ChatGPT login and Agy answers a no-tool headless prompt.
- The opted-in live run against `https://github.com/langchain-ai/social-media-agent` extracted and persisted source evidence, then failed safely at `drafting` after both Agy attempts were denied file-read permission in headless mode.
- Verified Agy's native `@file` context syntax is also correctly permission-gated as `read_file`; did not add the unsafe `--dangerously-skip-permissions` bypass.
- No image, manifest, approval, queue mutation, publication, or scheduling occurred in the failed live run.
- Delivery-gate evidence: 84 GB disk remained available; every automated quality command passed. The `ecc:delivery-gate` skill prevented treating these checks as a substitute for the still-missing live human approval.
- Blocker: the user must grant a narrow persisted Agy `read_file` rule for workspace context files and must personally decide whether to accept the resulting draft package.
- Next exact action: rerun `SOCIAL_AGENT_LIVE_PIPELINE_URL=https://github.com/langchain-ai/social-media-agent uv run pytest tests/live/test_pipeline_live.py -m live -s -q` after the permission grant, then process the retained package through explicit human review for final P7.4 evidence.

### 2026-08-26 — Phase 7 live acceptance complete (P7.4)

- Persisted narrow, exact Agy `read_file` grants for the brand and live job artifacts; no broad permission bypass was used.
- The first live source, `langchain-ai/social-media-agent`, exercised fail-closed drafting, deterministic validation, semantic rejection, bounded rewrites, and validation exhaustion without approval or publication.
- The successful live source, `astral-sh/uv` (post `30e283a9b3f70e35`), passed GitHub extraction, Agy drafting and grounded rewrite, deterministic and Codex semantic text review, real Codex image generation, image file validation, and independent image review.
- Presented the final copy and 1536×1024 PNG at `output/posts/30e283a9b3f70e35/image.png`; the user explicitly replied `accept`. The terminal review recorded `approved`, wrote `approved-manifest.json`, and checked only the matching ignored live queue item. Nothing was published or scheduled.
- The live gate exposed and fixed three production boundaries: writer prompts now forbid unlisted workspace reads, require integer `schema_version = 1`, and emit Codex-compatible strict review schemas. It also exposed and fixed a CLI status test that depended on a clean real workspace.
- Final verification: `uv sync --locked --all-groups`; Ruff format and lint pass; strict mypy passes for 19 source files; mocked end-to-end passes; 182 offline tests pass with 2 live tests deselected and 85.65% coverage; `git diff --check` passes.
- Skill influence: `ecc:delivery-gate` kept the live human approval and persisted artifacts as required evidence rather than treating automated checks alone as completion.
- Changed paths in the final hardening checkpoint: `src/social_media_agent/agents.py`, `tests/unit/test_agents.py`, `tests/unit/test_cli.py`, `docs/testing/phase-7-cutover.tdd.md`, and `docs/PROJECT_STATUS.md`.
- Next exact action: begin P8.1 only after rereading the Phase 8 removal list and verifying the dirty worktree against Git history.

### 2026-08-26 — Legacy executable surface removed (P8.1)

- Removed the tracked TypeScript application under `src/agents`, `src/clients`, `src/evals`, `src/tests`, and `src/utils`, while retaining `src/social_media_agent` and all Python tests/fixtures.
- Removed Node scripts and root Node/Jest/ESLint/TypeScript manifests and lockfiles, the root LangGraph manifest, `memory-v2`, `slack-messaging`, and generated legacy assets under `static`.
- Removed the obsolete Node-only Docker ignore file and pruned npm plus removed-memory-project entries from Dependabot; retained `uv` and GitHub Actions updates.
- Added `tests/unit/test_legacy_removal.py` to prevent the removed runtime/configuration surface from returning and to keep dependency automation aligned with retained ecosystems.
- Removal was performed with `git rm`, so every deleted tracked path remains recoverable from Git history. No dirty Python replacement path was overwritten or removed.
- Verification: the focused removal boundary passes; repository inventory finds no TypeScript/JavaScript, Node manifest/lockfile, or LangGraph manifest; Ruff format/lint and strict mypy pass; mocked end-to-end passes; 184 offline tests pass with 2 live tests deselected and 85.65% coverage.
- Skill influence: `ecc:git-workflow` kept the deletion recoverable and isolated from the pre-existing dirty worktree. `ecc:repo-scan` and `ecc:config-gc` were inspected but not applied because one is only an external-skill installer and the other explicitly excludes project-source cleanup.
- Changed paths: deleted legacy roots and manifests listed above; updated `.github/dependabot.yml`; added `tests/unit/test_legacy_removal.py`; updated `docs/testing/phase-8-removal.tdd.md` and `docs/PROJECT_STATUS.md`.
- Next exact action: P8.2 documentation/configuration cleanup, beginning with an `rg` inventory of the removed hosted and workflow concepts.

### 2026-08-26 — Legacy operational documentation/config removed (P8.2)

- Removed `FEATURES.md`, which documented only deleted LangGraph graph flows and TypeScript APIs.
- Removed `.env.full.example` and `.env.quickstart.example`, which requested hosted tracing/model, social authentication, scheduling, Slack, Supabase, and LangGraph settings unsupported by the local product.
- Removed legacy VS Code spelling settings and the Jest-only codespell ignore file.
- Reduced `.gitignore` to retained Python build/test caches, local environment and credentials, generated pipeline output, notebooks, and OS metadata; removed Node, Yarn, Turbo, ESLint, deleted-source, and LangGraph API entries.
- Added a documentation/config regression proving obsolete files stay absent and retained `.gitignore` rules remain Python-local.
- Preserved the README and AGENTS safety statements that the product does not publish or schedule; those are active negative boundaries, not legacy feature promises. Preserved governed planning, decision, status, and test-evidence history.
- Verification: 6 focused documentation/removal tests pass; operational config search finds none of the removed hosted-service/workflow concepts; Ruff format/lint and strict mypy pass; mocked end-to-end passes; 185 offline tests pass with 2 live tests deselected and 85.65% coverage.
- Skill influence: `ecc:search-first` kept the cleanup inventory-based and confirmed no dependency or external research was needed.
- Changed paths: deleted `FEATURES.md`, `.env.full.example`, `.env.quickstart.example`, `.vscode/settings.json`, and `.codespellignore`; updated `.gitignore`, `tests/unit/test_documentation.py`, `docs/testing/phase-8-removal.tdd.md`, and `docs/PROJECT_STATUS.md`.
- Next exact action: P8.3 retained-surface audit against the plan's allowlist.

### 2026-08-26 — Minimal retained surface verified (P8.3)

- Removed the final nonessential legacy-era root configuration, `.editorconfig`; it contained only JavaScript/JSON/YAML formatting rules and no local Python behavior.
- Added a tracked-root allowlist regression. The retained root is exactly the local Python package and metadata, `uv` lockfile, Python GitHub CI/dependency automation, tests/fixtures, content templates, output placeholder, licensing, README, and governed documents.
- The audit preserves historical migration evidence under `docs/` and active operational safety constraints under `AGENTS.md` and `README.md`.
- Verification: 3 focused legacy-removal tests pass; Ruff format/lint and strict mypy pass; mocked end-to-end passes; 186 offline tests pass with 2 live tests deselected and 85.65% coverage.
- Changed paths: deleted `.editorconfig`; updated `tests/unit/test_legacy_removal.py`, `docs/testing/phase-8-removal.tdd.md`, and `docs/PROJECT_STATUS.md`.
- Next exact action: P8.4 durable removal record.

### 2026-08-26 — OpenViking skill-discovery policy

- Updated `AGENTS.md` at the user's request: every prompt execution must query the OpenViking skill catalog, including skills not locally injected, then read and apply each relevant selected skill before task actions.
- Verification: `git diff --check` passes. No product code, pipeline behavior, approval state, publication, or scheduling behavior changed.
- Changed paths: `AGENTS.md` and `docs/PROJECT_STATUS.md`.
- Next exact action: P8.4 durable removal record.

### 2026-08-26 — Mandatory ECC TDD policy

- Updated `AGENTS.md` at the user's request so every code implementation conversation loads and applies OpenViking's `tdd-workflow` plus the task-appropriate ECC operation skill before implementation begins.
- The policy requires an executed intended RED test before production-code changes, then minimal GREEN, green refactoring, coverage verification, factual evidence, and the ECC security-review path when its trigger areas are touched. It also makes clear that Codex must preserve the workflow when Claude slash commands or named-agent dispatch are unavailable.
- Verification: reviewed the current OpenViking `tdd-workflow` and `orch-pipeline` instructions; `git diff --check` passes. No product code, pipeline behavior, approval state, publication, or scheduling behavior changed.
- Changed paths: `AGENTS.md` and `docs/PROJECT_STATUS.md`.
- Next exact action: P8.4 durable removal record.

### 2026-08-26 — Live non-Git-workspace Codex fix

- The opt-in live pipeline test uses an isolated temporary workspace, which is intentionally not a Git checkout. Its first run against `Anil-matcha/ai-creator-academy` reached Codex review but failed because Codex's default Git-repository guard rejected that workspace.
- Added Codex's explicit `--skip-git-repo-check` only to the local text reviewer, image generator, and image reviewer invocations. Their existing `read-only` or `workspace-write` sandbox choices, literal argument arrays, and workspace-confined paths remain unchanged.
- Added unit-contract coverage for the flag on all three Codex command shapes. Focused verification: 28 agent/image tests pass; Ruff format/lint, strict mypy, and `git diff --check` pass.
- The rerun against `https://github.com/Anil-matcha/ai-creator-academy.git` completed the formerly blocked Codex text review. It then failed safely at bounded text validation after legitimate semantic grounding feedback; no image, approval, checkbox update, publication, or scheduling occurred.
- Changed paths: `src/social_media_agent/agents.py`, `src/social_media_agent/images.py`, `tests/unit/test_agents.py`, `tests/unit/test_images.py`, and `docs/PROJECT_STATUS.md`.
- Next exact action: P8.4 durable removal record; when performing a live smoke run, choose source material whose generated draft can satisfy the bounded grounding-review contract.

### 2026-08-26 — Live smoke reaches human review

- The opt-in live workflow against `https://github.com/rebelytics/one-skill-to-rule-them-all.git` completed GitHub extraction, Agy drafting plus one bounded rewrite, deterministic validation, independent Codex text review, Codex image generation, local PNG validation, and independent image review.
- The isolated live workspace reached `human_review` with a validated local image. The explicit save/quit action preserved the reviewable package; it did not approve the draft, update a queue checkbox, publish, or schedule anything.
- Evidence: `/tmp/pytest-of-naoufel/pytest-19/test_live_url_reaches_local_hu0/output/state.json` records `human_review`; the post artifact directory contains the draft, validation evidence, semantic reviews, `image.png`, and `image-artifact.json`.
- No repository product-code change was made by this smoke run. Next exact action remains P8.4 durable removal record.

### 2026-08-26 — Durable legacy-removal record complete (P8.4)

- Added D010 to make the local Python CLI the sole product implementation and to record the removed hosted/workflow concepts and their local replacements.
- Expanded this delete-zone so future work cannot mistake removed publishing, hosted orchestration, social integrations, or auxiliary workflow features for dormant supported scope.
- No product code or test behavior changed; the remaining task is P8.5, the required fresh-environment acceptance gate.
- Changed paths: `docs/DECISIONS.md`, `docs/PROJECT_STATUS.md`, and `docs/testing/phase-8-removal.tdd.md`.
- Next exact action: create an isolated temporary `uv` environment, run the locked full offline gate, and record exact results for P8.5.

### 2026-08-26 — Final fresh-environment acceptance gate complete (P8.5)

- Created a new isolated environment at `/tmp/social-agent-phase8.tGNlPG/.venv` with `uv sync --locked --all-groups`, while hosted-model, hosted-service, social-platform, and extraction credentials were unset.
- RED/GREEN: the legacy-root regression initially failed because this copied checkout has broken parent-worktree Git metadata. It now uses the exact Git tracked-root allowlist when Git works and an exact filesystem-root allowlist with named runtime entries otherwise; focused evidence is 7 passing documentation/removal tests.
- Final verification: `uv run ruff format --check src tests`; `uv run ruff check src tests`; and `uv run mypy` all pass. The mocked end-to-end test passes. `uv run pytest -m "not live" --cov=social_media_agent --cov-report=term-missing -q` reports 186 passed, 2 deselected, and 85.65% coverage.
- `uv run social-agent --help` and `uv run social-agent status` run successfully without the unset credentials. Inventory finds no TypeScript/JavaScript or Node/LangGraph manifest/lockfile, and supported configuration/docs contain no LangGraph, LangSmith, Supabase, hosted-model SDK, Node, or database requirement.
- The Phase 8 gate is complete. The only operational follow-up is repairing the external Git worktree metadata before a future Git operation; no product behavior is blocked.
- Changed paths: `docs/DECISIONS.md`, `docs/PROJECT_STATUS.md`, `docs/testing/phase-8-removal.tdd.md`, and `tests/unit/test_legacy_removal.py`.
- Next exact action: none for this implementation plan.

## Blockers and risks

### 2026-08-28 — Packaged local operator console

- Replaced the temporary inline browser page with a Vite-built React and TypeScript
  console packaged inside the Python wheel. `social-agent workspace` remains a
  loopback-only Python command and serves only build-manifest-declared assets.
- Added stable `/api/v1/` snapshot and command aliases, strict CSP, active-candidate
  deletion with a source-content-free local event, and the five local console pages.
- Verification: focused workspace tests, Python Ruff and strict mypy, frontend
  typecheck and production build, and the full offline Python suite were run.

- The installed Agy CLI now exposes `--json-schema`, but Phase 3 intentionally retains independent Pydantic validation and the approved one-repair contract; adopting CLI-side schema enforcement later should preserve that fail-closed boundary.
- Built-in `$imagegen` output begins under Codex-managed storage; the invoked Codex session must copy the accepted asset into the post directory, and Python must verify it.
- Firecrawl and live agent behavior are external; default tests must remain deterministic and offline.

## Delete-zone

The Phase 7 acceptance gate has passed. Remove the legacy TypeScript source, Node lock/configuration, LangGraph manifests, Slack/memory subprojects, and legacy tests only within the ordered Phase 8 tasks.

After Phase 7, the Phase 8 removal list in `docs/IMPLEMENTATION_PLAN.md` is intentional. The local replacement is: Markdown queue; bounded general/GitHub/Reddit/YouTube extraction; Agy drafting; deterministic and independent Codex review; mandatory local Codex image generation; terminal human approval; and an immutable local manifest. Reintroducing LangGraph Platform, LangSmith, Supabase image storage, hosted LLM SDK inference, Arcade, Slack, social authentication, scheduling, publication, cron, curation, repurposing, reflection, or image discovery requires a new explicit scope decision recorded in `docs/DECISIONS.md`, corresponding tests, and a new acceptance gate.
