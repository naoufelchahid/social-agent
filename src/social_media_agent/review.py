"""Rich terminal human review and immutable local approval boundary."""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Protocol

from PIL import Image, UnidentifiedImageError
from pydantic import ValidationError
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from social_media_agent.artifacts import ArtifactRepository
from social_media_agent.errors import HumanReviewError, PipelineStateError
from social_media_agent.images import load_validated_image_artifact, validate_image_file
from social_media_agent.models import (
    AgentReview,
    ApprovedManifest,
    DraftPackage,
    ExtractedSource,
    ImageArtifact,
    ImageSemanticReview,
    JobStage,
    QueueItem,
    ValidationReport,
)
from social_media_agent.publication import (
    PublicationAttempt,
    PublicationPlatform,
    PublicationRequest,
    PublicationResult,
    PublicationState,
    UnconfiguredPublisher,
)
from social_media_agent.queue import QueueFormatError, mark_queue_item_checked
from social_media_agent.state import StateStore, transition_job
from social_media_agent.validation import validate_draft


class ReviewAction(StrEnum):
    """Human-controlled actions available at the local product boundary."""

    ACCEPT = "accept"
    EDIT = "edit"
    REGENERATE_TEXT = "regenerate_text"
    REGENERATE_IMAGE = "regenerate_image"
    OPEN_IMAGE = "open_image"
    REPLACE_IMAGE = "replace_image"
    SKIP = "skip"
    REJECT = "reject"
    SAVE_QUIT = "save_quit"


@dataclass(frozen=True)
class HumanReviewContext:
    """All persisted evidence required by one terminal review session."""

    post_id: str
    queue_item: QueueItem
    source: ExtractedSource
    draft: DraftPackage
    deterministic_validation: ValidationReport
    semantic_review: AgentReview
    image: ImageArtifact
    source_path: Path
    brand_path: Path
    draft_path: Path
    image_artifact_path: Path


@dataclass(frozen=True)
class ReviewOutcome:
    """Result of one review action."""

    action: ReviewAction
    stage: JobStage
    message: str
    sync_warning: str | None = None


class TextReviewer(Protocol):
    async def review(
        self,
        *,
        post_id: str,
        source_path: Path,
        brand_path: Path,
        draft_path: Path,
    ) -> AgentReview: ...


class ImageReviewer(Protocol):
    async def review(
        self,
        *,
        post_id: str,
        image_path: Path,
        draft_path: Path,
        request_path: Path,
        attempt: int,
    ) -> ImageSemanticReview: ...


class ImageOpener(Protocol):
    def open(self, path: Path) -> None: ...


class Editor(Protocol):
    def edit(self, path: Path) -> None: ...


class Publisher(Protocol):
    """Publish the exact approved image and renderings after acceptance."""

    async def publish(self, request: PublicationRequest) -> PublicationResult: ...


