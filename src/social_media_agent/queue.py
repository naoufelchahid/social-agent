"""Parse the human-maintained Markdown URL queue."""

from __future__ import annotations

import os
import re
from pathlib import Path
from tempfile import NamedTemporaryFile

from social_media_agent.errors import ConfigurationError
from social_media_agent.models import QueueItem
from social_media_agent.urls import InvalidUrlError, normalize_url, post_id_for_url


class QueueFormatError(ConfigurationError):
    """Raised when a queue line looks actionable but is malformed."""


_ITEM = re.compile(r"^\s*-\s+\[([ xX])\]\s+(\S+)\s*$")
_CHECKBOX_PREFIX = re.compile(r"^\s*-\s+\[")
_METADATA = re.compile(r"^\s+-\s+(Angle|Audience):\s*(.*?)\s*$", re.IGNORECASE)
_FENCE = re.compile(r"^\s*```")


def parse_queue(path: Path) -> list[QueueItem]:
    """Read actionable checkbox items from a Markdown file."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError as exc:
        raise QueueFormatError(f"Queue file not found: {path}") from exc

    items: list[QueueItem] = []
    in_fence = False

    for line_number, line in enumerate(lines, start=1):
        if _FENCE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue

        item_match = _ITEM.match(line)
        if item_match:
            checked_marker, original_url = item_match.groups()
            try:
                normalized_url = normalize_url(original_url)
            except InvalidUrlError as exc:
                raise QueueFormatError(f"line {line_number}: {exc}") from exc
            items.append(
                QueueItem(
                    id=post_id_for_url(normalized_url),
                    original_url=original_url,
                    normalized_url=normalized_url,
                    checked=checked_marker.lower() == "x",
                    source_line=line_number,
                )
            )
            continue

        if _CHECKBOX_PREFIX.match(line):
            raise QueueFormatError(
                f"line {line_number}: checkbox item must contain a valid HTTP URL"
            )

        metadata_match = _METADATA.match(line)
        if metadata_match:
            if not items:
                raise QueueFormatError(
                    f"line {line_number}: metadata requires a preceding queue item"
                )
            key, value = metadata_match.groups()
            if not value:
                raise QueueFormatError(f"line {line_number}: {key} cannot be empty")
            field = key.lower()
            items[-1] = items[-1].model_copy(update={field: value})

    if in_fence:
        raise QueueFormatError("Markdown queue contains an unclosed code fence")

    return items


def mark_queue_item_checked(path: Path, item: QueueItem) -> None:
    """Atomically mark the exact accepted queue item checked."""
    try:
        contents = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise QueueFormatError(f"Queue file not found: {path}") from exc
    lines = contents.splitlines(keepends=True)
    line_index = item.source_line - 1
    if line_index < 0 or line_index >= len(lines):
        raise QueueFormatError("Queue checkbox source line is no longer available")
    line = lines[line_index]
    line_without_ending = line.rstrip("\r\n")
    ending = line[len(line_without_ending) :]
    match = _ITEM.match(line_without_ending)
    if match is None:
        raise QueueFormatError("Queue checkbox no longer matches the accepted item")
    marker, original_url = match.groups()
    try:
        normalized = normalize_url(original_url)
    except InvalidUrlError as exc:
        raise QueueFormatError("Queue checkbox URL is no longer valid") from exc
    if normalized != item.normalized_url:
        raise QueueFormatError("Queue checkbox no longer matches the accepted URL")
    if marker.lower() == "x":
        return
    lines[line_index] = re.sub(r"\[ \]", "[x]", line_without_ending, count=1) + ending
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
            temporary.writelines(lines)
            temporary.flush()
            os.fsync(temporary.fileno())
        temporary_path.replace(path)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
