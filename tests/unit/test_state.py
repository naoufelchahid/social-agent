"""Tests for durable local pipeline state."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from social_media_agent.errors import PipelineStateError
from social_media_agent.models import JobRecord, JobStage, PipelineState
from social_media_agent.state import (
    StateStore,
    add_job,
    interrupt_active_job,
    next_resumable_job,
    restore_job,
    transition_job,
)


def test_state_store_round_trips_atomically(tmp_path: Path) -> None:
    """Saved state should validate on load and leave no temporary file behind."""
    store = StateStore(tmp_path / "output" / "state.json")
    state = add_job(PipelineState(), "post-1", "https://example.com/post")

    store.save(state)

    assert store.load() == state
    assert list((tmp_path / "output").glob(".state.json.*.tmp")) == []


def test_state_store_returns_empty_state_when_missing(tmp_path: Path) -> None:
    """A new workspace should not require manual state initialization."""
    store = StateStore(tmp_path / "output" / "state.json")

    assert store.load() == PipelineState()


@pytest.mark.parametrize("contents", ["not json", '{"schema_version": 2}'])
def test_state_store_fails_closed_for_untrusted_state(
    tmp_path: Path, contents: str
) -> None:
    """Corrupt or unknown state must never be silently overwritten."""
    state_path = tmp_path / "state.json"
    state_path.write_text(contents, encoding="utf-8")

    with pytest.raises(PipelineStateError):
        StateStore(state_path).load()


def test_transition_enforces_the_pipeline_state_machine() -> None:
    """Jobs may advance only through explicitly allowed transitions."""
    state = add_job(PipelineState(), "post-1", "https://example.com/post")

    extracting = transition_job(state, "post-1", JobStage.EXTRACTING)

    assert extracting.jobs["post-1"].stage is JobStage.EXTRACTING
    with pytest.raises(PipelineStateError, match=r"extracting.*approved"):
        transition_job(extracting, "post-1", JobStage.APPROVED)


def test_next_resumable_job_prefers_active_then_oldest() -> None:
    """Resume order should be deterministic across sessions."""
    now = datetime.now(UTC)
    older = JobRecord(
        post_id="older",
        normalized_url="https://example.com/older",
        created_at=now - timedelta(minutes=1),
        updated_at=now - timedelta(minutes=1),
    )
    newer = JobRecord(
        post_id="newer",
        normalized_url="https://example.com/newer",
        created_at=now,
        updated_at=now,
    )
    state = PipelineState(jobs={"older": older, "newer": newer}, active_job_id="newer")

    assert next_resumable_job(state).post_id == "newer"  # type: ignore[union-attr]
    without_active = state.model_copy(update={"active_job_id": None})
    assert next_resumable_job(without_active).post_id == "older"  # type: ignore[union-attr]


def test_terminal_jobs_are_not_resumable() -> None:
    """Approved and rejected work should stay terminal."""
    approved = JobRecord(
        post_id="done",
        normalized_url="https://example.com/done",
        stage=JobStage.APPROVED,
    )
    state = PipelineState(jobs={"done": approved})

    assert next_resumable_job(state) is None


def test_failed_job_requires_explicit_retry_before_resume() -> None:
    """Resume must not bypass the retry-failed command's explicit intent."""
    failed = JobRecord(
        post_id="failed",
        normalized_url="https://example.com/failed",
        stage=JobStage.FAILED,
        failed_stage=JobStage.EXTRACTING,
    )
    state = PipelineState(jobs={"failed": failed}, active_job_id="failed")

    assert next_resumable_job(state) is None


@pytest.mark.parametrize(
    "target",
    [JobStage.FAILED, JobStage.INTERRUPTED],
)
def test_failed_and_interrupted_jobs_restore_the_exact_prior_stage(
    target: JobStage,
) -> None:
    """Retry and resume should restart the failed operation, not the whole job."""
    state = add_job(PipelineState(), "post-1", "https://example.com/post")
    state = transition_job(state, "post-1", JobStage.EXTRACTING)
    stopped = transition_job(state, "post-1", target)

    restored = restore_job(stopped, "post-1")

    assert restored.jobs["post-1"].stage is JobStage.EXTRACTING
    assert restored.jobs["post-1"].attempts == {"extracting": 1}
    assert restored.jobs["post-1"].failed_stage is None
    assert restored.jobs["post-1"].resume_stage is None


def test_restore_rejects_a_job_without_a_saved_stage() -> None:
    """Only failed or interrupted jobs carry a valid restore target."""
    state = add_job(PipelineState(), "post-1", "https://example.com/post")

    with pytest.raises(PipelineStateError, match="not failed or interrupted"):
        restore_job(state, "post-1")


@pytest.mark.parametrize(
    "active_stage",
    [
        JobStage.EXTRACTING,
        JobStage.DRAFTING,
        JobStage.VALIDATING,
        JobStage.GENERATING_IMAGE,
        JobStage.VALIDATING_IMAGE,
        JobStage.HUMAN_REVIEW,
    ],
)
def test_every_active_stage_interrupts_and_resumes_once(
    active_stage: JobStage,
) -> None:
    """A cooperative signal checkpoint must preserve every active operation."""
    job = JobRecord(
        post_id="post-1",
        normalized_url="https://example.com/post",
        stage=active_stage,
    )
    state = PipelineState(jobs={"post-1": job}, active_job_id="post-1")

    interrupted = interrupt_active_job(state)
    restored = restore_job(interrupted, "post-1")

    assert interrupted.jobs["post-1"].stage is JobStage.INTERRUPTED
    assert restored.jobs["post-1"].stage is active_stage
    assert restored.jobs["post-1"].attempts == {active_stage.value: 1}
