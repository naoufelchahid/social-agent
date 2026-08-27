"""Tests for local terminal human review and approval."""

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import pytest
from PIL import Image
from rich.console import Console

from social_media_agent.artifacts import ArtifactRepository
from social_media_agent.errors import HumanReviewError
from social_media_agent.images import validate_image_file
from social_media_agent.models import (
    AgentReview,
    DraftPackage,
    ExtractedSource,
    ExtractionMethod,
    ImageArtifact,
    ImageSemanticReview,
    JobRecord,
    JobStage,
    PipelineState,
    QueueItem,
    SourceType,
)
from social_media_agent.publication import (
    PublicationAttempt,
    PublicationPlatform,
    PublicationRequest,
    PublicationResult,
    PublicationState,
)
from social_media_agent.review import (
    HumanReviewContext,
    ReviewAction,
    ReviewService,
    render_review_screen,
    run_review,
)
from social_media_agent.state import StateStore, add_job, next_resumable_job
from social_media_agent.validation import validate_draft


def _write_png(path: Path, *, color: tuple[int, int, int] = (20, 60, 90)) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (1536, 1024), color=color).save(path, format="PNG")


@dataclass
class FakeTextReviewer:
    outcomes: list[AgentReview]
    calls: list[dict[str, object]] = field(default_factory=list)

    async def review(self, **kwargs: object) -> AgentReview:
        self.calls.append(kwargs)
        return self.outcomes.pop(0)


@dataclass
class FakeImageReviewer:
    outcomes: list[ImageSemanticReview]
    calls: list[dict[str, object]] = field(default_factory=list)

    async def review(self, **kwargs: object) -> ImageSemanticReview:
        self.calls.append(kwargs)
        return self.outcomes.pop(0)


@dataclass
class FakeOpener:
    paths: list[Path] = field(default_factory=list)

    def open(self, path: Path) -> None:
        self.paths.append(path)


@dataclass
class FakePublisher:
    result: PublicationResult
    requests: list[PublicationRequest] = field(default_factory=list)

    async def publish(self, request: PublicationRequest) -> PublicationResult:
        self.requests.append(request)
        return self.result


@dataclass
class FakeEditor:
    update: Callable[[Path], None] | None = None
    failure: str | None = None

    def edit(self, path: Path) -> None:
        if self.failure:
            raise HumanReviewError(self.failure)
        if self.update:
            self.update(path)


def _semantic(*, passed: bool = True) -> AgentReview:
    return AgentReview(
        passed=passed,
        summary="Grounded." if passed else "Unsupported edit.",
        errors=[] if passed else ["The edit adds an unsupported claim."],
        suggested_fix=None if passed else "Remove the unsupported claim.",
    )


def _image_review(*, passed: bool = True) -> ImageSemanticReview:
    return ImageSemanticReview(
        passed=passed,
        relevance=passed,
        no_unwanted_text=passed,
        no_logos=passed,
        no_watermarks=passed,
        consistent_with_post=passed,
        summary="Valid image." if passed else "Image is inconsistent.",
        feedback=None if passed else "Use an image matching the concept.",
    )


def _draft(**changes: str) -> DraftPackage:
    values = {
        "concept": "Local stages make review dependable.",
        "linkedin": (
            "Local stages preserve evidence.\n\nReview remains human-controlled."
        ),
        "x": "Local stages keep draft review visible and resumable.",
        "image_brief": "Three connected stages in a local workflow.",
    }
    values.update(changes)
    return DraftPackage(**values)


def _source() -> ExtractedSource:
    return ExtractedSource(
        canonical_url="https://example.com/article",
        source_type=SourceType.GENERAL,
        title="Local workflow evidence",
        author="Example Author",
        content="Local stages preserve evidence for human review.",
        metadata={},
        extraction_method=ExtractionMethod.GENERAL_HTTP,
    )


