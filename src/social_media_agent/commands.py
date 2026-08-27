"""Secure asynchronous execution for local CLI agents."""

from __future__ import annotations

import asyncio
import os
import signal
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from time import monotonic

from social_media_agent.errors import ExternalCommandError

_DEFAULT_ENVIRONMENT_ALLOWLIST = frozenset(
    {
        "AGY_API_KEY",
        "AGY_API_TOKEN",
        "CODEX_HOME",
        "HOME",
        "LANG",
        "LC_ALL",
        "NO_COLOR",
        "OPENAI_API_KEY",
        "PATH",
        "SSL_CERT_DIR",
        "SSL_CERT_FILE",
        "TERM",
    }
)


@dataclass(frozen=True, slots=True)
class CommandResult:
    """Captured result from one completed local command."""

    arguments: tuple[str, ...]
    return_code: int
    stdout: str
    stderr: str
    duration_seconds: float


class CommandRunner:
    """Run argument arrays inside a workspace with explicit resource policy."""

    def __init__(
        self,
        *,
        workspace: Path,
        environment_allowlist: set[str] | frozenset[str] | None = None,
        source_environment: Mapping[str, str] | None = None,
        termination_grace_seconds: float = 2.0,
    ) -> None:
        if termination_grace_seconds <= 0:
            raise ValueError("Termination grace period must be greater than zero")
        self._workspace = workspace.resolve()
        self._environment_allowlist = frozenset(
            environment_allowlist
            if environment_allowlist is not None
            else _DEFAULT_ENVIRONMENT_ALLOWLIST
        )
        self._source_environment = dict(
            source_environment if source_environment is not None else os.environ
        )
        self._termination_grace_seconds = termination_grace_seconds

    async def run(
        self,
        arguments: Sequence[str],
        *,
        cwd: Path | None = None,
        timeout_seconds: float = 300.0,
        environment_overrides: Mapping[str, str] | None = None,
    ) -> CommandResult:
        """Execute one command without a shell and capture its complete streams."""
        args = self._validate_arguments(arguments)
        working_directory = self._working_directory(cwd)
        if timeout_seconds <= 0:
            raise ValueError("Command timeout must be greater than zero")
        environment = self._environment(environment_overrides)
        started = monotonic()
        try:
            process = await asyncio.create_subprocess_exec(
                *args,
                cwd=working_directory,
                env=environment,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                start_new_session=True,
            )
        except OSError as exc:
            raise ExternalCommandError("Failed to start local agent command") from exc

        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout_seconds,
            )
        except TimeoutError as exc:
            await asyncio.shield(self._terminate(process))
            raise ExternalCommandError(
                f"Local agent command timed out after {timeout_seconds:g} seconds"
            ) from exc
        except asyncio.CancelledError:
            await asyncio.shield(self._terminate(process))
            raise

        return_code = process.returncode
        if return_code is None:
            raise ExternalCommandError(
                "Local agent command did not report an exit status"
            )
        result = CommandResult(
            arguments=args,
            return_code=return_code,
            stdout=stdout_bytes.decode("utf-8", errors="replace"),
            stderr=stderr_bytes.decode("utf-8", errors="replace"),
            duration_seconds=monotonic() - started,
        )
        if result.return_code != 0:
            raise ExternalCommandError(
                f"Local agent command exited with status {result.return_code}",
                result=result,
            )
        return result

    def _working_directory(self, cwd: Path | None) -> Path:
        candidate = (cwd if cwd is not None else self._workspace).resolve()
        try:
            candidate.relative_to(self._workspace)
        except ValueError as exc:
            raise ValueError(
                "Command working directory must be inside workspace"
            ) from exc
        if not candidate.is_dir():
            raise ValueError("Command working directory must be an existing directory")
        return candidate

    def _environment(
        self,
        overrides: Mapping[str, str] | None,
    ) -> dict[str, str]:
        environment = {
            name: value
            for name, value in self._source_environment.items()
            if name in self._environment_allowlist
        }
        if overrides is None:
            return environment
        forbidden = set(overrides) - self._environment_allowlist
        if forbidden:
            raise ValueError("Command environment override is not allowlisted")
        environment.update(overrides)
        return environment

    @staticmethod
    def _validate_arguments(arguments: Sequence[str]) -> tuple[str, ...]:
        if isinstance(arguments, (str, bytes)):
            raise ValueError("Command must be provided as an argument array")
        args = tuple(arguments)
        if not args or any(not isinstance(value, str) or not value for value in args):
            raise ValueError("Command argument array must contain non-empty strings")
        return args

    async def _terminate(self, process: asyncio.subprocess.Process) -> None:
        if process.returncode is not None:
            return
        self._signal_process_group(process, signal.SIGTERM)
        try:
            await asyncio.wait_for(
                process.wait(),
                timeout=self._termination_grace_seconds,
            )
            return
        except TimeoutError:
            self._signal_process_group(process, signal.SIGKILL)
            await process.wait()

    @staticmethod
    def _signal_process_group(
        process: asyncio.subprocess.Process,
        requested_signal: signal.Signals,
    ) -> None:
        try:
            os.killpg(process.pid, requested_signal)
        except ProcessLookupError:
            return
