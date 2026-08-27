"""Tests for the Markdown URL queue."""

from pathlib import Path

import pytest

from social_media_agent.queue import QueueFormatError, parse_queue


def test_parse_queue_reads_items_and_optional_metadata(tmp_path: Path) -> None:
    """Queue items should retain display state, source line, and metadata."""
    queue_path = tmp_path / "urls.md"
    queue_path.write_text(
        """# Queue

- [ ] https://Example.com/article/?utm_source=newsletter#section
  - Angle: Focus on local execution
  - Audience: Python developers
- [x] https://github.com/Owner/Repo/
""",
        encoding="utf-8",
    )

    items = parse_queue(queue_path)

    assert len(items) == 2
    assert items[0].checked is False
    assert items[0].source_line == 3
    assert items[0].normalized_url == "https://example.com/article"
    assert items[0].angle == "Focus on local execution"
    assert items[0].audience == "Python developers"
    assert items[1].checked is True
    assert items[1].normalized_url == "https://github.com/Owner/Repo"


def test_parse_queue_ignores_headings_prose_and_fenced_examples(
    tmp_path: Path,
) -> None:
    """Documentation around the queue should not become runtime work."""
    queue_path = tmp_path / "urls.md"
    queue_path.write_text(
        """# Social media queue

Add URLs below.

```md
- [ ] https://example.com/documentation-only
```
""",
        encoding="utf-8",
    )

    assert parse_queue(queue_path) == []


def test_parse_queue_reports_the_line_for_a_malformed_checkbox(
    tmp_path: Path,
) -> None:
    """A checkbox that is not a valid HTTP URL should fail explicitly."""
    queue_path = tmp_path / "urls.md"
    queue_path.write_text("# Queue\n\n- [ ] not-a-url\n", encoding="utf-8")

    with pytest.raises(QueueFormatError, match=r"line 3.*HTTP URL"):
        parse_queue(queue_path)


def test_parse_queue_rejects_metadata_without_an_item(tmp_path: Path) -> None:
    """Recognized metadata must be attached to a preceding queue item."""
    queue_path = tmp_path / "urls.md"
    queue_path.write_text("  - Angle: Orphaned instruction\n", encoding="utf-8")

    with pytest.raises(QueueFormatError, match=r"line 1.*preceding queue item"):
        parse_queue(queue_path)
