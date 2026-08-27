"""Atomic pipeline state persistence and transition rules."""

from __future__ import annotations

import fcntl
import os
from datetime import UTC, datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from types import MappingProxyType, TracebackType
from typing import TextIO

from pydantic import ValidationError

from social_media_agent.errors import PipelineStateError
from social_media_agent.models import JobRecord, JobStage, PipelineState

_INACTIVE_STAGES = frozenset({JobStage.APPROVED, JobStage.REJECTED, JobStage.FAILED})
_ALLOWED_TRANSITIONS = MappingProxyType(
    {
        JobStage.PENDING: frozenset({JobStage.EXTRACTING, JobStage.REJECTED}),
        JobStage.EXTRACTING: frozenset(
            {JobStage.DRAFTING, JobStage.FAILED, JobStage.INTERRUPTED}
        ),
        JobStage.DRAFTING: frozenset(
            {JobStage.VALIDATING, JobStage.FAILED, JobStage.INTERRUPTED}
        ),
        JobStage.VALIDATING: frozenset(
            {
                JobStage.DRAFTING,
                JobStage.GENERATING_IMAGE,
                JobStage.FAILED,
                JobStage.INTERRUPTED,
            }
        ),
        JobStage.GENERATING_IMAGE: frozenset(
            {JobStage.VALIDATING_IMAGE, JobStage.FAILED, JobStage.INTERRUPTED}
        ),
        JobStage.VALIDATING_IMAGE: frozenset(
            {
                JobStage.GENERATING_IMAGE,
                JobStage.HUMAN_REVIEW,
                JobStage.FAILED,
                JobStage.INTERRUPTED,
            }
        ),
        JobStage.HUMAN_REVIEW: frozenset(
            {
                JobStage.PENDING,
                JobStage.VALIDATING,
                JobStage.GENERATING_IMAGE,
                JobStage.APPROVED,
                JobStage.REJECTED,
                JobStage.INTERRUPTED,
            }
        ),
        JobStage.FAILED: frozenset(),
        JobStage.INTERRUPTED: frozenset(),
        JobStage.APPROVED: frozenset(),
        JobStage.REJECTED: frozenset(),
    }
)


class StateStore:
    """Read and atomically replace the versioned state document."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> PipelineState:
        """Load validated state, returning a new state when no file exists."""
        try:
            contents = self.path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return PipelineState()

        try:
            return PipelineState.model_validate_json(contents)
        except ValidationError as exc:
            raise PipelineStateError(f"Invalid pipeline state: {self.path}") from exc

    def save(self, state: PipelineState) -> None:
        """Persist state atomically in the destination directory."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path: Path | None = None
        try:
            with NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.path.parent,
                prefix=f".{self.path.name}.",
                suffix=".tmp",
                delete=False,
            ) as temporary:
                temporary_path = Path(temporary.name)
                temporary.write(state.model_dump_json(indent=2))
                temporary.write("\n")
                temporary.flush()
                os.fsync(temporary.fileno())
            temporary_path.replace(self.path)
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)


class RunLock:
    """Nonblocking advisory lock that prevents concurrent pipeline writers."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._handle: TextIO | None = None

    def __enter__(self) -> RunLock:
        """Acquire the lock or raise when another writer holds it."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle = self.path.open("a+", encoding="utf-8")
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            handle.close()
            raise PipelineStateError(
                "The social-agent pipeline is already running"
            ) from exc
        handle.seek(0)
        handle.truncate()
        handle.write(f"{os.getpid()}\n")
        handle.flush()
        self._handle = handle
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Release the advisory lock while retaining the diagnostic file."""
        if self._handle is not None:
            fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
            self._handle.close()
            self._handle = None


def add_job(state: PipelineState, post_id: str, normalized_url: str) -> PipelineState:
    """Add one pending job without mutating the prior state snapshot."""
    if post_id in state.jobs:
        return state
    jobs = {
        **state.jobs,
        post_id: JobRecord(post_id=post_id, normalized_url=normalized_url),
    }
    return state.model_copy(update={"jobs": jobs})


def transition_job(
    state: PipelineState,
    post_id: str,
    target: JobStage,
) -> PipelineState:
    """Return state with one job advanced through an allowed edge."""
    try:
        job = state.jobs[post_id]
    except KeyError as exc:
        raise PipelineStateError(f"Unknown post ID: {post_id}") from exc
    if target not in _ALLOWED_TRANSITIONS[job.stage]:
        raise PipelineStateError(f"Invalid transition: {job.stage} -> {target}")

    updates: dict[str, object] = {
        "stage": target,
        "updated_at": datetime.now(UTC),
    }
    if target is JobStage.FAILED:
        updates["failed_stage"] = job.stage
    elif target is JobStage.INTERRUPTED:
        updates["resume_stage"] = job.stage
    updated = job.model_copy(update=updates)
    jobs = {**state.jobs, post_id: updated}
    active_job_id = None if target in _INACTIVE_STAGES else post_id
    return state.model_copy(update={"jobs": jobs, "active_job_id": active_job_id})


def next_resumable_job(state: PipelineState) -> JobRecord | None:
    """Return the active nonterminal job, otherwise the oldest nonterminal job."""
    if state.active_job_id:
        active = state.jobs.get(state.active_job_id)
        if active is not None and active.stage not in _INACTIVE_STAGES:
            return active
    candidates = [
        job for job in state.jobs.values() if job.stage not in _INACTIVE_STAGES
    ]
    return min(candidates, key=lambda job: job.created_at, default=None)


def restore_job(state: PipelineState, post_id: str) -> PipelineState:
    """Restore a failed or interrupted job to the operation that stopped."""
    try:
        job = state.jobs[post_id]
    except KeyError as exc:
        raise PipelineStateError(f"Unknown post ID: {post_id}") from exc

    saved_stage = (
        job.failed_stage
        if job.stage is JobStage.FAILED
        else job.resume_stage
        if job.stage is JobStage.INTERRUPTED
        else None
    )
    if saved_stage is None:
        raise PipelineStateError(f"Job {post_id} is not failed or interrupted")

    attempts = {
        **job.attempts,
        saved_stage.value: job.attempts.get(saved_stage.value, 0) + 1,
    }
    restored = job.model_copy(
        update={
            "stage": saved_stage,
            "failed_stage": None,
            "resume_stage": None,
            "last_error": None,
            "attempts": attempts,
            "updated_at": datetime.now(UTC),
        }
    )
    jobs = {**state.jobs, post_id: restored}
    return state.model_copy(update={"jobs": jobs, "active_job_id": post_id})


def interrupt_active_job(state: PipelineState) -> PipelineState:
    """Checkpoint the active operation after a cooperative signal request."""
    if state.active_job_id is None:
        return state
    try:
        active = state.jobs[state.active_job_id]
    except KeyError as exc:
        raise PipelineStateError(
            f"Active post ID is missing: {state.active_job_id}"
        ) from exc
    if JobStage.INTERRUPTED not in _ALLOWED_TRANSITIONS[active.stage]:
        return state
    return transition_job(state, active.post_id, JobStage.INTERRUPTED)
