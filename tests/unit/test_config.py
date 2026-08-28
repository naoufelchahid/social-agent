"""Tests for application configuration."""

from pathlib import Path

from pytest import MonkeyPatch

from social_media_agent.config import Settings


def test_settings_use_workspace_relative_defaults(tmp_path: Path) -> None:
    """Default paths should remain portable with the worktree."""
    settings = Settings.from_workspace(tmp_path)

    assert settings.workspace == tmp_path.resolve()
    assert settings.input_path == tmp_path.resolve() / "content" / "urls.md"
    assert settings.brand_path == tmp_path.resolve() / "content" / "brand.md"
    assert settings.output_path == tmp_path.resolve() / "output"
    assert settings.state_path == tmp_path.resolve() / "output" / "state.json"
    assert settings.candidates_path == tmp_path.resolve() / "content" / "candidates.md"
    assert settings.research_sources_path == (
        tmp_path.resolve() / "content" / "research-sources.md"
    )


def test_environment_can_override_input_path(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    """A relative input override should resolve from the workspace."""
    monkeypatch.setenv("SOCIAL_AGENT_INPUT", "queues/custom.md")

    settings = Settings.from_workspace(tmp_path)

    assert settings.input_path == tmp_path.resolve() / "queues" / "custom.md"


def test_absolute_path_override_is_preserved(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    """An absolute override should not be rebased onto the workspace."""
    absolute_input = tmp_path / "outside" / "queue.md"
    monkeypatch.setenv("SOCIAL_AGENT_INPUT", str(absolute_input))

    settings = Settings.from_workspace(tmp_path / "workspace")

    assert settings.input_path == absolute_input
