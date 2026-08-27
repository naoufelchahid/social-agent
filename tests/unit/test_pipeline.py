"""Sequential coordinator tests for the Phase 7 local cutover."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from social_media_agent.errors import ExtractionError
from social_media_agent.models import JobStage, QueueItem
from social_media_agent.pipeline import PipelineCoordinator, PipelineRunResult
from social_media_agent.review import ReviewAction, ReviewOutcome
from social_media_agent.state import StateStore


class FakeWorkflow:
    """Record stage calls and return configured human-review outcomes."""

    def __init__(
        self,
        *,
        review_actions: dict[str, ReviewAction] | None = None,
        extraction_failure: str | None = None,
        after_call: Callable[[str, JobStage], None] | None = None,
    ) -> None:
        self.review_actions = review_actions or {}
        self.extraction_failure = extraction_failure
        self.after_call = after_call
        self.calls: list[tuple[str, JobStage]] = []

    async def execute(self, item: QueueItem, stage: JobStage) -> ReviewOutcome | None:
        self.calls.append((item.id, stage))
        if self.after_call is not None:
            self.after_call(item.id, stage)
        if stage is JobStage.EXTRACTING and item.id == self.extraction_failure:
            raise ExtractionError("fixture extraction failed")
        if stage is not JobStage.HUMAN_REVIEW:
            return None
        action = self.review_actions.get(item.id, ReviewAction.ACCEPT)
        target = {
            ReviewAction.ACCEPT: JobStage.APPROVED,
            ReviewAction.REJECT: JobStage.REJECTED,
            ReviewAction.SKIP: JobStage.PENDING,
            ReviewAction.SAVE_QUIT: JobStage.HUMAN_REVIEW,
        }[action]
        return ReviewOutcome(action=action, stage=target, message=action.value)


def _queue(tmp_path: Path, count: int = 3) -> Path:
    path = tmp_path / "content" / "urls.md"
    path.parent.mkdir(parents=True)
    path.write_text(
        "# Queue\n\n"
        + "".join(
            f"- [ ] https://example.com/article-{number}\n"
            for number in range(1, count + 1)
        ),
        encoding="utf-8",
    )
    return path


@pytest.mark.asyncio
async def test_run_is_sequential_and_continues_after_failure_and_rejection(
    tmp_path: Path,
) -> None:
    queue_path = _queue(tmp_path)
    from social_media_agent.queue import parse_queue

    items = parse_queue(queue_path)
    workflow = FakeWorkflow(
        extraction_failure=items[0].id,
        review_actions={items[1].id: ReviewAction.REJECT},
    )
    coordinator = PipelineCoordinator(
        state_store=StateStore(tmp_path / "output/state.json"),
        queue_path=queue_path,
        workflow=workflow,
    )

    result = await coordinator.run()

    state = coordinator.state_store.load()
    assert result == PipelineRunResult(
        approved=1,
        rejected=1,
        failed=1,
        skipped=0,
        interrupted=False,
    )
    assert [state.jobs[item.id].stage for item in items] == [
        JobStage.FAILED,
        JobStage.REJECTED,
        JobStage.APPROVED,
    ]
    call_ids = [post_id for post_id, _ in workflow.calls]
    assert call_ids == sorted(call_ids, key=lambda value: call_ids.index(value))
    assert call_ids[-1] == items[2].id


@pytest.mark.asyncio
async def test_skip_is_pending_but_selected_only_once_in_the_same_run(
    tmp_path: Path,
) -> None:
    queue_path = _queue(tmp_path, count=2)
    from social_media_agent.queue import parse_queue

    items = parse_queue(queue_path)
    workflow = FakeWorkflow(
        review_actions={items[0].id: ReviewAction.SKIP},
    )
    coordinator = PipelineCoordinator(
        state_store=StateStore(tmp_path / "output/state.json"),
        queue_path=queue_path,
        workflow=workflow,
    )

    result = await coordinator.run()

    state = coordinator.state_store.load()
    assert result.skipped == 1
    assert result.approved == 1
    assert state.jobs[items[0].id].stage is JobStage.PENDING
    assert state.jobs[items[1].id].stage is JobStage.APPROVED
    assert workflow.calls.count((items[0].id, JobStage.HUMAN_REVIEW)) == 1


@pytest.mark.asyncio
async def test_resume_restores_interrupted_stage_without_repeating_prior_work(
    tmp_path: Path,
) -> None:
    queue_path = _queue(tmp_path, count=1)
    from social_media_agent.queue import parse_queue

    item = parse_queue(queue_path)[0]
    first_workflow: FakeWorkflow
    coordinator: PipelineCoordinator

    def interrupt_after_draft(post_id: str, stage: JobStage) -> None:
        if stage is JobStage.DRAFTING:
            coordinator.interruption.requested = True

    first_workflow = FakeWorkflow(after_call=interrupt_after_draft)
    coordinator = PipelineCoordinator(
        state_store=StateStore(tmp_path / "output/state.json"),
        queue_path=queue_path,
        workflow=first_workflow,
    )

    first = await coordinator.run()
    assert first.interrupted is True
    assert coordinator.state_store.load().jobs[item.id].stage is JobStage.INTERRUPTED

    resumed_workflow = FakeWorkflow()
    resumed = PipelineCoordinator(
        state_store=coordinator.state_store,
        queue_path=queue_path,
        workflow=resumed_workflow,
    )
    result = await resumed.resume()

    assert result.approved == 1
    assert (item.id, JobStage.EXTRACTING) not in resumed_workflow.calls
    assert (item.id, JobStage.DRAFTING) in resumed_workflow.calls
    assert resumed.state_store.load().jobs[item.id].attempts == {"drafting": 1}
