"""Safe atomic storage for per-post human and machine-readable artifacts."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from social_media_agent.errors import PipelineStateError

_SAFE_POST_ID = re.compile(r"^[A-Za-z0-9_-]+$")


class ArtifactRepository:
    """Persist post artifacts beneath one workspace-owned output directory."""

    def __init__(self, workspace: Path, output_path: Path) -> None:
        self.workspace = workspace.resolve()
        self.output_path = output_path.resolve()
        try:
            self.output_path.relative_to(self.workspace)
        except ValueError as exc:
            raise PipelineStateError(
                "Output path must be inside the workspace"
            ) from exc

    def write_text(self, post_id: str, name: str, contents: str) -> Path:
        """Atomically write text and return its workspace-relative path."""
        destination = self._destination(post_id, name)
        self._atomic_write(destination, contents)
        return destination.relative_to(self.workspace)

    def write_json(self, post_id: str, name: str, value: Any) -> Path:
        """Atomically write deterministic UTF-8 JSON."""
        contents = (
            json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        )
        return self.write_text(post_id, name, contents)

    def write_json_immutable(self, post_id: str, name: str, value: Any) -> Path:
        """Atomically create JSON exactly once without replacing prior evidence."""
        destination = self._destination(post_id, name)
        destination.parent.mkdir(parents=True, exist_ok=True)
        contents = (
            json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        )
        temporary_path: Path | None = None
        try:
            with NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=destination.parent,
                prefix=f".{destination.name}.",
                suffix=".tmp",
                delete=False,
            ) as temporary:
                temporary_path = Path(temporary.name)
                temporary.write(contents)
                temporary.flush()
                os.fsync(temporary.fileno())
            try:
                os.link(temporary_path, destination)
            except FileExistsError as exc:
                raise PipelineStateError(
                    f"Immutable artifact already exists: {name}"
                ) from exc
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
        return destination.relative_to(self.workspace)

    def _destination(self, post_id: str, name: str) -> Path:
        if not _SAFE_POST_ID.fullmatch(post_id):
            raise PipelineStateError(f"Unsafe post ID: {post_id}")
        name_path = Path(name)
        if name_path.is_absolute() or name_path.name != name or name in {".", ".."}:
            raise PipelineStateError(f"Unsafe artifact name: {name}")
        return self.output_path / "posts" / post_id / name

    @staticmethod
    def _atomic_write(destination: Path, contents: str) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary_path: Path | None = None
        try:
            with NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=destination.parent,
                prefix=f".{destination.name}.",
                suffix=".tmp",
                delete=False,
            ) as temporary:
                temporary_path = Path(temporary.name)
                temporary.write(contents)
                temporary.flush()
                os.fsync(temporary.fileno())
            temporary_path.replace(destination)
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
