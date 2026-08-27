"""Sequential local pipeline coordinator and production stage wiring."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, TypeVar

from pydantic import BaseModel, ValidationError

from social_media_agent.agents import AgyWriter, CodexReviewer
from social_media_agent.artifacts import ArtifactRepository
from social_media_agent.commands import CommandRunner
from social_media_agent.config import Settings
from social_media_agent.errors import PipelineStateError, SocialAgentError
from social_media_agent.extraction import (
    ExtractionDispatcher,
    FirecrawlExtractor,
    GeneralPageExtractor,
    GitHubRepositoryExtractor,
    RedditPostExtractor,
    YouTubeTranscriptExtractor,
    render_untrusted_evidence,
)
from social_media_agent.images import (
    CodexImageGenerator,
    CodexImageReviewer,
    generate_validated_image,
    load_validated_image_artifact,
)
from social_media_agent.models import (
    AgentReview,
    DraftPackage,
    ExtractedSource,
    ImageArtifact,
    JobStage,
    QueueItem,
    SourceType,
    ValidationReport,
)
from social_media_agent.publication import DirectOAuthPublisher, PublisherSettings
from social_media_agent.queue import parse_queue
from social_media_agent.review import (
    HumanReviewContext,
    Publisher,
    ReviewAction,
    ReviewOutcome,
    ReviewService,
    SystemImageOpener,
    run_review,
)
from social_media_agent.signals import InterruptionController
from social_media_agent.state import (
    StateStore,
    add_job,
    interrupt_active_job,
    restore_job,
    transition_job,
)
from social_media_agent.validation import validate_with_rewrites

ContractModel = TypeVar("ContractModel", bound=BaseModel)


class PipelineWorkflow(Protocol):
    """One implementation of the atomic work performed at each persisted stage."""

    async def execute(
        self,
        item: QueueItem,
        stage: JobStage,
    ) -> ReviewOutcome | None: ...


@dataclass(frozen=True)
class PipelineRunResult:
    """Per-invocation terminal outcomes."""

    approved: int = 0
    rejected: int = 0
    failed: int = 0
    skipped: int = 0
    interrupted: bool = False


class PipelineCoordinator:
    """Select and advance one queue item at a time with durable stage boundaries."""

    def __init__(
        self,
        *,
        state_store: StateStore,
        queue_path: Path,
        workflow: PipelineWorkflow,
        interruption: InterruptionController | None = None,
    ) -> None:
        self.state_store = state_store
        self.queue_path = queue_path
        self.workflow = workflow
        self.interruption = interruption or InterruptionController()

    async def run(self, *, only_post_id: str | None = None) -> PipelineRunResult:
        """Import pending queue items and process each eligible item once."""
        items = parse_queue(self.queue_path)
        self._synchronize(items)
        return await self._process(items, only_post_id=only_post_id)

    async def resume(self) -> PipelineRunResult:
        """Restore the interrupted operation and continue the persisted queue."""
        items = parse_queue(self.queue_path)
        state = self.state_store.load()
        interrupted = next(
            (job for job in state.jobs.values() if job.stage is JobStage.INTERRUPTED),
            None,
        )
        if interrupted is not None:
            self.state_store.save(restore_job(state, interrupted.post_id))
        return await self._process(items)

    async def _process(
        self,
        items: list[QueueItem],
        *,
        only_post_id: str | None = None,
    ) -> PipelineRunResult:
        by_id = {item.id: item for item in items}
        if only_post_id is not None and only_post_id not in by_id:
            raise PipelineStateError(
                f"Post ID is not present in the queue: {only_post_id}"
            )
        skipped: set[str] = set()
        counts = {"approved": 0, "rejected": 0, "failed": 0, "skipped": 0}

        while True:
            selected = self._select(items, skipped, only_post_id)
            if selected is None:
                return _run_result(counts)
            outcome = await self._process_job(selected)
            if outcome is None:
                return _run_result(counts, interrupted=True)
            if outcome is JobStage.PENDING:
                skipped.add(selected.id)
                counts["skipped"] += 1
            elif outcome is JobStage.APPROVED:
                counts["approved"] += 1
            elif outcome is JobStage.REJECTED:
                counts["rejected"] += 1
            elif outcome is JobStage.FAILED:
                counts["failed"] += 1
            elif outcome is JobStage.HUMAN_REVIEW:
                return _run_result(counts)
            if only_post_id is not None:
                return _run_result(counts)

    async def _process_job(self, item: QueueItem) -> JobStage | None:
        while True:
            state = self.state_store.load()
            job = state.jobs[item.id]
            if job.stage in {
                JobStage.APPROVED,
                JobStage.REJECTED,
                JobStage.FAILED,
            }:
                return job.stage
            if job.stage is JobStage.INTERRUPTED:
                state = restore_job(state, item.id)
                self.state_store.save(state)
                job = state.jobs[item.id]
            if job.stage is JobStage.PENDING:
                state = transition_job(state, item.id, JobStage.EXTRACTING)
                self.state_store.save(state)
                job = state.jobs[item.id]

            try:
                review_outcome = await self.workflow.execute(item, job.stage)
            except SocialAgentError as exc:
                self._fail(item.id, exc)
                return JobStage.FAILED

            if self.interruption.requested:
                state = interrupt_active_job(self.state_store.load())
                self.state_store.save(state)
                return None

            if job.stage is JobStage.HUMAN_REVIEW:
                if review_outcome is None:
                    raise PipelineStateError("Human review did not return an outcome")
                current = self.state_store.load().jobs[item.id].stage
                if (
                    current is JobStage.HUMAN_REVIEW
                    and review_outcome.stage is not current
                ):
                    self.state_store.save(
                        transition_job(
                            self.state_store.load(), item.id, review_outcome.stage
                        )
                    )
                if review_outcome.action is ReviewAction.SAVE_QUIT:
                    return JobStage.HUMAN_REVIEW
                if review_outcome.action is ReviewAction.SKIP:
                    return JobStage.PENDING
                if review_outcome.action in {
                    ReviewAction.ACCEPT,
                    ReviewAction.REJECT,
                }:
                    return review_outcome.stage
                continue

            next_stage = _NEXT_STAGE[job.stage]
            self.state_store.save(
                transition_job(self.state_store.load(), item.id, next_stage)
            )

    def _synchronize(self, items: list[QueueItem]) -> None:
        state = self.state_store.load()
        for item in items:
            if not item.checked:
                state = add_job(state, item.id, item.normalized_url)
        self.state_store.save(state)

    def _select(
        self,
        items: list[QueueItem],
        skipped: set[str],
        only_post_id: str | None,
    ) -> QueueItem | None:
        state = self.state_store.load()
        eligible = {
            JobStage.PENDING,
            JobStage.EXTRACTING,
            JobStage.DRAFTING,
            JobStage.VALIDATING,
            JobStage.GENERATING_IMAGE,
            JobStage.VALIDATING_IMAGE,
            JobStage.HUMAN_REVIEW,
            JobStage.INTERRUPTED,
        }
        for item in items:
            if only_post_id is not None and item.id != only_post_id:
                continue
            job = state.jobs.get(item.id)
            if job is not None and job.stage in eligible and item.id not in skipped:
                return item
        return None

    def _fail(self, post_id: str, exc: SocialAgentError) -> None:
        state = transition_job(self.state_store.load(), post_id, JobStage.FAILED)
        job = state.jobs[post_id].model_copy(
            update={"last_error": f"{type(exc).__name__}: {exc}"}
        )
        self.state_store.save(
            state.model_copy(update={"jobs": {**state.jobs, post_id: job}})
        )


_NEXT_STAGE: Mapping[JobStage, JobStage] = {
    JobStage.EXTRACTING: JobStage.DRAFTING,
    JobStage.DRAFTING: JobStage.VALIDATING,
    JobStage.VALIDATING: JobStage.GENERATING_IMAGE,
    JobStage.GENERATING_IMAGE: JobStage.VALIDATING_IMAGE,
    JobStage.VALIDATING_IMAGE: JobStage.HUMAN_REVIEW,
}


def _run_result(
    counts: Mapping[str, int], *, interrupted: bool = False
) -> PipelineRunResult:
    return PipelineRunResult(
        approved=counts["approved"],
        rejected=counts["rejected"],
        failed=counts["failed"],
        skipped=counts["skipped"],
        interrupted=interrupted,
    )


class LocalPipelineWorkflow:
    """Compose the production services behind the coordinator's stage interface."""

    def __init__(
        self,
        *,
        settings: Settings,
        queue_path: Path,
        state_store: StateStore,
        artifacts: ArtifactRepository,
        extractor: ExtractionDispatcher,
        writer: AgyWriter,
        text_reviewer: CodexReviewer,
        image_generator: CodexImageGenerator,
        image_reviewer: CodexImageReviewer,
        publisher: Publisher | None = None,
        interactive_review: bool = True,
        explicit_action: ReviewAction | None = None,
    ) -> None:
        self.settings = settings
        self.queue_path = queue_path
        self.state_store = state_store
        self.artifacts = artifacts
        self.extractor = extractor
        self.writer = writer
        self.text_reviewer = text_reviewer
        self.image_generator = image_generator
        self.image_reviewer = image_reviewer
        self.interactive_review = interactive_review
        self.explicit_action = explicit_action
        self.review_service = ReviewService(
            workspace=settings.workspace,
            artifacts=artifacts,
            state_store=state_store,
            queue_path=queue_path,
            text_reviewer=text_reviewer,
            image_reviewer=image_reviewer,
            opener=SystemImageOpener(),
            publisher=publisher,
        )

    async def execute(
        self,
        item: QueueItem,
        stage: JobStage,
    ) -> ReviewOutcome | None:
        """Execute one stage and persist its canonical handoff artifacts."""
        if stage is JobStage.EXTRACTING:
            source = await self.extractor.extract(item.normalized_url)
            self.artifacts.write_json(
                item.id, "source.json", source.model_dump(mode="json")
            )
            self.artifacts.write_text(
                item.id, "source-evidence.md", render_untrusted_evidence(source)
            )
            return None
        if stage is JobStage.DRAFTING:
            await self.writer.write(
                post_id=item.id,
                source_path=self._path(item.id, "source-evidence.md"),
                brand_path=self.settings.brand_path,
                angle=item.angle,
                audience=item.audience,
            )
            return None
        if stage is JobStage.VALIDATING:
            source = self._load(item.id, "source.json", ExtractedSource)
            draft = self._load(item.id, "draft.json", DraftPackage)
            outcome = await validate_with_rewrites(
                post_id=item.id,
                draft=draft,
                source=source,
                source_path=self._path(item.id, "source-evidence.md"),
                brand_path=self.settings.brand_path,
                artifacts=self.artifacts,
                rewriter=self.writer,
                reviewer=self.text_reviewer,
            )
            self.artifacts.write_json(
                item.id, "draft.json", outcome.draft.model_dump(mode="json")
            )
            self.artifacts.write_json(
                item.id,
                "validation-report.json",
                outcome.deterministic_report.model_dump(mode="json"),
            )
            self.artifacts.write_json(
                item.id,
                "semantic-review.json",
                outcome.semantic_review.model_dump(mode="json"),
            )
            return None
        if stage is JobStage.GENERATING_IMAGE:
            draft = self._load(item.id, "draft.json", DraftPackage)
            await generate_validated_image(
                post_id=item.id,
                image_brief=draft.image_brief,
                draft_path=self._path(item.id, "draft.json"),
                artifacts=self.artifacts,
                generator=self.image_generator,
                reviewer=self.image_reviewer,
            )
            return None
        if stage is JobStage.VALIDATING_IMAGE:
            load_validated_image_artifact(
                workspace=self.settings.workspace,
                post_id=item.id,
                artifact_path=self._path(item.id, "image-artifact.json"),
            )
            return None
        if stage is JobStage.HUMAN_REVIEW:
            context = self._review_context(item)
            return await run_review(
                context,
                service=self.review_service,
                interactive=self.interactive_review,
                explicit_post_id=item.id if not self.interactive_review else None,
                explicit_action=self.explicit_action,
            )
        raise PipelineStateError(f"Unsupported executable stage: {stage}")

    def _review_context(self, item: QueueItem) -> HumanReviewContext:
        return HumanReviewContext(
            post_id=item.id,
            queue_item=item,
            source=self._load(item.id, "source.json", ExtractedSource),
            draft=self._load(item.id, "draft.json", DraftPackage),
            deterministic_validation=self._load(
                item.id, "validation-report.json", ValidationReport
            ),
            semantic_review=self._load(item.id, "semantic-review.json", AgentReview),
            image=self._load(item.id, "image-artifact.json", ImageArtifact),
            source_path=self._path(item.id, "source-evidence.md"),
            brand_path=self.settings.brand_path,
            draft_path=self._path(item.id, "draft.json"),
            image_artifact_path=self._path(item.id, "image-artifact.json"),
        )

    def _path(self, post_id: str, name: str) -> Path:
        return self.settings.output_path / "posts" / post_id / name

    def _load(
        self,
        post_id: str,
        name: str,
        model: type[ContractModel],
    ) -> ContractModel:
        path = self._path(post_id, name)
        try:
            return model.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, ValidationError) as exc:
            raise PipelineStateError(
                f"Invalid or missing stage artifact: {name}"
            ) from exc


