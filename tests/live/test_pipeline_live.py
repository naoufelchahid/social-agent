"""Manually opted-in complete live workflow smoke test."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from social_media_agent.config import Settings
from social_media_agent.models import JobStage
from social_media_agent.pipeline import build_local_coordinator
from social_media_agent.review import ReviewAction

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(
        not os.getenv("SOCIAL_AGENT_LIVE_PIPELINE_URL"),
        reason="set SOCIAL_AGENT_LIVE_PIPELINE_URL to run the live workflow smoke test",
    ),
]


@pytest.mark.asyncio
async def test_live_url_reaches_local_human_review_with_image(tmp_path: Path) -> None:
    """Use real extraction and local agents, stopping before human acceptance."""
    url = os.environ["SOCIAL_AGENT_LIVE_PIPELINE_URL"]
    content_path = tmp_path / "content"
    content_path.mkdir()
    queue_path = content_path / "urls.md"
    queue_path.write_text(f"# Live smoke\n\n- [ ] {url}\n", encoding="utf-8")
    source_brand = Path(__file__).parents[2] / "content/brand.md"
    brand_path = content_path / "brand.md"
    brand_path.write_text(source_brand.read_text(encoding="utf-8"), encoding="utf-8")
    output_path = tmp_path / "output"
    settings = Settings(
        workspace=tmp_path,
        input_path=queue_path,
        brand_path=brand_path,
        output_path=output_path,
        state_path=output_path / "state.json",
        firecrawl_api_key=os.getenv("FIRECRAWL_API_KEY"),
        github_token=os.getenv("GITHUB_TOKEN"),
    )
    coordinator = build_local_coordinator(
        settings,
        interactive_review=False,
        explicit_action=ReviewAction.SAVE_QUIT,
    )

    result = await coordinator.run()

    job = next(iter(coordinator.state_store.load().jobs.values()))
    assert result.interrupted is False
    assert job.stage is JobStage.HUMAN_REVIEW
    assert (output_path / "posts" / job.post_id / "image.png").is_file()