class SystemImageOpener:
    """Open an image with the platform viewer only after explicit action."""

    def open(self, path: Path) -> None:
        if sys.platform == "darwin":
            command = ["open", str(path)]
        elif os.name == "nt":
            command = ["cmd", "/c", "start", "", str(path)]
        else:
            command = ["xdg-open", str(path)]
        try:
            subprocess.Popen(
                command,
                shell=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        except OSError as exc:
            raise HumanReviewError("Failed to open the image viewer") from exc


class SystemEditor:
    """Run the configured terminal editor through a literal argument array."""

    def edit(self, path: Path) -> None:
        editor = os.environ.get("EDITOR", "").strip()
        if not editor:
            raise HumanReviewError("EDITOR is not configured")
        arguments = [*shlex.split(editor), str(path)]
        try:
            completed = subprocess.run(arguments, shell=False, check=False)
        except OSError as exc:
            raise HumanReviewError("Failed to start the configured editor") from exc
        if completed.returncode != 0:
            raise HumanReviewError("Configured editor failed")


def render_review_screen(context: HumanReviewContext) -> str:
    """Render provenance, both copies, warnings, and the mandatory image path."""
    console = Console(record=True, width=110, color_system=None)
    provenance = Table.grid(padding=(0, 1))
    provenance.add_row("Title", context.source.title)
    provenance.add_row("URL", context.source.canonical_url)
    provenance.add_row("Source", context.source.source_type.value)
    provenance.add_row("Extraction", context.source.extraction_method.value)
    if context.source.author:
        provenance.add_row("Author", context.source.author)
    console.print(Panel(provenance, title=f"Review {context.post_id}"))
    console.print(Panel(context.draft.linkedin, title="LinkedIn"))
    console.print(Panel(context.draft.x, title="X"))
    warnings = context.deterministic_validation.warnings
    warning_text = (
        "\n".join(f"{warning.code.value}: {warning.message}" for warning in warnings)
        or "None"
    )
    console.print(Panel(warning_text, title="Validation warnings"))
    console.print(Panel(context.image.path, title="Mandatory image"))
    return console.export_text()


class ReviewService:
    """Apply human actions while preserving exact persisted workflow state."""

    def __init__(
        self,
        *,
        workspace: Path,
        artifacts: ArtifactRepository,
        state_store: StateStore,
        queue_path: Path,
        text_reviewer: TextReviewer,
        image_reviewer: ImageReviewer,
        opener: ImageOpener,
        publisher: Publisher | None = None,
    ) -> None:
        self.workspace = workspace.resolve()
        self.artifacts = artifacts
        self.state_store = state_store
        self.queue_path = queue_path
        self.text_reviewer = text_reviewer
        self.image_reviewer = image_reviewer
        self.opener = opener
        self.publisher = publisher or UnconfiguredPublisher()

    async def apply(
        self,
        context: HumanReviewContext,
        action: ReviewAction,
        *,
        feedback: str | None = None,
        replacement_path: Path | None = None,
        editor: Editor | None = None,
    ) -> tuple[HumanReviewContext, ReviewOutcome]:
        """Apply one explicit human action."""
        self._require_human_review(context.post_id)
        if action is ReviewAction.OPEN_IMAGE:
            self.opener.open(self.workspace / context.image.path)
            return context, self._outcome(action, JobStage.HUMAN_REVIEW, "Image opened")
        if action is ReviewAction.SAVE_QUIT:
            return context, self._outcome(
                action,
                JobStage.HUMAN_REVIEW,
                "Review saved for exact resumption",
            )
        if action is ReviewAction.EDIT:
            return await self._edit(context, editor or SystemEditor())
        if action is ReviewAction.REPLACE_IMAGE:
            if replacement_path is None:
                raise HumanReviewError("Image replacement requires an explicit path")
            return await self._replace_image(context, replacement_path)
        if action in {ReviewAction.REGENERATE_TEXT, ReviewAction.REGENERATE_IMAGE}:
            normalized_feedback = (feedback or "").strip()
            if not normalized_feedback:
                raise HumanReviewError("Regeneration requires non-empty feedback")
            is_text = action is ReviewAction.REGENERATE_TEXT
            name = (
                "human-text-regeneration.json"
                if is_text
                else "human-image-regeneration.json"
            )
            self.artifacts.write_json(
                context.post_id,
                name,
                {"schema_version": 1, "feedback": normalized_feedback},
            )
            target = JobStage.VALIDATING if is_text else JobStage.GENERATING_IMAGE
            self._transition(context.post_id, target)
            return context, self._outcome(action, target, "Regeneration requested")
        if action is ReviewAction.SKIP:
            self._transition(context.post_id, JobStage.PENDING)
            return context, self._outcome(action, JobStage.PENDING, "Review skipped")
        if action is ReviewAction.REJECT:
            self._transition(context.post_id, JobStage.REJECTED)
            return context, self._outcome(action, JobStage.REJECTED, "Draft rejected")
        if action is ReviewAction.ACCEPT:
            return await self._accept(context)
        raise HumanReviewError(f"Unsupported review action: {action}")

    async def write_approved_manifest(self, context: HumanReviewContext) -> Path:
        """Create the immutable approval snapshot exactly once."""
        validated_image = load_validated_image_artifact(
            workspace=self.workspace,
            post_id=context.post_id,
            artifact_path=context.image_artifact_path,
        )
        manifest = ApprovedManifest(
            post_id=context.post_id,
            source=context.source,
            draft=context.draft,
            deterministic_validation=context.deterministic_validation,
            semantic_review=context.semantic_review,
            image=validated_image,
        )
        try:
            return self.artifacts.write_json_immutable(
                context.post_id,
                "approved-manifest.json",
                manifest.model_dump(mode="json"),
            )
        except PipelineStateError as exc:
            raise HumanReviewError("Approved manifest is immutable") from exc

    async def _accept(
        self, context: HumanReviewContext
    ) -> tuple[HumanReviewContext, ReviewOutcome]:
        await self.write_approved_manifest(context)
        self._transition(context.post_id, JobStage.APPROVED)
        publication = await self.publisher.publish(
            PublicationRequest(
                post_id=context.post_id,
                x_text=context.draft.x,
                linkedin_text=context.draft.linkedin,
                image_bytes=(self.workspace / context.image.path).read_bytes(),
            )
        )
        self._write_publication_artifacts(context.post_id, publication)
        sync_warning: str | None = None
        try:
            mark_queue_item_checked(self.queue_path, context.queue_item)
        except (OSError, QueueFormatError):
            sync_warning = "Approved; queue checkbox synchronization failed"
            self._record_warning(context.post_id, sync_warning)
        return context, ReviewOutcome(
            action=ReviewAction.ACCEPT,
            stage=JobStage.APPROVED,
            message="Draft package approved locally",
            sync_warning=sync_warning,
        )

    def _write_publication_artifacts(
        self, post_id: str, publication: PublicationResult
    ) -> None:
        attempts = {attempt.platform: attempt for attempt in publication.attempts}
        outcomes = [
            _publication_attempt_payload(
                attempts.get(
                    platform,
                    PublicationAttempt(
                        platform=platform,
                        state=PublicationState.PENDING,
                    ),
                )
            )
            for platform in (PublicationPlatform.X, PublicationPlatform.LINKEDIN)
        ]
        self.artifacts.write_json_immutable(
            post_id,
            "publication-outcomes.json",
            {
                "schema_version": 1,
                "post_id": post_id,
                "recorded_at": datetime.now(UTC).isoformat(),
                "outcomes": outcomes,
            },
        )
        for attempt in publication.attempts:
            if attempt.state is not PublicationState.PUBLISHED:
                continue
            self.artifacts.write_json_immutable(
                post_id,
                f"{attempt.platform}-publication-receipt.json",
                {
                    "schema_version": 1,
                    "post_id": post_id,
                    "platform": attempt.platform,
                    "remote_id": attempt.remote_id,
                    "remote_url": attempt.remote_url,
                    "published_at": datetime.now(UTC).isoformat(),
                },
            )

    async def _edit(
        self,
        context: HumanReviewContext,
        editor: Editor,
    ) -> tuple[HumanReviewContext, ReviewOutcome]:
        candidate_reference = self.artifacts.write_json(
            context.post_id,
            "human-edit-candidate.json",
            context.draft.model_dump(mode="json"),
        )
        candidate_path = self.workspace / candidate_reference
        editor.edit(candidate_path)
        try:
            candidate = DraftPackage.model_validate_json(candidate_path.read_text())
        except (OSError, ValidationError) as exc:
            raise HumanReviewError("Edited draft contract is invalid") from exc
        if candidate.image_brief != context.draft.image_brief:
            raise HumanReviewError(
                "Text editing cannot change the approved image brief"
            )
        validation = validate_draft(candidate, source=context.source)
        self.artifacts.write_json(
            context.post_id,
            "human-edit-validation.json",
            validation.model_dump(mode="json"),
        )
        if not validation.passed:
            raise HumanReviewError("Edited draft failed deterministic validation")
        semantic = context.semantic_review
        if _meaningful_draft(candidate) != _meaningful_draft(context.draft):
            semantic = await self.text_reviewer.review(
                post_id=context.post_id,
                source_path=context.source_path,
                brand_path=context.brand_path,
                draft_path=candidate_path,
            )
            self.artifacts.write_json(
                context.post_id,
                "human-edit-semantic-review.json",
                semantic.model_dump(mode="json"),
            )
            if not semantic.passed:
                raise HumanReviewError("Edited draft failed semantic review")
        self.artifacts.write_json(
            context.post_id,
            context.draft_path.name,
            candidate.model_dump(mode="json"),
        )
        updated = replace(
            context,
            draft=candidate,
            deterministic_validation=validation,
            semantic_review=semantic,
        )
        return updated, self._outcome(
            ReviewAction.EDIT,
            JobStage.HUMAN_REVIEW,
            "Draft edit validated",
        )

    async def _replace_image(
        self,
        context: HumanReviewContext,
        replacement_path: Path,
    ) -> tuple[HumanReviewContext, ReviewOutcome]:
        source = replacement_path.resolve()
        if replacement_path.is_symlink() or not source.is_file():
            raise HumanReviewError("Replacement image must be a regular file")
        candidate = (
            self.workspace
            / "output"
            / "posts"
            / context.post_id
            / ("human-image-replacement.png")
        )
        _atomic_copy(source, candidate)
        try:
            _validate_replacement_candidate(candidate)
            request_reference = self.artifacts.write_json(
                context.post_id,
                "human-image-replacement-request.json",
                {
                    "schema_version": 1,
                    "image_brief": context.draft.image_brief,
                    "source": "human replacement",
                },
            )
            review = await self.image_reviewer.review(
                post_id=context.post_id,
                image_path=candidate,
                draft_path=context.draft_path,
                request_path=self.workspace / request_reference,
                attempt=1,
            )
            self.artifacts.write_json(
                context.post_id,
                "human-image-replacement-review.json",
                review.model_dump(mode="json"),
            )
            if not review.passed:
                raise HumanReviewError("Replacement image failed semantic validation")
            final_path = self.workspace / context.image.path
            candidate.replace(final_path)
            metadata = validate_image_file(
                workspace=self.workspace,
                post_id=context.post_id,
                reported_path=Path(context.image.path),
            )
            image = ImageArtifact(
                **metadata.model_dump(),
                prompt="Human-provided replacement image",
                generator_identity="human-replacement",
                generation_attempt=1,
                validation_result=review,
            )
            self.artifacts.write_json(
                context.post_id,
                context.image_artifact_path.name,
                image.model_dump(mode="json"),
            )
        except HumanReviewError:
            raise
        except (OSError, UnidentifiedImageError, ValueError) as exc:
            raise HumanReviewError("Replacement image failed local validation") from exc
        updated = replace(context, image=image)
        return updated, self._outcome(
            ReviewAction.REPLACE_IMAGE,
            JobStage.HUMAN_REVIEW,
            "Replacement image validated",
        )

    def _transition(self, post_id: str, stage: JobStage) -> None:
        state = self.state_store.load()
        self.state_store.save(transition_job(state, post_id, stage))

    def _record_warning(self, post_id: str, warning: str) -> None:
        state = self.state_store.load()
        job = state.jobs[post_id].model_copy(update={"last_error": warning})
        self.state_store.save(
            state.model_copy(update={"jobs": {**state.jobs, post_id: job}})
        )

    def _require_human_review(self, post_id: str) -> None:
        state = self.state_store.load()
        job = state.jobs.get(post_id)
        if job is None or job.stage is not JobStage.HUMAN_REVIEW:
            raise HumanReviewError("Post is not at human_review")

    @staticmethod
    def _outcome(
        action: ReviewAction,
        stage: JobStage,
        message: str,
    ) -> ReviewOutcome:
        return ReviewOutcome(action=action, stage=stage, message=message)


async def run_review(
    context: HumanReviewContext,
    *,
    service: ReviewService,
    interactive: bool,
    explicit_post_id: str | None = None,
    explicit_action: ReviewAction | None = None,
    feedback: str | None = None,
    replacement_path: Path | None = None,
    read: Callable[[str], str] = input,
    console: Console | None = None,
) -> ReviewOutcome:
    """Run interactive review or one fully explicit noninteractive action."""
    if not interactive:
        if explicit_post_id is None or explicit_action is None:
            raise HumanReviewError(
                "Noninteractive review requires an explicit post ID and action"
            )
        if explicit_post_id != context.post_id:
            raise HumanReviewError("Explicit post ID does not match review context")
        _, outcome = await service.apply(
            context,
            explicit_action,
            feedback=feedback,
            replacement_path=replacement_path,
        )
        return outcome

    active_console = console or Console()
    active_console.print(render_review_screen(context))
    current = context
    while True:
        try:
            raw = read(
                "Action [a/e/t/i/o/p/s/r/q] (accept/edit/text/image/open/replace/"
                "skip/reject/quit): "
            )
        except (EOFError, KeyboardInterrupt):
            _, outcome = await service.apply(current, ReviewAction.SAVE_QUIT)
            return outcome
        try:
            action = _parse_action(raw)
            action_feedback: str | None = None
            action_replacement: Path | None = None
            if action in {ReviewAction.REGENERATE_TEXT, ReviewAction.REGENERATE_IMAGE}:
                action_feedback = read("Feedback: ")
            elif action is ReviewAction.REPLACE_IMAGE:
                action_replacement = Path(read("Replacement image path: "))
            current, outcome = await service.apply(
                current,
                action,
                feedback=action_feedback,
                replacement_path=action_replacement,
            )
        except HumanReviewError as exc:
            active_console.print(f"Review action failed: {exc}")
            continue
        if action in {
            ReviewAction.OPEN_IMAGE,
            ReviewAction.EDIT,
            ReviewAction.REPLACE_IMAGE,
        }:
            active_console.print(render_review_screen(current))
            continue
        return outcome


def _parse_action(value: str) -> ReviewAction:
    actions = {
        "a": ReviewAction.ACCEPT,
        "e": ReviewAction.EDIT,
        "t": ReviewAction.REGENERATE_TEXT,
        "i": ReviewAction.REGENERATE_IMAGE,
        "o": ReviewAction.OPEN_IMAGE,
        "p": ReviewAction.REPLACE_IMAGE,
        "s": ReviewAction.SKIP,
        "r": ReviewAction.REJECT,
        "q": ReviewAction.SAVE_QUIT,
    }
    try:
        return actions[value.strip().casefold()]
    except KeyError as exc:
        raise HumanReviewError("Unknown review action") from exc


def _meaningful_draft(draft: DraftPackage) -> tuple[str, str, str, str]:
    return (
        " ".join(draft.concept.split()),
        " ".join(draft.linkedin.split()),
        " ".join(draft.x.split()),
        " ".join(draft.image_brief.split()),
    )


def _publication_attempt_payload(attempt: PublicationAttempt) -> dict[str, str | None]:
    return {
        "platform": attempt.platform,
        "state": attempt.state,
        "remote_id": attempt.remote_id,
        "remote_url": attempt.remote_url,
        "error": attempt.error,
    }


def _atomic_copy(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with (
            source.open("rb") as source_handle,
            NamedTemporaryFile(
                mode="wb",
                dir=destination.parent,
                prefix=f".{destination.name}.",
                suffix=".tmp",
                delete=False,
            ) as temporary,
        ):
            temporary_path = Path(temporary.name)
            shutil.copyfileobj(source_handle, temporary)
            temporary.flush()
            os.fsync(temporary.fileno())
        temporary_path.replace(destination)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def _validate_replacement_candidate(path: Path) -> None:
    if path.is_symlink() or path.stat().st_size <= 0:
        raise HumanReviewError("Replacement image must be a non-empty regular file")
    try:
        with Image.open(path) as opened:
            image_format = opened.format
            dimensions = opened.size
            opened.verify()
    except (OSError, UnidentifiedImageError, ValueError) as exc:
        raise HumanReviewError("Replacement image cannot be decoded") from exc
    if image_format != "PNG" or dimensions != (1536, 1024):
        raise HumanReviewError("Replacement image must be a 1536x1024 PNG")
