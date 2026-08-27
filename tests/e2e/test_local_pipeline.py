"""Offline end-to-end proof for the complete local draft workflow."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest

from social_media_agent.agents import AgyWriter, CodexReviewer
from social_media_agent.artifacts import ArtifactRepository
from social_media_agent.commands import CommandRunner
from social_media_agent.config import Settings
from social_media_agent.extraction import ExtractionDispatcher, ExtractionRequest
from social_media_agent.images import CodexImageGenerator, CodexImageReviewer
from social_media_agent.models import (
    ExtractedSource,
    ExtractionMethod,
    JobStage,
)
from social_media_agent.pipeline import LocalPipelineWorkflow, PipelineCoordinator
from social_media_agent.review import ReviewAction
from social_media_agent.state import StateStore


class FakeFirecrawl:
    """Return bounded fixture evidence through the primary extraction path."""

    async def extract(self, request: ExtractionRequest) -> ExtractedSource:
        return ExtractedSource(
            canonical_url=request.normalized_url,
            source_type=request.source_type,
            title="Durable local content workflows",
            author="Fixture Author",
            content=(
                "A sequential local workflow persists evidence after extraction, "
                "drafting, independent review, image validation, and human approval."
            ),
            metadata={"fixture": True},
            extraction_method=ExtractionMethod.FIRECRAWL,
        )


def _install_fake_agents(tmp_path: Path) -> Path:
    fixture = Path(__file__).parents[1] / "fixtures/e2e/fake_local_agent.py"
    bin_path = tmp_path / "fake-bin"
    bin_path.mkdir()
    for name in ("agy", "codex"):
        target = bin_path / name
        shutil.copyfile(fixture, target)
        target.chmod(0o755)
    return bin_path


@pytest.mark.asyncio
async def test_complete_offline_workflow_approves_once_with_real_artifacts(
    tmp_path: Path,
) -> None:
    queue_path = tmp_path / "content/urls.md"
    queue_path.parent.mkdir(parents=True)
    queue_path.write_text(
        "# Queue\n\n- [ ] https://example.com/local-workflow\n",
        encoding="utf-8",
    )
    brand_path = tmp_path / "content/brand.md"
    brand_path.write_text(
        "Audience: technical teams\nVoice: precise and practical\n",
        encoding="utf-8",
    )
    output_path = tmp_path / "output"
    settings = Settings(
        workspace=tmp_path,
        input_path=queue_path,
        brand_path=brand_path,
        output_path=output_path,
        state_path=output_path / "state.json",
    )
    artifacts = ArtifactRepository(tmp_path, output_path)
    state_store = StateStore(settings.state_path)
    fake_bin = _install_fake_agents(tmp_path)
    source_environment = dict(os.environ)
    source_environment["PATH"] = f"{fake_bin}:{source_environment['PATH']}"
    runner = CommandRunner(
        workspace=tmp_path,
        source_environment=source_environment,
    )
    extractor = ExtractionDispatcher(
        firecrawl=FakeFirecrawl(),
        fallbacks={},
    )
    writer = AgyWriter(workspace=tmp_path, artifacts=artifacts, runner=runner)
    text_reviewer = CodexReviewer(
        workspace=tmp_path,
        artifacts=artifacts,
        runner=runner,
    )
    image_generator = CodexImageGenerator(
        workspace=tmp_path,
        artifacts=artifacts,
        runner=runner,
    )
    image_reviewer = CodexImageReviewer(
        workspace=tmp_path,
        artifacts=artifacts,
        runner=runner,
    )
    workflow = LocalPipelineWorkflow(
        settings=settings,
        queue_path=queue_path,
        state_store=state_store,
        artifacts=artifacts,
        extractor=extractor,
        writer=writer,
        text_reviewer=text_reviewer,
        image_generator=image_generator,
        image_reviewer=image_reviewer,
        interactive_review=False,
        explicit_action=ReviewAction.ACCEPT,
    )
    coordinator = PipelineCoordinator(
        state_store=state_store,
        queue_path=queue_path,
        workflow=workflow,
    )

    first = await coordinator.run()
    call_log = output_path / "fake-agent-calls.jsonl"
    calls_after_first_run = call_log.read_text(encoding="utf-8").splitlines()
    second = await coordinator.run()

    state = state_store.load()
    job = next(iter(state.jobs.values()))
    post_path = output_path / "posts" / job.post_id
    manifest = json.loads((post_path / "approved-manifest.json").read_text())
    assert first.approved == 1
    assert second.approved == 0
    assert job.stage is JobStage.APPROVED
    assert queue_path.read_text(encoding="utf-8").count("- [x]") == 1
    assert (post_path / "image.png").is_file()
    assert manifest["source"]["extraction_method"] == "firecrawl"
    assert manifest["image"]["generator_identity"] == "codex-imagegen-built-in"
    assert call_log.read_text(encoding="utf-8").splitlines() == calls_after_first_run
    assert [json.loads(line)["identity"] for line in calls_after_first_run] == [
        "agy",
        "codex",
        "codex",
        "codex",
    ]
