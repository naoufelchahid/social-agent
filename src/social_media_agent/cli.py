"""Local command-line interface."""

import asyncio
from collections import Counter
from collections.abc import Coroutine
from pathlib import Path
from typing import Annotated, Any

import typer

from social_media_agent.config import Settings
from social_media_agent.errors import PipelineStateError, SocialAgentError
from social_media_agent.logging import configure_logging
from social_media_agent.models import JobStage
from social_media_agent.pipeline import PipelineRunResult, build_local_coordinator
from social_media_agent.review import ReviewAction
from social_media_agent.signals import InterruptionController
from social_media_agent.state import (
    RunLock,
    StateStore,
    next_resumable_job,
    restore_job,
)

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
