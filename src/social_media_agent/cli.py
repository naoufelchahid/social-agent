"""Local command-line interface."""

import asyncio
import webbrowser
from collections import Counter
from collections.abc import Coroutine
from pathlib import Path
from typing import Annotated, Any

import typer

from social_media_agent.commands import CommandRunner
from social_media_agent.config import Settings
from social_media_agent.errors import PipelineStateError, SocialAgentError
from social_media_agent.logging import configure_logging
from social_media_agent.models import JobStage
from social_media_agent.oauth import (
    ConnectPlatform,
    OAuthSettings,
    connect,
    format_exports,
)
from social_media_agent.operator_workspace import OperatorWorkspace
from social_media_agent.pipeline import PipelineRunResult, build_local_coordinator
from social_media_agent.research_intake import (
    CodexResearchEvaluator,
    ResearchIntakeService,
    promote_candidate,
    write_run_report,
)
from social_media_agent.review import ReviewAction
from social_media_agent.signals import InterruptionController
from social_media_agent.state import (
    RunLock,
    StateStore,
    next_resumable_job,
    restore_job,
)
from social_media_agent.workspace_web import build_workspace_server

app = typer.Typer(
    help="Generate and approve social-media drafts locally.",
    no_args_is_help=True,
)


@app.callback()
def main(
    ctx: typer.Context,
    workspace: Annotated[
        Path | None,
        typer.Option(
            "--workspace",
            "-C",
            file_okay=False,
            dir_okay=True,
            resolve_path=True,
            help="Repository workspace containing content and output directories.",
        ),
    ] = None,
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Enable debug logging."),
    ] = False,
) -> None:
    """Initialize settings shared by local workflow commands."""
    configure_logging(verbose)
    ctx.obj = Settings.from_workspace(workspace or Path.cwd())


@app.command()
def status(ctx: typer.Context) -> None:
    """Show persisted pipeline status without changing it."""
    settings: Settings = ctx.obj
    if not settings.state_path.exists():
        typer.echo(f"No pipeline state found at {settings.state_path}")
        return

    state = StateStore(settings.state_path).load()
    counts = Counter(job.stage.value for job in state.jobs.values())
    typer.echo(f"Total jobs: {len(state.jobs)}")
    for stage, count in sorted(counts.items()):
        typer.echo(f"{stage}: {count}")
    if state.active_job_id is not None:
        typer.echo(f"Active job: {state.active_job_id}")
    errors = [job.last_error for job in state.jobs.values() if job.last_error]
    if errors:
        typer.echo(f"Last error: {errors[-1]}")
    resumable = next_resumable_job(state)
    typer.echo(
        f"Next action: resume {resumable.post_id} at {resumable.stage.value}"
        if resumable is not None
        else "Next action: add a pending URL or run the queue"
    )


@app.command("run")
def run_command(
    ctx: typer.Context,
    input_path: Annotated[
        Path | None,
        typer.Option(
            "--input",
            exists=True,
            dir_okay=False,
            resolve_path=True,
            help="Markdown URL queue (defaults to content/urls.md).",
        ),
    ] = None,
) -> None:
    """Process pending URLs sequentially through local human review."""
    settings: Settings = ctx.obj
    coordinator = build_local_coordinator(settings, queue_path=input_path)
    with RunLock(settings.output_path / ".run.lock"), InterruptionController() as stop:
        coordinator.interruption = stop
        result = _run_async(coordinator.run())
    _print_result(result)


@app.command()
def resume(ctx: typer.Context) -> None:
    """Resume the oldest persisted nonterminal job from its exact stage."""
    settings: Settings = ctx.obj
    job = next_resumable_job(StateStore(settings.state_path).load())
    if job is None:
        typer.echo("No resumable jobs")
        return
    if not settings.input_path.exists():
        typer.echo(f"Next resumable job: {job.post_id} ({job.stage.value})")
        return
    coordinator = build_local_coordinator(settings)
    with RunLock(settings.output_path / ".run.lock"), InterruptionController() as stop:
        coordinator.interruption = stop
        result = _run_async(coordinator.resume())
    _print_result(result)


@app.command("retry-failed")
def retry_failed(
    ctx: typer.Context,
    post_id: Annotated[str | None, typer.Argument(help="Failed post ID.")] = None,
) -> None:
    """Move one or every failed job back to its recorded retry stage."""
    settings: Settings = ctx.obj
    store = StateStore(settings.state_path)
    with RunLock(settings.output_path / ".run.lock"):
        state = store.load()
        failed = [
            job
            for job in state.jobs.values()
            if job.stage is JobStage.FAILED
            and (post_id is None or job.post_id == post_id)
        ]
        if post_id is not None and not failed:
            raise typer.BadParameter(f"No failed job found: {post_id}")
        for job in failed:
            state = restore_job(state, job.post_id)
        store.save(state)
    typer.echo(f"Restored failed jobs: {len(failed)}")