def _setup(
    tmp_path: Path,
    *,
    text_reviews: list[AgentReview] | None = None,
    image_reviews: list[ImageSemanticReview] | None = None,
    queue_contents: str = "# Queue\n\n- [ ] https://example.com/article\n",
    publisher: FakePublisher | None = None,
) -> tuple[
    HumanReviewContext, ReviewService, FakeTextReviewer, FakeImageReviewer, FakeOpener
]:
    output = tmp_path / "output"
    post_dir = output / "posts/post-1"
    image_path = post_dir / "image.png"
    _write_png(image_path)
    source = _source()
    draft = _draft()
    validation = validate_draft(draft, source=source)
    semantic = _semantic()
    image_review = _image_review()
    metadata = validate_image_file(
        workspace=tmp_path,
        post_id="post-1",
        reported_path=Path("output/posts/post-1/image.png"),
    )
    image = ImageArtifact(
        **metadata.model_dump(),
        prompt="Final image prompt.",
        generator_identity="codex-imagegen-built-in",
        generation_attempt=1,
        validation_result=image_review,
    )
    source_path = post_dir / "source.json"
    source_path.write_text(source.model_dump_json())
    brand_path = tmp_path / "content/brand.md"
    brand_path.parent.mkdir(parents=True)
    brand_path.write_text("Professional, precise, no hype.")
    draft_path = post_dir / "draft.json"
    draft_path.write_text(draft.model_dump_json())
    image_artifact_path = post_dir / "image-artifact.json"
    image_artifact_path.write_text(image.model_dump_json())
    queue_path = tmp_path / "content/urls.md"
    queue_path.write_text(queue_contents)
    queue_item = QueueItem(
        id="post-1",
        original_url="https://example.com/article",
        normalized_url="https://example.com/article",
        checked=False,
        source_line=3,
    )
    context = HumanReviewContext(
        post_id="post-1",
        queue_item=queue_item,
        source=source,
        draft=draft,
        deterministic_validation=validation,
        semantic_review=semantic,
        image=image,
        source_path=source_path,
        brand_path=brand_path,
        draft_path=draft_path,
        image_artifact_path=image_artifact_path,
    )
    store = StateStore(output / "state.json")
    store.save(
        PipelineState(
            jobs={
                "post-1": JobRecord(
                    post_id="post-1",
                    normalized_url="https://example.com/article",
                    stage=JobStage.HUMAN_REVIEW,
                )
            },
            active_job_id="post-1",
        )
    )
    text_reviewer = FakeTextReviewer(text_reviews or [])
    image_reviewer = FakeImageReviewer(image_reviews or [])
    opener = FakeOpener()
    service = ReviewService(
        workspace=tmp_path,
        artifacts=ArtifactRepository(tmp_path, output),
        state_store=store,
        queue_path=queue_path,
        text_reviewer=text_reviewer,
        image_reviewer=image_reviewer,
        opener=opener,
        publisher=publisher,
    )
    return context, service, text_reviewer, image_reviewer, opener


def test_rich_screen_shows_provenance_copy_warnings_and_image_without_opening(
    tmp_path: Path,
) -> None:
    context, _, _, _, opener = _setup(tmp_path)

    screen = render_review_screen(context)

    assert "Local workflow evidence" in screen
    assert "https://example.com/article" in screen
    assert "general_http" in screen
    assert "Local stages preserve evidence." in screen
    assert "Review remains human-controlled." in screen
    assert context.draft.x in screen
    assert "linkedin_target_length" in screen
    assert context.image.path in screen
    assert opener.paths == []


@pytest.mark.asyncio
async def test_open_image_requires_explicit_action(tmp_path: Path) -> None:
    context, service, _, _, opener = _setup(tmp_path)

    updated, outcome = await service.apply(context, ReviewAction.OPEN_IMAGE)

    assert updated == context
    assert outcome.action is ReviewAction.OPEN_IMAGE
    assert opener.paths == [tmp_path / context.image.path]
    assert service.state_store.load().jobs["post-1"].stage is JobStage.HUMAN_REVIEW


