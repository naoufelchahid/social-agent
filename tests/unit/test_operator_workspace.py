"""Tests for the local web operator-workspace application seam."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from social_media_agent.config import Settings
from social_media_agent.models import JobStage, PipelineState
from social_media_agent.operator_workspace import OperatorWorkspace
from social_media_agent.research_intake import (
    CandidateStatus,
    ResearchCandidate,
    ResearchCandidateStore,
)
from social_media_agent.state import StateStore, add_job, transition_job


def _candidate() -> ResearchCandidate:
    return ResearchCandidate.model_validate(
        {
            "candidate_id": "candidate-001",
            "canonical_url": "https://example.com/article",
            "source_family": "publication",
            "title": "Useful source",
            "discovered_at": datetime(2026, 8, 28, tzinfo=UTC),
            "evidence_notes": ["Grounded evidence."],
            "angle": "A deliberate angle.",
            "professional_use_case": "A concrete use case.",
            "audience": "Operators",
            "score": 8,
            "score_rationale": "Useful.",
        }
    )


def test_snapshot_exposes_read_only_state_and_candidate_portfolio(
    tmp_path: Path,
) -> None:
    """The workspace collects persisted facts without exposing file paths or secrets."""
    settings = Settings.from_workspace(tmp_path)
    state = add_job(PipelineState(), "post-1", "https://example.com/post")
    state = transition_job(state, "post-1", JobStage.EXTRACTING)
    StateStore(settings.state_path).save(state)
    ResearchCandidateStore(settings.candidates_path).save([_candidate()])

    snapshot = OperatorWorkspace(settings).snapshot()

    assert snapshot["active_post_id"] == "post-1"
    assert snapshot["posts"][0]["stage"] == "extracting"
    assert snapshot["candidates"][0]["candidate_id"] == "candidate-001"
    assert snapshot["oauth"] == {"x_configured": False, "linkedin_configured": False}
    assert str(tmp_path) not in str(snapshot)


def test_snapshot_filters_candidates_by_lifecycle(tmp_path: Path) -> None:
    """Portfolio filtering retains audit history but focuses the requested lifecycle."""
    settings = Settings.from_workspace(tmp_path)
    promoted = _candidate().model_copy(
        update={"candidate_id": "candidate-002", "status": CandidateStatus.PROMOTED}
    )
    ResearchCandidateStore(settings.candidates_path).save([_candidate(), promoted])

    snapshot = OperatorWorkspace(settings).snapshot(candidate_status="active")

    assert [candidate["status"] for candidate in snapshot["candidates"]] == ["active"]


def test_promote_command_delegates_to_existing_candidate_promotion(
    tmp_path: Path,
) -> None:
    """Only the explicit command may move an active candidate into the queue."""
    settings = Settings.from_workspace(tmp_path)
    settings.input_path.parent.mkdir(parents=True)
    settings.input_path.write_text("# Queue\n", encoding="utf-8")
    ResearchCandidateStore(settings.candidates_path).save([_candidate()])

    result = OperatorWorkspace(settings).submit(
        {"action": "promote_candidate", "candidate_id": "candidate-001"}
    )

    assert result["ok"] is True
    assert "https://example.com/article" in settings.input_path.read_text()


def test_regeneration_requires_non_empty_feedback(tmp_path: Path) -> None:
    """Browser input cannot silently initiate a fresh review cycle."""
    with pytest.raises(ValueError, match="non-empty feedback"):
        OperatorWorkspace(Settings.from_workspace(tmp_path)).submit(
            {
                "action": "review",
                "post_id": "post-1",
                "review_action": "regenerate_text",
            }
        )