@app.command("review")
def review_command(
    ctx: typer.Context,
    post_id: Annotated[str, typer.Argument(help="Reviewable post ID.")],
    action: Annotated[
        ReviewAction | None,
        typer.Option(help="Fully explicit noninteractive review action."),
    ] = None,
) -> None:
    """Reopen one persisted package at the local human-review boundary."""
    settings: Settings = ctx.obj
    coordinator = build_local_coordinator(
        settings,
        interactive_review=action is None,
        explicit_action=action,
    )
    with RunLock(settings.output_path / ".run.lock"), InterruptionController() as stop:
        coordinator.interruption = stop
        result = _run_async(coordinator.run(only_post_id=post_id))
    _print_result(result)


@app.command("promote-candidate")
def promote_candidate_command(
    ctx: typer.Context,
    candidate_id: Annotated[str, typer.Argument(help="Active source candidate ID.")],
) -> None:
    """Validate and explicitly add one research candidate to the URL queue."""
    settings: Settings = ctx.obj
    promoted = promote_candidate(
        candidate_id=candidate_id,
        candidates_path=settings.candidates_path,
        queue_path=settings.input_path,
    )
    typer.echo(
        f"Promoted candidate: {promoted.candidate_id} ({promoted.normalized_url()})"
    )


@app.command("research-intake")
def research_intake_command(ctx: typer.Context) -> None:
    """Discover bounded source candidates without drafting or publishing content."""
    settings: Settings = ctx.obj
    evaluator = CodexResearchEvaluator(
        workspace=settings.workspace,
        sources_path=settings.research_sources_path,
        brand_path=settings.brand_path,
        runner=CommandRunner(workspace=settings.workspace),
        schema_path=settings.output_path / "research-intake" / "schema-v1.json",
    )
    service = ResearchIntakeService(
        candidates_path=settings.candidates_path,
        evaluator=evaluator,
    )
    try:
        with RunLock(settings.output_path / ".research-intake.lock"):
            result = asyncio.run(service.run())
            write_run_report(
                settings.output_path / "research-intake" / "latest-report.md", result
            )
    except SocialAgentError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(
        "Research intake complete: "
        f"added={len(result.added_candidate_ids)}, "
        f"expired={len(result.expired_candidate_ids)}"
    )


@app.command("connect")
def connect_command(
    ctx: typer.Context,
    platform: Annotated[
        str,
        typer.Option(help="OAuth provider to authorize: x, linkedin, or all."),
    ] = "all",
    timeout_seconds: Annotated[
        float,
        typer.Option("--timeout-seconds", min=1.0, help="Loopback callback timeout."),
    ] = 300.0,
) -> None:
    """Authorize the local operator and print session-only environment exports."""
    selected_platform = _connect_platform(platform)
    settings: Settings = ctx.obj
    try:
        results = connect(
            selected_platform,
            OAuthSettings(
                x_client_id=settings.x_client_id,
                x_redirect_uri=settings.x_redirect_uri,
                linkedin_client_id=settings.linkedin_client_id,
                linkedin_redirect_uri=settings.linkedin_redirect_uri,
                linkedin_version=settings.linkedin_version,
            ),
            timeout_seconds=timeout_seconds,
        )
    except SocialAgentError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(format_exports(results))


@app.command("workspace")
def workspace_command(
    ctx: typer.Context,
    port: Annotated[
        int,
        typer.Option("--port", min=1, max=65535, help="Loopback-only workspace port."),
    ] = 8767,
    open_browser: Annotated[
        bool,
        typer.Option("--open/--no-open", help="Open the local workspace in a browser."),
    ] = True,
) -> None:
    """Open the local-only visual operator workspace on 127.0.0.1."""
    settings: Settings = ctx.obj
    server = build_workspace_server(OperatorWorkspace(settings), port)
    address = f"http://127.0.0.1:{server.server_port}/"
    typer.echo(f"Local operator workspace: {address}")
    if open_browser:
        webbrowser.open(address)
    with server:
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            typer.echo("Workspace stopped")


def _connect_platform(value: str) -> ConnectPlatform:
    match value:
        case "x" | "linkedin" | "all":
            return value
        case _:
            raise typer.BadParameter("Platform must be x, linkedin, or all")


def _run_async(
    awaitable: Coroutine[Any, Any, PipelineRunResult],
) -> PipelineRunResult:
    try:
        return asyncio.run(awaitable)
    except (PipelineStateError, SocialAgentError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc


def _print_result(result: PipelineRunResult) -> None:
    typer.echo(
        "Run complete: "
        f"approved={result.approved}, rejected={result.rejected}, "
        f"failed={result.failed}, skipped={result.skipped}"
    )
    if result.interrupted:
        typer.echo("Interrupted safely; resume will continue the recorded stage")
