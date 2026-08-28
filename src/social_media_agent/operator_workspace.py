"""Local-only operator workspace seam for browser and other presentations."""

from __future__ import annotations

import asyncio
import base64
import json
import os
import re
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import Lock, Thread
from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, model_validator

from social_media_agent.commands import CommandRunner
from social_media_agent.config import Settings
from social_media_agent.errors import SocialAgentError
from social_media_agent.models import ImageArtifact, JobStage
from social_media_agent.oauth import ConnectPlatform, OAuthSettings, connect
from social_media_agent.pipeline import build_local_coordinator, build_local_workflow
from social_media_agent.research_intake import (
    CandidateStatus,
    CodexResearchEvaluator,
    ResearchCandidateStore,
    ResearchIntakeService,
    promote_candidate,
    write_run_report,
)
from social_media_agent.review import ReviewAction
from social_media_agent.state import (
    RunLock,
    StateStore,
    next_resumable_job,
    restore_job,
)

_POST_ID = re.compile(r"^[A-Za-z0-9_-]+$")


class WorkspaceCommand(BaseModel):
    """Closed, browser-safe command contract for one operator action."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    action: Literal[
        "run",
        "resume",
        "retry_failed",
        "promote_candidate",
        "research_intake",
        "review",
        "connect",
    ]
    post_id: str | None = None
    candidate_id: str | None = None
    review_action: ReviewAction | None = None
    feedback: str | None = None
    replacement_image_base64: str | None = None
    platform: Literal["x", "linkedin", "all"] | None = None

    @model_validator(mode="after")
    def validate_action_fields(self) -> WorkspaceCommand:
        if self.action == "promote_candidate" and not self.candidate_id:
            raise ValueError("Candidate promotion requires a candidate ID")
        if self.action == "review":
            if not self.post_id or self.review_action is None:
                raise ValueError("Review requires a post ID and review action")
            if (
                self.review_action
                in {
                    ReviewAction.REGENERATE_TEXT,
                    ReviewAction.REGENERATE_IMAGE,
                }
                and not (self.feedback or "").strip()
            ):
                raise ValueError("Regeneration requires non-empty feedback")
            if self.review_action is ReviewAction.REPLACE_IMAGE and not (
                self.replacement_image_base64
            ):
                raise ValueError("Image replacement requires an explicit file")
        if self.action == "retry_failed" and self.post_id is not None:
            _validate_post_id(self.post_id)
        if self.action == "review" and self.post_id is not None:
            _validate_post_id(self.post_id)
        return self


@dataclass(frozen=True)
class _ActiveCommand:
    action: str
    status: str
    message: str | None = None


class OperatorWorkspace:
    """Deep application module hiding local workflow storage and execution details."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._lock = Lock()
        self._active: _ActiveCommand | None = None

    def snapshot(self, *, candidate_status: str | None = None) -> dict[str, Any]:
        """Return a serializable, secret-free view of persisted local workflow facts."""
        status = _candidate_status(candidate_status)
        state = StateStore(self._settings.state_path).load()
        candidates = ResearchCandidateStore(self._settings.candidates_path).load()
        if status is not None:
            candidates = [
                candidate for candidate in candidates if candidate.status is status
            ]
        posts = [
            {
                "post_id": job.post_id,
                "url": job.normalized_url,
                "stage": job.stage.value,
                "resume_stage": job.resume_stage.value if job.resume_stage else None,
                "failed_stage": job.failed_stage.value if job.failed_stage else None,
                "last_error": job.last_error,
                "updated_at": job.updated_at.isoformat(),
                "review": self._review_snapshot(job.post_id)
                if job.stage is JobStage.HUMAN_REVIEW
                else None,
                "publication": self._publication_snapshot(job.post_id),
            }
            for job in sorted(state.jobs.values(), key=lambda value: value.created_at)
        ]
        resumable = next_resumable_job(state)
        with self._lock:
            active = self._active
        command = active or self._persisted_command()
        return {
            "active_post_id": state.active_job_id,
            "counts": dict(Counter(job["stage"] for job in posts)),
            "posts": posts,
            "next_resumable": (
                {"post_id": resumable.post_id, "stage": resumable.stage.value}
                if resumable is not None
                else None
            ),
            "command": (
                {
                    "action": command.action,
                    "status": command.status,
                    "message": command.message,
                }
                if command is not None
                else None
            ),
            "candidates": [
                candidate.model_dump(mode="json") for candidate in candidates
            ],
            "research": {
                "sources": _safe_text(self._settings.research_sources_path),
                "latest_report": _safe_text(
                    self._settings.output_path / "research-intake" / "latest-report.md"
                ),
            },
            "oauth": {
                "x_configured": bool(
                    self._settings.x_client_id and self._settings.x_redirect_uri
                ),
                "linkedin_configured": bool(
                    self._settings.linkedin_client_id
                    and self._settings.linkedin_redirect_uri
                ),
            },
        }

    def submit(self, payload: Mapping[str, object]) -> dict[str, object]:
        """Validate and execute or start exactly one explicit operator command."""
        command = WorkspaceCommand.model_validate(payload)
        if command.action in {"run", "resume", "research_intake", "connect"}:
            self._start(command)
            return {"ok": True, "message": f"Started {command.action}"}
        try:
            return self._perform(command)
        except (SocialAgentError, ValueError, OSError) as exc:
            return {"ok": False, "message": str(exc)}

    def image_path(self, post_id: str) -> Path:
        """Resolve only the validated image retained inside an existing post package."""
        _validate_post_id(post_id)
        post_directory = self._settings.output_path / "posts" / post_id
        artifact_path = post_directory / "image-artifact.json"
        if not post_directory.is_dir() or not artifact_path.is_file():
            raise ValueError("Post package image is unavailable")
        image = ImageArtifact.model_validate_json(
            artifact_path.read_text(encoding="utf-8")
        )
        candidate = (self._settings.workspace / image.path).resolve()
        try:
            candidate.relative_to(post_directory.resolve())
        except ValueError as exc:
            raise ValueError("Post package image is unavailable") from exc
        if not candidate.is_file() or candidate.suffix.lower() != ".png":
            raise ValueError("Post package image is unavailable")
        return candidate

    def _start(self, command: WorkspaceCommand) -> None:
        with self._lock:
            if self._active is not None:
                raise ValueError("A local workspace command is already running")
            self._active = _ActiveCommand(command.action, "running")
            self._write_command_status(self._active)
        Thread(target=self._run_background, args=(command,), daemon=True).start()

    def _run_background(self, command: WorkspaceCommand) -> None:
        try:
            result = self._perform(command)
            message = str(result["message"])
            state = _ActiveCommand(command.action, "completed", message)
        except (SocialAgentError, ValueError, OSError) as exc:
            state = _ActiveCommand(command.action, "failed", str(exc))
        with self._lock:
            self._active = None
            self._write_command_status(state)

    def _perform(self, command: WorkspaceCommand) -> dict[str, object]:
        if command.action == "run":
            coordinator = build_local_coordinator(self._settings)
            with RunLock(self._settings.output_path / ".run.lock"):
                result = asyncio.run(coordinator.run())
            return {"ok": True, "message": _result_message(result)}
        if command.action == "resume":
            coordinator = build_local_coordinator(self._settings)
            with RunLock(self._settings.output_path / ".run.lock"):
                result = asyncio.run(coordinator.resume())
            return {"ok": True, "message": _result_message(result)}
        if command.action == "retry_failed":
            return self._retry_failed(command.post_id)
        if command.action == "promote_candidate":
            assert command.candidate_id is not None
            promoted = promote_candidate(
                candidate_id=command.candidate_id,
                candidates_path=self._settings.candidates_path,
                queue_path=self._settings.input_path,
            )
            return {"ok": True, "message": f"Promoted {promoted.candidate_id}"}
        if command.action == "research_intake":
            return self._research_intake()
        if command.action == "review":
            assert command.post_id is not None and command.review_action is not None
            replacement = self._replacement_path(command.replacement_image_base64)
            workflow = build_local_workflow(self._settings)
            with RunLock(self._settings.output_path / ".run.lock"):
                outcome = asyncio.run(
                    workflow.apply_review_action(
                        post_id=command.post_id,
                        action=command.review_action,
                        feedback=command.feedback,
                        replacement_path=replacement,
                    )
                )
            return {"ok": True, "message": outcome.message}
        if command.action == "connect":
            selected: ConnectPlatform = command.platform or "all"
            connect(
                selected,
                OAuthSettings(
                    x_client_id=self._settings.x_client_id,
                    x_redirect_uri=self._settings.x_redirect_uri,
                    linkedin_client_id=self._settings.linkedin_client_id,
                    linkedin_redirect_uri=self._settings.linkedin_redirect_uri,
                    linkedin_version=self._settings.linkedin_version,
                ),
            )
            return {"ok": True, "message": "OAuth connection completed"}
        raise ValueError("Unsupported workspace command")

    def _retry_failed(self, post_id: str | None) -> dict[str, object]:
        with RunLock(self._settings.output_path / ".run.lock"):
            store = StateStore(self._settings.state_path)
            state = store.load()
            failed = [
                job
                for job in state.jobs.values()
                if job.stage is JobStage.FAILED
                and (post_id is None or job.post_id == post_id)
            ]
            if post_id is not None and not failed:
                raise ValueError(f"No failed job found: {post_id}")
            for job in failed:
                state = restore_job(state, job.post_id)
            store.save(state)
        return {"ok": True, "message": f"Restored failed jobs: {len(failed)}"}

    def _research_intake(self) -> dict[str, object]:
        evaluator = CodexResearchEvaluator(
            workspace=self._settings.workspace,
            sources_path=self._settings.research_sources_path,
            brand_path=self._settings.brand_path,
            runner=CommandRunner(workspace=self._settings.workspace),
            schema_path=self._settings.output_path
            / "research-intake"
            / "schema-v1.json",
        )
        with RunLock(self._settings.output_path / ".research-intake.lock"):
            result = asyncio.run(
                ResearchIntakeService(
                    candidates_path=self._settings.candidates_path,
                    evaluator=evaluator,
                ).run()
            )
            write_run_report(
                self._settings.output_path / "research-intake" / "latest-report.md",
                result,
            )
        return {"ok": True, "message": "Research intake completed"}

    def _replacement_path(self, encoded_image: str | None) -> Path | None:
        if encoded_image is not None:
            try:
                contents = base64.b64decode(encoded_image, validate=True)
            except ValueError as exc:
                raise ValueError("Replacement image upload is invalid") from exc
            if not contents or len(contents) > 10 * 1024 * 1024:
                raise ValueError("Replacement image upload is invalid")
            destination = self._settings.output_path / ".workspace-replacement.png"
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(contents)
            return destination
        return None

    def _persisted_command(self) -> _ActiveCommand | None:
        value = _safe_json(self._settings.output_path / "workspace-command.json")
        if not isinstance(value, dict):
            return None
        action = value.get("action")
        status = value.get("status")
        message = value.get("message")
        if not isinstance(action, str) or not isinstance(status, str):
            return None
        return _ActiveCommand(
            action, status, message if isinstance(message, str) else None
        )

    def _write_command_status(self, status: _ActiveCommand) -> None:
        path = self._settings.output_path / "workspace-command.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, delete=False
        ) as temporary:
            temporary_path = Path(temporary.name)
            temporary.write(
                json.dumps(
                    {
                        "action": status.action,
                        "status": status.status,
                        "message": status.message,
                    }
                )
            )
            temporary.flush()
            os.fsync(temporary.fileno())
        temporary_path.replace(path)

    def _review_snapshot(self, post_id: str) -> dict[str, object] | None:
        directory = self._settings.output_path / "posts" / post_id
        values = {
            name: _safe_json(directory / name)
            for name in (
                "source.json",
                "draft.json",
                "validation-report.json",
                "semantic-review.json",
            )
        }
        if not any(value is not None for value in values.values()):
            return None
        values["image_url"] = (
            f"/api/posts/{post_id}/image"
            if (directory / "image-artifact.json").is_file()
            else None
        )
        return values

    def _publication_snapshot(self, post_id: str) -> object:
        return _safe_json(
            self._settings.output_path / "posts" / post_id / "publication-outcomes.json"
        )


def _validate_post_id(value: str) -> None:
    if not _POST_ID.fullmatch(value):
        raise ValueError("Invalid post ID")


def _candidate_status(value: str | None) -> CandidateStatus | None:
    if value is None:
        return None
    try:
        return CandidateStatus(value)
    except ValueError as exc:
        raise ValueError(
            "Candidate status must be active, promoted, or expired"
        ) from exc


def _safe_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None


def _safe_json(path: Path) -> object | None:
    try:
        return cast(object, json.loads(path.read_text(encoding="utf-8")))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return None


def _result_message(result: object) -> str:
    return f"Workflow complete: {result}"
