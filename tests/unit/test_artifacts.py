"""Tests for per-post artifact persistence."""

from pathlib import Path

import pytest

from social_media_agent.artifacts import ArtifactRepository
from social_media_agent.errors import PipelineStateError


def test_repository_writes_text_and_json_inside_post_directory(tmp_path: Path) -> None:
    """Artifacts should be durable and addressed relative to the workspace."""
    repository = ArtifactRepository(tmp_path, tmp_path / "output")

    text_path = repository.write_text("post-1", "source.md", "evidence")
    json_path = repository.write_json("post-1", "source.json", {"title": "Post"})

    assert text_path == Path("output/posts/post-1/source.md")
    assert json_path == Path("output/posts/post-1/source.json")
    assert (tmp_path / text_path).read_text(encoding="utf-8") == "evidence"
    assert (tmp_path / json_path).read_text(encoding="utf-8").endswith("\n")


@pytest.mark.parametrize("name", ["../escape.json", "/tmp/escape.json", "nested/file"])
def test_repository_rejects_unsafe_artifact_names(tmp_path: Path, name: str) -> None:
    """An artifact name must not escape or introduce an unexpected hierarchy."""
    repository = ArtifactRepository(tmp_path, tmp_path / "output")

    with pytest.raises(PipelineStateError):
        repository.write_text("post-1", name, "unsafe")
