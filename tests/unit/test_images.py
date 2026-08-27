"""Tests for mandatory Codex image generation and validation."""

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

import pytest
from PIL import Image
from pydantic import ValidationError

from social_media_agent.artifacts import ArtifactRepository
from social_media_agent.commands import CommandResult
from social_media_agent.errors import (
    ImageValidationError,
    ImageValidationExhaustedError,
)
from social_media_agent.images import (
    CodexImageGenerator,
    CodexImageReviewer,
    build_image_request,
    generate_validated_image,
    load_validated_image_artifact,
    render_image_prompt,
    validate_image_file,
)
from social_media_agent.models import (
    ImageGenerationRequest,
    ImageGenerationResult,
    ImageSemanticReview,
)


def _result(stdout: str) -> CommandResult:
    return CommandResult(
        arguments=("fake",),
        return_code=0,
        stdout=stdout,
        stderr="",
        duration_seconds=0.1,
    )


@dataclass
class FakeRunner:
    outcomes: list[CommandResult]
    calls: list[tuple[tuple[str, ...], dict[str, object]]] = field(default_factory=list)

    async def run(self, arguments: Sequence[str], **kwargs: object) -> CommandResult:
        self.calls.append((tuple(arguments), kwargs))
        return self.outcomes.pop(0)


def _write_png(path: Path, *, size: tuple[int, int] = (1536, 1024)) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, color=(31, 63, 95)).save(path, format="PNG")


def _generation_result(*, prompt: str = "final production prompt") -> dict[str, object]:
    return {
        "schema_version": 1,
        "path": "output/posts/post-1/image.png",
        "final_prompt": prompt,
        "generator_identity": "codex-imagegen-built-in",
    }


def _semantic_review(
    *, passed: bool, feedback: str | None = None
) -> ImageSemanticReview:
    return ImageSemanticReview(
        passed=passed,
        relevance=passed,
        no_unwanted_text=passed,
        no_logos=passed,
        no_watermarks=passed,
        consistent_with_post=passed,
        summary="Image passes." if passed else "Image is not relevant enough.",
        feedback=feedback,
    )


def test_image_request_defaults_to_versioned_editorial_landscape_schema() -> None:
    request = build_image_request(
        "A visible sequence of local pipeline stages connected by persisted artifacts."
    )

    assert request == ImageGenerationRequest(
        image_brief=(
            "A visible sequence of local pipeline stages connected by persisted "
            "artifacts."
        )
    )
    assert request.schema_version == 1
    assert (request.width, request.height) == (1536, 1024)
    assert request.use_case == "stylized-concept"
    assert request.style_medium == "editorial technical illustration"
    assert request.constraints == (
        "no embedded text",
        "no logos or trademarks",
        "no watermarks",
    )
    prompt = render_image_prompt(request)
    assert "Use case: stylized-concept" in prompt
    assert "1536x1024 landscape" in prompt
    assert "Primary request: A visible sequence" in prompt
    assert "no embedded text; no logos or trademarks; no watermarks" in prompt


def test_semantic_review_cannot_pass_with_a_failed_criterion() -> None:
    with pytest.raises(ValidationError):
        ImageSemanticReview(
            passed=True,
            relevance=True,
            no_unwanted_text=True,
            no_logos=False,
            no_watermarks=True,
            consistent_with_post=True,
            summary="Contradictory response.",
        )


@pytest.mark.asyncio
async def test_codex_generator_uses_imagegen_workspace_write_and_structured_result(
    tmp_path: Path,
) -> None:
    artifacts = ArtifactRepository(tmp_path, tmp_path / "output")
    runner = FakeRunner([_result(json.dumps(_generation_result()))])
    generator = CodexImageGenerator(
        workspace=tmp_path,
        artifacts=artifacts,
        runner=runner,
    )

    result = await generator.generate(
        post_id="post-1",
        request=build_image_request("A local workflow."),
        attempt=1,
    )

    assert result == ImageGenerationResult.model_validate(_generation_result())
    arguments, options = runner.calls[0]
    assert arguments[:6] == (
        "codex",
        "exec",
        "--ephemeral",
        "--sandbox",
        "workspace-write",
        "--skip-git-repo-check",
    )
    assert arguments[6] == "--output-schema"
    assert arguments[8:10] == ("-C", str(tmp_path))
    assert "$imagegen" in arguments[10]
    assert "output/posts/post-1/image.png" in arguments[10]
    assert "CODEX_HOME" in arguments[10]
    assert options == {"cwd": tmp_path, "timeout_seconds": 900.0}
    post_dir = tmp_path / "output/posts/post-1"
    assert (post_dir / "image-generation-request-1.json").exists()
    generation_schema = json.loads(
        (post_dir / "image-generation-schema-v1.json").read_text()
    )
    assert set(generation_schema["required"]) == set(generation_schema["properties"])
    assert (post_dir / "image-generation-prompt-1-v1.txt").exists()
    assert (post_dir / "image-generation-raw-1.txt").exists()
    assert json.loads((post_dir / "image-generation-result-1.json").read_text()) == (
        _generation_result()
    )


