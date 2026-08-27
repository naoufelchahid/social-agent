# Phase 2 Firecrawl-first Extraction — TDD Evidence

Source plan: `docs/IMPLEMENTATION_PLAN.md`, tasks P2.1–P2.7.

## Completed guarantees

| Task | Guarantee | Evidence | Result |
|---|---|---|---|
| P2.1 | General, GitHub, Reddit, and YouTube URLs classify by exact host; every backend implements one async protocol; requests are canonical; extracted evidence has versioned provenance; configured Firecrawl is selected before a source fallback | `tests/unit/test_extraction.py` | PASS |
| P2.2 | Configured Firecrawl maps usable Markdown into source evidence; missing keys, timeouts, rate limits, malformed responses, unusable content, and service errors invoke the matching fallback with a stable non-sensitive reason | `tests/unit/test_firecrawl.py` | PASS |
| P2.3 | General pages use bounded redirect-following and streamed response reads; timeouts, HTTP failures, oversized bodies, and pages without readable evidence fail safely; Trafilatura retains readable content and provenance | `tests/unit/test_general_extraction.py` | PASS |
| P2.4 | GitHub fallback reads repository metadata, raw README, and an allowlisted bounded set of small root manifests through REST; public access omits authentication, optional bearer tokens never enter artifacts, missing optional content is accepted, and no repository is cloned | `tests/unit/test_github_extraction.py` | PASS |
| P2.5 | Reddit fallback requests public raw JSON with top/depth/limit bounds, independently caps and retains only top-level `t1` comments, ignores nested replies and `more` placeholders, and uses bounded readable old-Reddit HTML for unavailable, malformed, or unusable JSON | `tests/unit/test_reddit_extraction.py` | PASS |
| P2.6 | YouTube fallback parses watch, short, Shorts, embed, and live video IDs; validates credential-free oEmbed metadata; fetches transcript snippets through the current library adapter; and fails explicitly when no usable public transcript exists | `tests/unit/test_youtube_extraction.py` | PASS |
| P2.7 | Dispatcher sanitizes control characters, caps persisted source content, records processing metrics without replacing provenance, and renders every source field as explicitly quoted untrusted evidence for downstream file prompts | `tests/unit/test_extraction.py` | PASS |

## RED/GREEN checkpoints

- P2.1 RED: `uv run pytest tests/unit/test_extraction.py -q` failed at collection because `ExtractionError` and the extraction contract did not exist.
- P2.1 GREEN: all 11 focused tests passed after adding the models, protocol, classifier, and dispatcher.
- P2.2 RED: `uv run pytest tests/unit/test_firecrawl.py -q` failed at collection because `FirecrawlExtractor` and its typed fallback error did not exist.
- P2.2 GREEN: all 9 focused Firecrawl tests and all 20 extraction tests passed.
- P2.3 RED: `uv run pytest tests/unit/test_general_extraction.py -q` failed at collection because `GeneralPageExtractor` did not exist.
- P2.3 GREEN: all 7 focused general-page fallback tests passed.
- P2.4 RED: `uv run pytest tests/unit/test_github_extraction.py -q` failed at collection because `GitHubRepositoryExtractor` did not exist.
- P2.4 GREEN: all 7 focused GitHub fallback tests passed.
- P2.5 RED: `uv run pytest tests/unit/test_reddit_extraction.py -q` failed at collection because `RedditPostExtractor` did not exist.
- P2.5 GREEN: all 7 focused Reddit fallback tests passed.
- P2.6 RED: `uv run pytest tests/unit/test_youtube_extraction.py -q` failed at collection because the YouTube extractor, video-ID parser, and transcript-unavailable error did not exist.
- P2.6 GREEN: all 10 focused YouTube fallback tests passed.
- P2.7 RED: focused extraction tests failed at collection because the shared untrusted-evidence renderer did not exist.
- P2.7 GREEN: all 13 focused extraction contract tests and 9 Firecrawl policy tests passed.

## Current quality evidence

```text
uv run pytest --cov=social_media_agent --cov-report=term-missing
97 passed; 88.16% total coverage

uv run ruff format --check src tests
29 files already formatted

uv run ruff check src tests
All checks passed

uv run mypy
Success: no issues found in 13 source files
```

## Current phase boundary

P2.1–P2.7 and the Phase 2 extraction gate are complete. Phase 3 begins with the secure local subprocess runner in P3.1.