def build_local_coordinator(
    settings: Settings,
    *,
    queue_path: Path | None = None,
    interactive_review: bool = True,
    explicit_action: ReviewAction | None = None,
) -> PipelineCoordinator:
    """Construct the real local services used by CLI writer commands."""
    selected_queue = (queue_path or settings.input_path).resolve()
    artifacts = ArtifactRepository(settings.workspace, settings.output_path)
    state_store = StateStore(settings.state_path)
    runner = CommandRunner(workspace=settings.workspace)
    firecrawl = (
        FirecrawlExtractor(api_key=settings.firecrawl_api_key)
        if settings.firecrawl_api_key
        else None
    )
    extractor = ExtractionDispatcher(
        firecrawl=firecrawl,
        fallbacks={
            SourceType.GENERAL: GeneralPageExtractor(),
            SourceType.GITHUB: GitHubRepositoryExtractor(token=settings.github_token),
            SourceType.REDDIT: RedditPostExtractor(),
            SourceType.YOUTUBE: YouTubeTranscriptExtractor(),
        },
    )
    writer = AgyWriter(workspace=settings.workspace, artifacts=artifacts, runner=runner)
    text_reviewer = CodexReviewer(
        workspace=settings.workspace, artifacts=artifacts, runner=runner
    )
    image_generator = CodexImageGenerator(
        workspace=settings.workspace, artifacts=artifacts, runner=runner
    )
    image_reviewer = CodexImageReviewer(
        workspace=settings.workspace, artifacts=artifacts, runner=runner
    )
    publisher = _build_publisher(settings)
    workflow = LocalPipelineWorkflow(
        settings=settings,
        queue_path=selected_queue,
        state_store=state_store,
        artifacts=artifacts,
        extractor=extractor,
        writer=writer,
        text_reviewer=text_reviewer,
        image_generator=image_generator,
        image_reviewer=image_reviewer,
        publisher=publisher,
        interactive_review=interactive_review,
        explicit_action=explicit_action,
    )
    return PipelineCoordinator(
        state_store=state_store,
        queue_path=selected_queue,
        workflow=workflow,
    )


def _build_publisher(settings: Settings) -> DirectOAuthPublisher | None:
    values = (
        settings.x_access_token,
        settings.linkedin_access_token,
        settings.linkedin_author_urn,
        settings.linkedin_version,
    )
    if not all(value and value.strip() for value in values):
        return None
    x_access_token, linkedin_access_token, linkedin_author_urn, linkedin_version = (
        values
    )
    assert x_access_token is not None
    assert linkedin_access_token is not None
    assert linkedin_author_urn is not None
    assert linkedin_version is not None
    return DirectOAuthPublisher(
        PublisherSettings(
            x_access_token=x_access_token,
            linkedin_access_token=linkedin_access_token,
            linkedin_author_urn=linkedin_author_urn,
            linkedin_version=linkedin_version,
        )
    )