def test_image_file_validation_returns_integrity_metadata(tmp_path: Path) -> None:
    image_path = tmp_path / "output/posts/post-1/image.png"
    _write_png(image_path)

    metadata = validate_image_file(
        workspace=tmp_path,
        post_id="post-1",
        reported_path=Path("output/posts/post-1/image.png"),
    )

    assert metadata.path == "output/posts/post-1/image.png"
    assert metadata.mime_type == "image/png"
    assert (metadata.width, metadata.height) == (1536, 1024)
    assert metadata.size_bytes == image_path.stat().st_size
    assert metadata.sha256 == hashlib.sha256(image_path.read_bytes()).hexdigest()


@pytest.mark.parametrize(
    "case",
    ["outside", "missing", "symlink", "corrupt", "jpeg", "dimensions"],
)
def test_image_file_validation_rejects_unsafe_or_invalid_files(
    tmp_path: Path,
    case: str,
) -> None:
    post_dir = tmp_path / "output/posts/post-1"
    post_dir.mkdir(parents=True)
    reported = Path("output/posts/post-1/image.png")
    image_path = tmp_path / reported
    if case == "outside":
        reported = Path("output/posts/other/image.png")
        _write_png(tmp_path / reported)
    elif case == "symlink":
        target = tmp_path / "outside.png"
        _write_png(target)
        image_path.symlink_to(target)
    elif case == "corrupt":
        image_path.write_bytes(b"not an image")
    elif case == "jpeg":
        Image.new("RGB", (1536, 1024)).save(image_path, format="JPEG")
    elif case == "dimensions":
        _write_png(image_path, size=(1024, 1024))

    with pytest.raises(ImageValidationError):
        validate_image_file(
            workspace=tmp_path,
            post_id="post-1",
            reported_path=reported,
        )


@pytest.mark.asyncio
async def test_codex_image_reviewer_attaches_image_in_fresh_read_only_session(
    tmp_path: Path,
) -> None:
    artifacts = ArtifactRepository(tmp_path, tmp_path / "output")
    image_path = tmp_path / "output/posts/post-1/image.png"
    _write_png(image_path)
    draft_path = image_path.parent / "draft.json"
    draft_path.write_text('{"image_brief":"A local workflow"}')
    request_path = image_path.parent / "image-generation-request-1.json"
    request_path.write_text(build_image_request("A local workflow").model_dump_json())
    expected = _semantic_review(passed=True)
    runner = FakeRunner([_result(expected.model_dump_json())])
    reviewer = CodexImageReviewer(
        workspace=tmp_path,
        artifacts=artifacts,
        runner=runner,
    )

    review = await reviewer.review(
        post_id="post-1",
        image_path=image_path,
        draft_path=draft_path,
        request_path=request_path,
        attempt=1,
    )

    assert review == expected
    arguments, options = runner.calls[0]
    assert arguments[:5] == (
        "codex",
        "exec",
        "--ephemeral",
        "--sandbox",
        "read-only",
    )
    assert arguments[5] == "--skip-git-repo-check"
    assert arguments[6:8] == ("--image", str(image_path))
    assert "--output-schema" in arguments
    assert options == {"cwd": tmp_path, "timeout_seconds": 300.0}
    prompt = arguments[-1]
    for criterion in ("relevance", "text", "logos", "watermarks", "consistency"):
        assert criterion in prompt
    review_schema = json.loads(
        (tmp_path / "output/posts/post-1/image-review-schema-v1.json").read_text()
    )
    assert set(review_schema["required"]) == set(review_schema["properties"])


@dataclass
class FakeGenerator:
    workspace: Path
    payloads: list[bytes | None]
    calls: list[tuple[ImageGenerationRequest, int]] = field(default_factory=list)

    async def generate(
        self,
        *,
        post_id: str,
        request: ImageGenerationRequest,
        attempt: int,
    ) -> ImageGenerationResult:
        self.calls.append((request, attempt))
        image_path = self.workspace / f"output/posts/{post_id}/image.png"
        image_path.parent.mkdir(parents=True, exist_ok=True)
        payload = self.payloads.pop(0)
        if payload is None:
            image_path.write_bytes(b"corrupt")
        else:
            image_path.write_bytes(payload)
        return ImageGenerationResult.model_validate(
            _generation_result(prompt=f"final prompt {attempt}")
        )


