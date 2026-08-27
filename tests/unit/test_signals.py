"""Tests for cooperative operating-system signal handling."""

import os
import signal

from social_media_agent.signals import InterruptionController


def test_controller_captures_signal_and_restores_prior_handler() -> None:
    """SIGTERM should request a safe checkpoint instead of killing mid-write."""
    prior_handler = signal.getsignal(signal.SIGTERM)

    with InterruptionController() as controller:
        os.kill(os.getpid(), signal.SIGTERM)
        assert controller.requested is True
        assert controller.received_signal is signal.Signals.SIGTERM

    assert signal.getsignal(signal.SIGTERM) == prior_handler
