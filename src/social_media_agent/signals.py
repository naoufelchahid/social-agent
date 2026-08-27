"""Cooperative signal capture for safe stage-boundary interruption."""

from __future__ import annotations

import signal
from collections.abc import Callable
from types import FrameType, TracebackType

SignalHandler = Callable[[int, FrameType | None], object] | int | None


class InterruptionController:
    """Convert SIGINT/SIGTERM into a flag the pipeline checks after atomic work."""

    def __init__(self) -> None:
        self.requested = False
        self.received_signal: signal.Signals | None = None
        self._prior_handlers: dict[signal.Signals, SignalHandler] = {}

    def __enter__(self) -> InterruptionController:
        """Install temporary handlers for cooperative termination."""
        for received_signal in (signal.Signals.SIGINT, signal.Signals.SIGTERM):
            self._prior_handlers[received_signal] = signal.getsignal(received_signal)
            signal.signal(received_signal, self._handle)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Restore every handler that was active before this controller."""
        for received_signal, prior_handler in self._prior_handlers.items():
            signal.signal(received_signal, prior_handler)
        self._prior_handlers.clear()

    def _handle(self, signum: int, _frame: FrameType | None) -> None:
        """Record a request without raising during an atomic file operation."""
        self.requested = True
        self.received_signal = signal.Signals(signum)
