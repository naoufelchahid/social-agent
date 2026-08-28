"""Tests for the bounded local research-intake handoff."""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast

import pytest

from social_media_agent.research_intake import (
    CandidateStatus,
    ResearchCandidate,
    ResearchCandidateStore,
    ResearchIntakeService,
    promote_candidate,
)


def _candidate(
    *, status: CandidateStatus = CandidateStatus.ACTIVE
) -> ResearchCandidate:
    return ResearchCandidate(
        candidate_id="candidate-001",
        canonical_url="https://example.com/ai-workflow?utm_source=newsletter",
        source_family="publication",
        title="A grounded AI workflow article",
        published_at=datetime(2026, 8, 20, tzinfo=UTC),
        discovered_at=datetime(2026, 8, 28, tzinfo=UTC),
        evidence_notes=["The article describes a documented approval workflow."],
        angle="Prioriser un processus avant de choisir un outil IA.",
        professional_use_case="Aider un COO à choisir un premier workflow à auditer.",
        audience="Dirigeants de PME et ETI francophones",
        score=8,
        score_rationale="Pratique, récent et directement lié à une décision métier.",
        status=status,
    )


def test_candidate_store_round_trips_human_readable_records(tmp_path: Path) -> None:
    """The operator can inspect a persisted candidate register without JSON files."""
    path = tmp_path / "content" / "candidates.md"
    store = ResearchCandidateStore(path)

    store.save([_candidate()])

    restored = store.load()

    assert restored == [_candidate()]
    contents = path.read_text(encoding="utf-8")
    assert "# Research candidates" in contents
    assert "Prioriser un processus" in contents
    assert "candidate-001" in contents


def test_promote_candidate_appends_normalized_url_and_context(tmp_path: Path) -> None:
    """Promotion is the only handoff from the candidate register to the queue."""
    candidates_path = tmp_path / "content" / "candidates.md"
    queue_path = tmp_path / "content" / "urls.md"
    ResearchCandidateStore(candidates_path).save([_candidate()])
    queue_path.parent.mkdir(parents=True, exist_ok=True)
    queue_path.write_text("# Social media queue\n", encoding="utf-8")

    promoted = promote_candidate(
        candidate_id="candidate-001",
        candidates_path=candidates_path,
        queue_path=queue_path,
        now=datetime(2026, 8, 28, tzinfo=UTC),
    )

    assert promoted.normalized_url() == "https://example.com/ai-workflow"
    assert "- [ ] https://example.com/ai-workflow" in queue_path.read_text()
    assert "  - Angle: Prioriser un processus" in queue_path.read_text()
    assert "  - Audience: Dirigeants de PME" in queue_path.read_text()
    assert (
        ResearchCandidateStore(candidates_path).load()[0].status
        is CandidateStatus.PROMOTED
    )


def test_promote_candidate_rejects_expired_record(tmp_path: Path) -> None:
    """Expired candidates remain auditable but cannot enter the runnable queue."""
    candidates_path = tmp_path / "content" / "candidates.md"
    queue_path = tmp_path / "content" / "urls.md"
    candidate = _candidate()
    expired = candidate.model_copy(
        update={"discovered_at": datetime(2026, 7, 1, tzinfo=UTC)}
    )
    ResearchCandidateStore(candidates_path).save([expired])

    with pytest.raises(ValueError, match="expired"):
        promote_candidate(
            candidate_id=expired.candidate_id,
            candidates_path=candidates_path,
            queue_path=queue_path,
            now=datetime(2026, 8, 28, tzinfo=UTC),
        )


def test_candidate_expiry_is_thirty_days() -> None:
    """A candidate becomes expired after the agreed thirty-day review window."""
    candidate = _candidate()

    assert (
        candidate.is_expired_at(candidate.discovered_at + timedelta(days=29)) is False
    )
    assert candidate.is_expired_at(candidate.discovered_at + timedelta(days=30)) is True


@pytest.mark.asyncio
async def test_intake_retains_only_new_active_candidates_within_caps(
    tmp_path: Path,
) -> None:
    """The evaluator proposes findings; deterministic local code owns the register."""
    candidates_path = tmp_path / "content" / "candidates.md"
    existing = _candidate()
    ResearchCandidateStore(candidates_path).save([existing])
    proposed = _candidate().model_copy(
        update={
            "candidate_id": "candidate-002",
            "canonical_url": "https://example.com/governance",
            "title": "Governance evidence",
        }
    )

    class Evaluator:
        async def evaluate(self) -> list[ResearchCandidate]:
            return [existing, proposed]

    service = ResearchIntakeService(
        candidates_path=candidates_path,
        evaluator=cast(object, Evaluator()),
        now=lambda: datetime(2026, 8, 28, tzinfo=UTC),
    )

    result = await service.run()

    assert result.added_candidate_ids == ("candidate-002",)
    assert [
        candidate.candidate_id
        for candidate in ResearchCandidateStore(candidates_path).load()
    ] == [
        "candidate-001",
        "candidate-002",
    ]
