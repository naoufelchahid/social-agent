"""Tests for secure local agent subprocess execution."""

import asyncio
import json
import os
import sys
from pathlib import Path

import pytest

from social_media_agent.commands import CommandRunner
from social_media_agent.errors import ExternalCommandError


@pytest.mark.asyncio
async def test_runner_uses_literal_arguments_allowlisted_env_and_captured_output(
    tmp_path: Path,
) -> None:
    """Arguments must not reach a shell and children receive only allowed env."""
    runner = CommandRunner(
        workspace=tmp_path,
        environment_allowlist={"PATH", "TEST_ALLOWED"},
        source_environment={
            "PATH": os.environ.get("PATH", ""),
            "TEST_ALLOWED": "visible",
            "SECRET_VALUE": "hidden",
        },
    )
    literal = "$(touch should-not-exist)"
    code = (
        "import json, os, pathlib, sys; "
        "print(json.dumps({'arg': sys.argv[1], 'cwd': str(pathlib.Path.cwd()), "
        "'allowed': os.getenv('TEST_ALLOWED'), 'secret': os.getenv('SECRET_VALUE')})); "
        "print('captured stderr', file=sys.stderr)"
    )

    result = await runner.run(
        [sys.executable, "-c", code, literal],
        cwd=tmp_path,
        timeout_seconds=5,
    )

    payload = json.loads(result.stdout)
    assert payload == {
        "allowed": "visible",
        "arg": literal,
        "cwd": str(tmp_path),
        "secret": None,
    }
    assert result.stderr.strip() == "captured stderr"
    assert result.return_code == 0
    assert not (tmp_path / "should-not-exist").exists()


@pytest.mark.asyncio
async def test_runner_reports_nonzero_exit_with_captured_result(tmp_path: Path) -> None:
    """Callers should receive the exit status and streams for local evidence."""
    runner = CommandRunner(workspace=tmp_path)
    code = (
        "import sys; print('partial'); print('failure', file=sys.stderr); sys.exit(7)"
    )

    with pytest.raises(ExternalCommandError, match="status 7") as raised:
        await runner.run([sys.executable, "-c", code], timeout_seconds=5)

    assert raised.value.result is not None
    assert raised.value.result.return_code == 7
    assert raised.value.result.stdout.strip() == "partial"
    assert raised.value.result.stderr.strip() == "failure"


@pytest.mark.asyncio
async def test_runner_timeout_terminates_the_process_group(tmp_path: Path) -> None:
    """Timeout should terminate descendants started by the agent process."""
    child_pid_path = tmp_path / "child.pid"
    code = (
        "import pathlib, subprocess, sys, time; "
        "child = subprocess.Popen([sys.executable, '-c', "
        "'import time; time.sleep(60)']); "
        f"pathlib.Path({str(child_pid_path)!r}).write_text(str(child.pid)); "
        "time.sleep(60)"
    )
    runner = CommandRunner(workspace=tmp_path, termination_grace_seconds=0.1)

    with pytest.raises(ExternalCommandError, match="timed out"):
        await runner.run([sys.executable, "-c", code], timeout_seconds=0.3)

    child_pid = int(child_pid_path.read_text())
    await _assert_process_exited(child_pid)


@pytest.mark.asyncio
async def test_runner_cancellation_terminates_process_before_propagating(
    tmp_path: Path,
) -> None:
    """Task cancellation should clean up the child and remain cancellation."""
    pid_path = tmp_path / "agent.pid"
    code = (
        "import os, pathlib, time; "
        f"pathlib.Path({str(pid_path)!r}).write_text(str(os.getpid())); "
        "time.sleep(60)"
    )
    runner = CommandRunner(workspace=tmp_path, termination_grace_seconds=0.1)
    task = asyncio.create_task(
        runner.run([sys.executable, "-c", code], timeout_seconds=5)
    )
    await _wait_for_file(pid_path)
    process_pid = int(pid_path.read_text())

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    await _assert_process_exited(process_pid)


@pytest.mark.asyncio
async def test_runner_rejects_unsafe_invocation_configuration(tmp_path: Path) -> None:
    """String commands, external cwd, and invalid timeouts must fail early."""
    runner = CommandRunner(workspace=tmp_path)

    with pytest.raises(ValueError, match="argument array"):
        await runner.run("echo unsafe", timeout_seconds=1)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="working directory"):
        await runner.run([sys.executable, "--version"], cwd=tmp_path.parent)
    with pytest.raises(ValueError, match="timeout"):
        await runner.run([sys.executable, "--version"], timeout_seconds=0)


async def _wait_for_file(path: Path) -> None:
    for _ in range(100):
        if path.exists():
            return
        await asyncio.sleep(0.01)
    pytest.fail(f"Timed out waiting for {path.name}")


async def _assert_process_exited(pid: int) -> None:
    for _ in range(100):
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return
        status_path = Path(f"/proc/{pid}/status")
        if status_path.exists() and "State:\tZ" in status_path.read_text():
            return
        await asyncio.sleep(0.01)
    pytest.fail(f"Process {pid} was not terminated")
