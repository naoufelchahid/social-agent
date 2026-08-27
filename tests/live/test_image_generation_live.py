"""Manually opted-in live Codex image-generation smoke test."""

import os
from pathlib import Path
from uuid import uuid4

import pytest

from social_media_agent.artifacts import ArtifactRepository
from social_media_agent.commands import CommandRunner
from social_media_agent.images import (
    CodexImageGenerator,
    CodexImageReviewer,
    generate_validated_image,
    load_validated_image_artifact,
)

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(
        os.environ.get("SOCIAL_AGENT_LIVE_IMAGE_TEST") != "1",
        reason="set SOCIAL_AGENT_LIVE_IMAGE_TEST=1 to run live Codex image generation",
    ),
]


@pytest.mark.asyncio
async def test_live_image_is_copied_into_project_and_survives_validation() -> None:
    workspace = Path.cwd().resolve()
    post_id = f"live-smoke-{uuid4().hex[:10]}"
    artifacts = ArtifactRepository(workspace, workspace / "output")
    runner = CommandRunner(workspace=workspace)
    generator = CodexImageGenerator(
        workspace=workspace,
        artifacts=artifacts,
        runner=runner,
    )
    reviewer = CodexImageReviewer(
        workspace=workspace,
        artifacts=artifacts,
        runner=runner,
    )
    post_dir = workspace / "output" / "posts" / post_id
    draft_path = post_dir / "draft.json"
    draft_path.parent.mkdir(parents=True)
    draft_path.write_text(
        '{"concept":"A local sequential workflow","linkedin":"Local stages.",'
        '"x":"Local stages.","image_brief":"Three connected workflow blocks."}'
    )

    artifact = await generate_validated_image(
        post_id=post_id,
        image_brief=(
            "Three simple connected blocks representing a local sequential workflow."
        ),
        draft_path=draft_path,
        artifacts=artifacts,
        generator=generator,
        reviewer=reviewer,
    )

    resumed = load_validated_image_artifact(
        workspace=workspace,
        post_id=post_id,
        artifact_path=post_dir / "image-artifact.json",
    )
    assert resumed == artifact
    assert artifact.path == f"output/posts/{post_id}/image.png"
