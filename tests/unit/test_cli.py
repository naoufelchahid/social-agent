"""Tests for the local command-line entry point."""

from pathlib import Path

from typer.testing import CliRunner

from social_media_agent.cli import app
from social_media_agent.models import JobStage, PipelineState
from social_media_agent.research_intake import ResearchCandidate, ResearchCandidateStore
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
    for command in (
        "run",
        "resume",
        "status",
        "retry-failed",
        "review",
        "connect",
        "research-intake",
        "promote-candidate",
        "workspace",
    ):
        assert command in result.stdout


def test_connect_requires_the_selected_platform_registration() -> None:
    """Onboarding fails before opening a browser when registration is absent."""
    result = runner.invoke(app, ["connect", "--platform", "x"])

    assert result.exit_code == 1
    assert "X_CLIENT_ID" in result.stderr
    assert "X_REDIRECT_URI" in result.stderr


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


def test_promote_candidate_command_requires_explicit_candidate_id(
    tmp_path: Path,
) -> None:
    """The operator can promote one reviewed candidate through the CLI boundary."""
    candidates_path = tmp_path / "content" / "candidates.md"
    queue_path = tmp_path / "content" / "urls.md"
    queue_path.parent.mkdir(parents=True)
    queue_path.write_text("# Social media queue\n", encoding="utf-8")
    ResearchCandidateStore(candidates_path).save(
        [
            ResearchCandidate.model_validate(
                {
                    "candidate_id": "candidate-001",
                    "canonical_url": "https://example.com/article",
                    "source_family": "publication",
                    "title": "A useful article",
                    "discovered_at": "2026-08-28T00:00:00Z",
                    "evidence_notes": ["Grounded public evidence."],
                    "angle": "Prioriser un workflow.",
                    "professional_use_case": "Aider un COO à décider.",
                    "audience": "Dirigeants de PME",
                    "score": 8,
                    "score_rationale": "Utile et fiable.",
                }
            )
        ]
    )

    result = runner.invoke(
        app, ["-C", str(tmp_path), "promote-candidate", "candidate-001"]
    )

    assert result.exit_code == 0
    assert "Promoted candidate: candidate-001" in result.stdout
    assert "https://example.com/article" in queue_path.read_text(encoding="utf-8")