@dataclass
class FakeImageReviewer:
    outcomes: list[ImageSemanticReview]
    calls: list[dict[str, object]] = field(default_factory=list)

    async def review(self, **kwargs: object) -> ImageSemanticReview:
        self.calls.append(kwargs)
        return self.outcomes.pop(0)


def _png_bytes(tmp_path: Path) -> bytes:
    path = tmp_path / "fixture.png"
    _write_png(path)
    return path.read_bytes()


@pytest.mark.asyncio
async def test_image_loop_regenerates_twice_then_persists_final_artifact(
    tmp_path: Path,
) -> None:
    png = _png_bytes(tmp_path)
    artifacts = ArtifactRepository(tmp_path, tmp_path / "output")
    draft_path = tmp_path / "output/posts/post-1/draft.json"
    draft_path.parent.mkdir(parents=True)
    draft_path.write_text('{"image_brief":"A local workflow"}')
    generator = FakeGenerator(tmp_path, [png, png, png])
    reviewer = FakeImageReviewer(
        [
            _semantic_review(passed=False, feedback="Make it more relevant."),
            _semantic_review(passed=False, feedback="Remove the visible label."),
            _semantic_review(passed=True),
        ]
    )

    artifact = await generate_validated_image(
        post_id="post-1",
        image_brief="A local workflow represented as visible sequential stages.",
        draft_path=draft_path,
        artifacts=artifacts,
        generator=generator,
        reviewer=reviewer,
    )

    assert [attempt for _, attempt in generator.calls] == [1, 2, 3]
    assert generator.calls[1][0].regeneration_feedback == "Make it more relevant."
    assert generator.calls[2][0].regeneration_feedback == ("Remove the visible label.")
    assert len(reviewer.calls) == 3
    assert artifact.prompt == "final prompt 3"
    assert artifact.generator_identity == "codex-imagegen-built-in"
    assert artifact.validation_result.passed is True
    assert artifact.sha256 == hashlib.sha256(png).hexdigest()
    artifact_path = tmp_path / "output/posts/post-1/image-artifact.json"
    assert json.loads(artifact_path.read_text()) == artifact.model_dump(mode="json")

    resumed = load_validated_image_artifact(
        workspace=tmp_path,
        post_id="post-1",
        artifact_path=artifact_path,
    )
    assert resumed == artifact


@pytest.mark.asyncio
async def test_image_loop_fails_after_three_invalid_local_files(tmp_path: Path) -> None:
    artifacts = ArtifactRepository(tmp_path, tmp_path / "output")
    draft_path = tmp_path / "output/posts/post-1/draft.json"
    draft_path.parent.mkdir(parents=True)
    draft_path.write_text('{"image_brief":"A local workflow"}')
    generator = FakeGenerator(tmp_path, [None, None, None])
    reviewer = FakeImageReviewer([])

    with pytest.raises(ImageValidationExhaustedError, match="two regenerations"):
        await generate_validated_image(
            post_id="post-1",
            image_brief="A local workflow.",
            draft_path=draft_path,
            artifacts=artifacts,
            generator=generator,
            reviewer=reviewer,
        )

    assert len(generator.calls) == 3
    assert reviewer.calls == []
    failure = json.loads(
        (tmp_path / "output/posts/post-1/image-validation-failure.json").read_text()
    )
    assert failure["schema_version"] == 1
    assert failure["attempts"] == 3
    assert failure["last_failure_stage"] == "file"


def test_resumption_rejects_an_image_changed_after_artifact_persistence(
    tmp_path: Path,
) -> None:
    image_path = tmp_path / "output/posts/post-1/image.png"
    _write_png(image_path)
    metadata = validate_image_file(
        workspace=tmp_path,
        post_id="post-1",
        reported_path=Path("output/posts/post-1/image.png"),
    )
    artifact_path = image_path.parent / "image-artifact.json"
    artifact = {
        "schema_version": 1,
        **metadata.model_dump(mode="json"),
        "prompt": "final prompt",
        "generator_identity": "codex-imagegen-built-in",
        "generation_attempt": 1,
        "validation_result": _semantic_review(passed=True).model_dump(mode="json"),
    }
    artifact_path.write_text(json.dumps(artifact))
    image_path.write_bytes(image_path.read_bytes() + b"tampered")

    with pytest.raises(ImageValidationError, match="integrity"):
        load_validated_image_artifact(
            workspace=tmp_path,
            post_id="post-1",
            artifact_path=artifact_path,
        )
