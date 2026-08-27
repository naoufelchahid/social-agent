# Phase 4 Text Validation — TDD Evidence

Source plan: `docs/IMPLEMENTATION_PLAN.md`, tasks P4.1–P4.5.

## Completed guarantees

| Task | Guarantee | Evidence | Result |
|---|---|---|---|
| P4.1 | Deterministic validation produces a strict versioned report with typed findings and metrics; rejects blank required fields, URLs/domains in platform copy, agent markup, configured forbidden phrases, identical or near-duplicate renderings, and clear source-language mismatches | `tests/unit/test_validation.py` | PASS |
| P4.1 | Language checks prefer explicit natural-language metadata, allow an output-language override, remain non-failing when detection is ambiguous, and do not confuse GitHub programming-language metadata or names such as `Next.js` with language/URL violations | `tests/unit/test_validation.py` | PASS |
| P4.2 | X accepts at most 260 Unicode code points, including an exact-boundary check | `tests/unit/test_validation.py` | PASS |
| P4.2 | LinkedIn's 600–1,300 character target and blank-line paragraph spacing produce advisory warnings without failing an otherwise valid draft | `tests/unit/test_validation.py` | PASS |
| P4.2 | LinkedIn accepts exactly 3,000 characters and hard-fails at 3,001 characters | `tests/unit/test_validation.py` | PASS |
| P4.3 | A fresh read-only Codex review references persisted untrusted evidence, brand context, and draft data; explicitly evaluates all seven semantic criteria; validates a strict response; and persists semantic rejection evidence | `tests/unit/test_agents.py` | PASS |
| P4.4 | Deterministic hard failures bypass semantic review and provide structured file-based evidence to a fresh Agy rewrite | `tests/unit/test_validation_loop.py`, `tests/unit/test_agents.py` | PASS |
| P4.4 | One shared budget permits at most two rewrites across deterministic and semantic failures, succeeds when a corrected draft passes, and persists every attempt plus a terminal success/failure record | `tests/unit/test_validation_loop.py` | PASS |
| P4.4 | Rewrite feedback contains actionable suggested fixes for X and LinkedIn hard length failures | `tests/unit/test_validation.py` | PASS |
| P4.5 | Fixture-backed adversarial cases reject prompt markup, zero-width-obfuscated domains, X/LinkedIn hard length violations, fabricated claims, and platform disagreement | `tests/fixtures/validation/adversarial.json`, `tests/unit/test_validation.py`, `tests/unit/test_agents.py` | PASS |
| P4.5 | Persisted writer/reviewer prompts, semantic schemas, and deterministic reports identify `writer-v1`, `reviewer-v1`, schema version 1, and `text-validation-v1` | `tests/unit/test_agents.py`, `tests/unit/test_validation_loop.py` | PASS |

## RED/GREEN checkpoint

- RED: `uv run pytest tests/unit/test_validation.py -q` failed during collection because `social_media_agent.validation` did not exist.
- GREEN: all 9 focused deterministic-validation tests pass.
- P4.2 RED: the four new platform-policy tests ran and failed because the typed length/spacing codes and checks did not exist.
- P4.2 GREEN: all 13 focused deterministic-validation tests pass.
- P4.3 characterization: the existing Phase 3 reviewer satisfied the full P4.3 policy without a production change; all 11 focused agent tests pass, including semantic rejection for disagreement and an unsupported claim.
- P4.4 RED: focused tests failed during collection because the bounded loop and exhaustion error did not exist; a later focused regression failed because platform-length errors produced an empty suggested action.
- P4.4 GREEN: all 30 focused validation, loop, and agent tests pass.
- P4.5 RED: the zero-width-hidden-domain fixture ran and failed because URL inspection preserved invisible Unicode format characters.
- P4.5 GREEN: all 36 focused Phase 4 validation, loop, agent, and adversarial-fixture tests pass.

## Current quality evidence

```text
uv run pytest --cov=social_media_agent --cov-report=term-missing
138 passed; 88.21% total coverage

uv run ruff format --check src tests
36 files already formatted

uv run ruff check src tests
All checks passed

uv run mypy
Success: no issues found in 16 source files
```

## Current phase boundary

P4.1–P4.5 and the Phase 4 gate are complete. The next governed task is P5.1, converting a validated image brief into the versioned image-generation production schema.
