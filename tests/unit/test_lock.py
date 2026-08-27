"""Tests for the single-writer pipeline lock."""

from pathlib import Path

import pytest

from social_media_agent.errors import PipelineStateError
from social_media_agent.state import RunLock


def test_second_writer_cannot_acquire_the_same_lock(tmp_path: Path) -> None:
    """Concurrent pipeline writers should fail immediately and clearly."""
    lock_path = tmp_path / "output" / ".run.lock"

    with (
        RunLock(lock_path),
        pytest.raises(PipelineStateError, match="already running"),
        RunLock(lock_path),
    ):
        pytest.fail("second lock unexpectedly acquired")


def test_lock_can_be_reacquired_after_release(tmp_path: Path) -> None:
    """A clean exit should release the advisory lock."""
    lock_path = tmp_path / "output" / ".run.lock"

    with RunLock(lock_path):
        pass
    with RunLock(lock_path):
        assert lock_path.exists()
