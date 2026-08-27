"""Tests for the local command-line entry point."""

from pathlib import Path

from typer.testing import CliRunner

from social_media_agent.cli import app
from social_media_agent.models import JobStage, PipelineState
from social_media_agent.state import StateStore, add_job, transition_job

runner = CliRunner()


def test_help_describes_local_draft_workflow() -> None:
    """The root command should explain its local-only product boundary."""
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "Generate and approve social-media drafts locally" in result.stdout


def test_status_command_is_available(tmp_path: Path) -> None:
    """The foundation should expose the planned read-only status command."""
    result = runner.invoke(app, ["-C", str(tmp_path), "status"])

    assert result.exit_code == 0
    assert "No pipeline state found" in result.stdout


def test_status_reports_existing_state_path(tmp_path: Path) -> None:
    """Status should summarize persisted job stages."""
    state_path = tmp_path / "output" / "state.json"
    state = add_job(PipelineState(), "post-1", "https://example.com/post")
    StateStore(state_path).save(state)

    result = runner.invoke(app, ["-C", str(tmp_path), "status"])

    assert result.exit_code == 0
    assert "Total jobs: 1" in result.stdout
    assert "pending: 1" in result.stdout


def test_resume_reports_the_next_persisted_job(tmp_path: Path) -> None:
    """Resume should identify the exact job and stage selected for continuation."""
    state_path = tmp_path / "output" / "state.json"
    state = add_job(PipelineState(), "post-1", "https://example.com/post")
    StateStore(state_path).save(state)

    result = runner.invoke(app, ["-C", str(tmp_path), "resume"])

    assert result.exit_code == 0
    assert "post-1" in result.stdout
    assert "pending" in result.stdout


def test_resume_is_safe_when_no_jobs_exist(tmp_path: Path) -> None:
    """A fresh workspace should have nothing to resume."""
    result = runner.invoke(app, ["-C", str(tmp_path), "resume"])

    assert result.exit_code == 0
    assert "No resumable jobs" in result.stdout


def test_phase_7_exposes_complete_local_command_surface() -> None:
    """Cutover should expose every planned local workflow command."""
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    for command in ("run", "resume", "status", "retry-failed", "review"):
        assert command in result.stdout


def test_retry_failed_restores_the_recorded_stage(tmp_path: Path) -> None:
    """The explicit retry command should restore exactly the failed operation."""
    state_path = tmp_path / "output" / "state.json"
    state = add_job(PipelineState(), "post-1", "https://example.com/post")
    state = transition_job(state, "post-1", JobStage.EXTRACTING)
    state = transition_job(state, "post-1", JobStage.FAILED)
    StateStore(state_path).save(state)

    result = runner.invoke(
        app,
        ["-C", str(tmp_path), "retry-failed", "post-1"],
    )

    restored = StateStore(state_path).load().jobs["post-1"]
    assert result.exit_code == 0
    assert "Restored failed jobs: 1" in result.stdout
    assert restored.stage is JobStage.EXTRACTING
    assert restored.attempts == {"extracting": 1}