@pytest.mark.asyncio
async def test_noninteractive_review_requires_post_id_and_action(
    tmp_path: Path,
) -> None:
    context, service, _, _, _ = _setup(tmp_path)

    with pytest.raises(HumanReviewError, match="explicit post ID and action"):
        await run_review(context, service=service, interactive=False)
    with pytest.raises(HumanReviewError, match="does not match"):
        await run_review(
            context,
            service=service,
            interactive=False,
            explicit_post_id="other",
            explicit_action=ReviewAction.REJECT,
        )


@pytest.mark.asyncio
async def test_noninteractive_review_applies_fully_explicit_action(
    tmp_path: Path,
) -> None:
    context, service, _, _, _ = _setup(tmp_path)

    outcome = await run_review(
        context,
        service=service,
        interactive=False,
        explicit_post_id="post-1",
        explicit_action=ReviewAction.REJECT,
    )

    assert outcome.action is ReviewAction.REJECT
    assert service.state_store.load().jobs["post-1"].stage is JobStage.REJECTED


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("action", "feedback", "expected_stage"),
    [
        (ReviewAction.REGENERATE_TEXT, "Make it clearer.", JobStage.VALIDATING),
        (
            ReviewAction.REGENERATE_IMAGE,
            "Use a simpler scene.",
            JobStage.GENERATING_IMAGE,
        ),
        (ReviewAction.SKIP, None, JobStage.PENDING),
        (ReviewAction.REJECT, None, JobStage.REJECTED),
        (ReviewAction.SAVE_QUIT, None, JobStage.HUMAN_REVIEW),
    ],
)
async def test_review_actions_persist_exact_resume_stage(
    tmp_path: Path,
    action: ReviewAction,
    feedback: str | None,
    expected_stage: JobStage,
) -> None:
    context, service, _, _, _ = _setup(tmp_path)

    _, outcome = await service.apply(context, action, feedback=feedback)

    state = service.state_store.load()
    assert outcome.stage is expected_stage
    assert state.jobs["post-1"].stage is expected_stage
    if action is ReviewAction.SAVE_QUIT:
        assert next_resumable_job(state).stage is JobStage.HUMAN_REVIEW  # type: ignore[union-attr]
    if feedback:
        feedback_name = (
            "human-text-regeneration.json"
            if action is ReviewAction.REGENERATE_TEXT
            else "human-image-regeneration.json"
        )
        persisted = json.loads(
            (tmp_path / "output/posts/post-1" / feedback_name).read_text()
        )
        assert persisted["feedback"] == feedback


@pytest.mark.asyncio
@pytest.mark.parametrize("raised", [EOFError(), KeyboardInterrupt()])
async def test_eof_and_ctrl_c_save_without_leaving_human_review(
    tmp_path: Path,
    raised: BaseException,
) -> None:
    context, service, _, _, _ = _setup(tmp_path)

    def interrupted_input(_: str) -> str:
        raise raised

    outcome = await run_review(
        context,
        service=service,
        interactive=True,
        read=interrupted_input,
        console=Console(file=None, force_terminal=False),
    )

    assert outcome.action is ReviewAction.SAVE_QUIT
    assert service.state_store.load().jobs["post-1"].stage is JobStage.HUMAN_REVIEW


@pytest.mark.asyncio
async def test_editor_failure_preserves_original_draft_and_stage(
    tmp_path: Path,
) -> None:
    context, service, _, _, _ = _setup(tmp_path)

    with pytest.raises(HumanReviewError, match="editor failed"):
        await service.apply(
            context,
            ReviewAction.EDIT,
            editor=FakeEditor(failure="editor failed"),
        )

    assert context.draft_path.read_text() == context.draft.model_dump_json()
    assert service.state_store.load().jobs["post-1"].stage is JobStage.HUMAN_REVIEW


