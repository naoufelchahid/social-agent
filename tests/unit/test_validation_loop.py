"""Tests for the bounded deterministic and semantic text-validation loop."""

import json
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from social_media_agent.artifacts import ArtifactRepository
from social_media_agent.errors import TextValidationExhaustedError
from social_media_agent.models import (
    AgentReview,
    DraftPackage,
    ExtractedSource,
    ExtractionMethod,
    SourceType,
)
from social_media_agent.validation import validate_with_rewrites


def _draft(
    *, x: str = "A concise rendering.", concept: str = "One concept"
) -> DraftPackage:
    return DraftPackage(
        concept=concept,
        linkedin="A professional rendering.\n\nWith useful context.",
        x=x,
        image_brief="Editorial illustration of a sequential workflow.",
    )


def _source() -> ExtractedSource:
    return ExtractedSource(
        canonical_url="https://example.com/article",
        source_type=SourceType.GENERAL,
        title="Workflow",
        content="Evidence about a sequential local workflow.",
        metadata={},
        extraction_method=ExtractionMethod.GENERAL_HTTP,
    )


def _review(*, passed: bool) -> AgentReview:
    return AgentReview(
        passed=passed,
        summary="Grounded." if passed else "The renderings disagree.",
        errors=[] if passed else ["The X rendering adds an unsupported claim."],
        suggested_fix=None if passed else "Remove the unsupported claim.",
    )


@dataclass
class FakeRewriter:
    outcomes: list[DraftPackage]
    calls: list[dict[str, object]] = field(default_factory=list)

    async def rewrite(self, **kwargs: object) -> DraftPackage:
        self.calls.append(kwargs)
        return self.outcomes.pop(0)


@dataclass
class FakeReviewer:
    outcomes: list[AgentReview]
    calls: list[dict[str, object]] = field(default_factory=list)

    async def review(self, **kwargs: object) -> AgentReview:
        self.calls.append(kwargs)
        return self.outcomes.pop(0)


def _context(tmp_path: Path) -> tuple[Path, Path, ArtifactRepository]:
    source_path = tmp_path / "output/posts/post-1/source-evidence.txt"
    source_path.parent.mkdir(parents=True)
    source_path.write_text("quoted source")
    brand_path = tmp_path / "content/brand.md"
    brand_path.parent.mkdir(parents=True)
    brand_path.write_text("brand context")
    return (
        source_path,
        brand_path,
        ArtifactRepository(tmp_path, tmp_path / "output"),
    )


@pytest.mark.asyncio
async def test_deterministic_failure_rewrites_before_semantic_review(
    tmp_path: Path,
) -> None:
    source_path, brand_path, artifacts = _context(tmp_path)
    rewriter = FakeRewriter([_draft(concept="Rewritten concept")])
    reviewer = FakeReviewer([_review(passed=True)])

    outcome = await validate_with_rewrites(
        post_id="post-1",
        draft=_draft(x="x" * 261),
        source=_source(),
        source_path=source_path,
        brand_path=brand_path,
        artifacts=artifacts,
        rewriter=rewriter,
        reviewer=reviewer,
    )

    assert outcome.passed is True
    assert outcome.rewrite_count == 1
    assert outcome.draft.concept == "Rewritten concept"
    assert len(reviewer.calls) == 1
    feedback_path = rewriter.calls[0]["feedback_path"]
    feedback = json.loads(Path(feedback_path).read_text())  # type: ignore[arg-type]
    assert feedback["rewrite_number"] == 1
    assert feedback["deterministic_report"]["passed"] is False
    assert feedback["deterministic_report"]["errors"][0]["code"] == "x_length"
    assert feedback["semantic_review"] is None
    success = json.loads(
        (tmp_path / "output/posts/post-1/text-validation-success.json").read_text()
    )
    final_report = json.loads(
        (tmp_path / "output/posts/post-1" / success["deterministic_report"]).read_text()
    )
    assert final_report["schema_version"] == 1
    assert final_report["policy_version"] == "text-validation-v1"


@pytest.mark.asyncio
async def test_two_rewrites_are_shared_across_deterministic_and_semantic_failures(
    tmp_path: Path,
) -> None:
    source_path, brand_path, artifacts = _context(tmp_path)
    rewriter = FakeRewriter(
        [_draft(concept="First rewrite"), _draft(concept="Second rewrite")]
    )
    reviewer = FakeReviewer([_review(passed=False), _review(passed=True)])

    outcome = await validate_with_rewrites(
        post_id="post-1",
        draft=_draft(x="x" * 261),
        source=_source(),
        source_path=source_path,
        brand_path=brand_path,
        artifacts=artifacts,
        rewriter=rewriter,
        reviewer=reviewer,
    )

    assert outcome.passed is True
    assert outcome.rewrite_count == 2
    assert outcome.draft.concept == "Second rewrite"
    assert len(rewriter.calls) == 2
    assert len(reviewer.calls) == 2
    second_feedback = json.loads(
        Path(rewriter.calls[1]["feedback_path"]).read_text()  # type: ignore[arg-type]
    )
    assert second_feedback["deterministic_report"]["passed"] is True
    assert second_feedback["semantic_review"]["passed"] is False


@pytest.mark.asyncio
async def test_exhaustion_persists_all_attempt_evidence_and_fails(
    tmp_path: Path,
) -> None:
    source_path, brand_path, artifacts = _context(tmp_path)
    invalid = _draft(x="x" * 261)
    rewriter = FakeRewriter([invalid, invalid])
    reviewer = FakeReviewer([])

    with pytest.raises(TextValidationExhaustedError, match="two rewrites"):
        await validate_with_rewrites(
            post_id="post-1",
            draft=invalid,
            source=_source(),
            source_path=source_path,
            brand_path=brand_path,
            artifacts=artifacts,
            rewriter=rewriter,
            reviewer=reviewer,
        )

    assert len(rewriter.calls) == 2
    assert reviewer.calls == []
    post_dir = tmp_path / "output/posts/post-1"
    failure = json.loads((post_dir / "text-validation-failure.json").read_text())
    assert failure == {
        "schema_version": 1,
        "passed": False,
        "rewrite_count": 2,
        "failed_stage": "deterministic",
        "attempts": [
            "text-validation-attempt-1.json",
            "text-validation-attempt-2.json",
            "text-validation-attempt-3.json",
        ],
    }
    assert all(
        json.loads((post_dir / name).read_text())["passed"] is False
        for name in failure["attempts"]
    )


@pytest.mark.asyncio
async def test_semantic_exhaustion_persists_every_review(tmp_path: Path) -> None:
    source_path, brand_path, artifacts = _context(tmp_path)
    rewriter = FakeRewriter([_draft(), _draft()])
    reviewer = FakeReviewer(
        [_review(passed=False), _review(passed=False), _review(passed=False)]
    )

    with pytest.raises(TextValidationExhaustedError, match="two rewrites"):
        await validate_with_rewrites(
            post_id="post-1",
            draft=_draft(),
            source=_source(),
            source_path=source_path,
            brand_path=brand_path,
            artifacts=artifacts,
            rewriter=rewriter,
            reviewer=reviewer,
        )

    post_dir = tmp_path / "output/posts/post-1"
    failure = json.loads((post_dir / "text-validation-failure.json").read_text())
    assert failure["failed_stage"] == "semantic"
    assert len(reviewer.calls) == 3
    assert [
        json.loads((post_dir / f"semantic-review-attempt-{attempt}.json").read_text())[
            "passed"
        ]
        for attempt in (1, 2, 3)
    ] == [False, False, False]