@pytest.mark.asyncio
async def test_every_edit_is_deterministic_and_material_edits_are_semantic(
    tmp_path: Path,
) -> None:
    context, service, text_reviewer, _, _ = _setup(
        tmp_path,
        text_reviews=[_semantic(passed=True)],
    )

    def material_edit(path: Path) -> None:
        edited = context.draft.model_copy(
            update={"x": "Human-edited local workflow copy."}
        )
        path.write_text(edited.model_dump_json())

    updated, outcome = await service.apply(
        context,
        ReviewAction.EDIT,
        editor=FakeEditor(update=material_edit),
    )

    assert outcome.stage is JobStage.HUMAN_REVIEW
    assert updated.draft.x == "Human-edited local workflow copy."
    assert len(text_reviewer.calls) == 1
    validation = json.loads(
        (tmp_path / "output/posts/post-1/human-edit-validation.json").read_text()
    )
    assert validation["passed"] is True
    assert json.loads(updated.draft_path.read_text())["x"] == updated.draft.x

    def whitespace_edit(path: Path) -> None:
        edited = updated.draft.model_copy(update={"x": f"  {updated.draft.x}\n"})
        path.write_text(edited.model_dump_json())

    whitespace_updated, _ = await service.apply(
        updated,
        ReviewAction.EDIT,
        editor=FakeEditor(update=whitespace_edit),
    )
    assert whitespace_updated.draft.x.startswith("  ")
    assert len(text_reviewer.calls) == 1


@pytest.mark.asyncio
async def test_invalid_edit_fails_revalidation_without_replacing_draft(
    tmp_path: Path,
) -> None:
    context, service, text_reviewer, _, _ = _setup(tmp_path)

    def invalid_edit(path: Path) -> None:
        path.write_text(
            context.draft.model_copy(
                update={"x": "Read example.com before approval."}
            ).model_dump_json()
        )

    with pytest.raises(HumanReviewError, match="deterministic validation"):
        await service.apply(
            context,
            ReviewAction.EDIT,
            editor=FakeEditor(update=invalid_edit),
        )

    assert text_reviewer.calls == []
    assert json.loads(context.draft_path.read_text())["x"] == context.draft.x


@pytest.mark.asyncio
async def test_semantically_rejected_edit_preserves_original_draft(
    tmp_path: Path,
) -> None:
    context, service, text_reviewer, _, _ = _setup(
        tmp_path,
        text_reviews=[_semantic(passed=False)],
    )

    def unsupported_edit(path: Path) -> None:
        path.write_text(
            context.draft.model_copy(
                update={"x": "This workflow guarantees a tenfold improvement."}
            ).model_dump_json()
        )

    with pytest.raises(HumanReviewError, match="semantic review"):
        await service.apply(
            context,
            ReviewAction.EDIT,
            editor=FakeEditor(update=unsupported_edit),
        )

    assert len(text_reviewer.calls) == 1
    assert json.loads(context.draft_path.read_text())["x"] == context.draft.x


@pytest.mark.asyncio
async def test_image_replacement_is_copied_validated_and_semantically_reviewed(
    tmp_path: Path,
) -> None:
    context, service, _, image_reviewer, _ = _setup(
        tmp_path,
        image_reviews=[_image_review(passed=True)],
    )
    replacement = tmp_path / "replacement.png"
    _write_png(replacement, color=(120, 30, 50))

    updated, outcome = await service.apply(
        context,
        ReviewAction.REPLACE_IMAGE,
        replacement_path=replacement,
    )

    assert outcome.stage is JobStage.HUMAN_REVIEW
    assert len(image_reviewer.calls) == 1
    assert updated.image.generator_identity == "human-replacement"
    assert updated.image.sha256 != context.image.sha256
    assert json.loads(updated.image_artifact_path.read_text())["sha256"] == (
        updated.image.sha256
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["local", "semantic"])
async def test_invalid_image_replacement_preserves_existing_image(
    tmp_path: Path,
    failure: str,
) -> None:
    reviews = [_image_review(passed=False)] if failure == "semantic" else []
    context, service, _, image_reviewer, _ = _setup(
        tmp_path,
        image_reviews=reviews,
    )
    original_bytes = (tmp_path / context.image.path).read_bytes()
    replacement = tmp_path / "replacement.png"
    if failure == "local":
        replacement.write_bytes(b"corrupt")
    else:
        _write_png(replacement, color=(120, 30, 50))

    with pytest.raises(HumanReviewError, match="Replacement image"):
        await service.apply(
            context,
            ReviewAction.REPLACE_IMAGE,
            replacement_path=replacement,
        )

    assert (tmp_path / context.image.path).read_bytes() == original_bytes
    assert len(image_reviewer.calls) == (1 if failure == "semantic" else 0)


@pytest.mark.asyncio
async def test_accept_writes_immutable_manifest_checks_queue_and_approves_state(
    tmp_path: Path,
) -> None:
    context, service, _, _, _ = _setup(tmp_path)
    state = add_job(
        service.state_store.load(),
        "post-2",
        "https://example.com/next",
    )
    service.state_store.save(state)

    _, outcome = await service.apply(context, ReviewAction.ACCEPT)

    assert outcome.sync_warning is None
    assert service.state_store.load().jobs["post-1"].stage is JobStage.APPROVED
    assert "- [x] https://example.com/article" in service.queue_path.read_text()
    manifest_path = tmp_path / "output/posts/post-1/approved-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    assert manifest["post_id"] == "post-1"
    assert manifest["draft"]["x"] == context.draft.x
    assert manifest["image"]["sha256"] == context.image.sha256
    assert next_resumable_job(service.state_store.load()).post_id == "post-2"  # type: ignore[union-attr]
    with pytest.raises(HumanReviewError, match="immutable"):
        await service.write_approved_manifest(context)


@pytest.mark.asyncio
async def test_accept_publishes_exact_approved_package_and_writes_separate_receipts(
    tmp_path: Path,
) -> None:
    publisher = FakePublisher(
        PublicationResult(
            attempts=(
                PublicationAttempt(
                    platform=PublicationPlatform.X,
                    state=PublicationState.PUBLISHED,
                    remote_id="x-post",
                    remote_url="https://x.example/post",
                ),
                PublicationAttempt(
                    platform=PublicationPlatform.LINKEDIN,
                    state=PublicationState.PUBLISHED,
                    remote_id="urn:li:share:post",
                ),
            )
        )
    )
    context, service, _, _, _ = _setup(tmp_path, publisher=publisher)

    await service.apply(context, ReviewAction.ACCEPT)

    assert publisher.requests == [
        PublicationRequest(
            post_id="post-1",
            x_text=context.draft.x,
            linkedin_text=context.draft.linkedin,
            image_bytes=(tmp_path / context.image.path).read_bytes(),
        )
    ]
    manifest = json.loads(
        (tmp_path / "output/posts/post-1/approved-manifest.json").read_text()
    )
    assert "publication" not in manifest
    outcomes = json.loads(
        (tmp_path / "output/posts/post-1/publication-outcomes.json").read_text()
    )
    assert [outcome["state"] for outcome in outcomes["outcomes"]] == [
        "published",
        "published",
    ]
    assert (
        json.loads(
            (tmp_path / "output/posts/post-1/x-publication-receipt.json").read_text()
        )["remote_id"]
        == "x-post"
    )
    assert (
        json.loads(
            (
                tmp_path / "output/posts/post-1/linkedin-publication-receipt.json"
            ).read_text()
        )["remote_id"]
        == "urn:li:share:post"
    )


@pytest.mark.asyncio
async def test_checkbox_failure_preserves_approval_with_recoverable_warning(
    tmp_path: Path,
) -> None:
    context, service, _, _, _ = _setup(
        tmp_path,
        queue_contents="# Queue\n\n- [ ] https://example.com/different\n",
    )

    _, outcome = await service.apply(context, ReviewAction.ACCEPT)

    job = service.state_store.load().jobs["post-1"]
    assert job.stage is JobStage.APPROVED
    assert outcome.sync_warning is not None
    assert "checkbox" in outcome.sync_warning.lower()
    assert job.last_error == outcome.sync_warning
