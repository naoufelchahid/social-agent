"""Loopback HTTP presentation for the packaged local operator workspace."""

from __future__ import annotations

import json
import mimetypes
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from social_media_agent.operator_workspace import OperatorWorkspace

_ASSETS = Path(__file__).with_name("web_assets")


def build_workspace_server(
    workspace: OperatorWorkspace, port: int = 0
) -> ThreadingHTTPServer:
    """Create a local-only server; callers must serve it on loopback."""
    return ThreadingHTTPServer(("127.0.0.1", port), _handler_for(workspace))


def _handler_for(workspace: OperatorWorkspace) -> type[BaseHTTPRequestHandler]:
    class WorkspaceHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/":
                self._asset("index.html", "text/html; charset=utf-8")
                return
            if parsed.path in {"/api/snapshot", "/api/v1/snapshot"}:
                self._snapshot(parsed.query)
                return
            parts = parsed.path.split("/")
            if (
                len(parts) == 5
                and parts[:3] == ["", "api", "posts"]
                and parts[4] == "image"
            ) or (
                len(parts) == 6
                and parts[:4] == ["", "api", "v1", "posts"]
                and parts[5] == "image"
            ):
                self._image(parts[-2])
                return
            if parsed.path.startswith("/assets/"):
                self._asset(parsed.path.removeprefix("/"), None)
                return
            self._json(HTTPStatus.NOT_FOUND, {"ok": False, "message": "Not found"})

        def do_POST(self) -> None:
            if urlparse(self.path).path not in {"/api/commands", "/api/v1/commands"}:
                self._json(HTTPStatus.NOT_FOUND, {"ok": False, "message": "Not found"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0 or length > 14 * 1024 * 1024:
                    raise ValueError("Command body exceeds the local upload limit")
                payload = json.loads(self.rfile.read(length))
                if not isinstance(payload, dict):
                    raise ValueError("Command body must be a JSON object")
                result = workspace.submit(payload)
            except (ValueError, json.JSONDecodeError) as exc:
                self._json(HTTPStatus.BAD_REQUEST, {"ok": False, "message": str(exc)})
                return
            self._json(
                HTTPStatus.OK if result["ok"] else HTTPStatus.BAD_REQUEST, result
            )

        def _snapshot(self, query_string: str) -> None:
            query = parse_qs(query_string)
            try:
                snapshot = workspace.snapshot(
                    candidate_status=query.get("candidate_status", [None])[0]
                )
            except ValueError as exc:
                self._json(HTTPStatus.BAD_REQUEST, {"ok": False, "message": str(exc)})
                return
            self._json(HTTPStatus.OK, snapshot)

        def _image(self, post_id: str) -> None:
            try:
                image = workspace.image_path(post_id)
                self._bytes(HTTPStatus.OK, image.read_bytes(), "image/png")
            except (OSError, ValueError):
                self._json(
                    HTTPStatus.NOT_FOUND,
                    {"ok": False, "message": "Image unavailable"},
                )

        def _asset(self, name: str, content_type: str | None) -> None:
            if name not in _manifest_assets():
                self._json(HTTPStatus.NOT_FOUND, {"ok": False, "message": "Not found"})
                return
            path = _ASSETS / name
            if not path.is_file():
                self._json(HTTPStatus.NOT_FOUND, {"ok": False, "message": "Not found"})
                return
            resolved_type = content_type or mimetypes.guess_type(path.name)[0]
            if path.suffix == ".js":
                resolved_type = "application/javascript; charset=utf-8"
            self._bytes(
                HTTPStatus.OK,
                path.read_bytes(),
                resolved_type or "application/octet-stream",
            )

        def _json(self, status: HTTPStatus, value: object) -> None:
            self._bytes(
                status,
                json.dumps(value, ensure_ascii=False).encode(),
                "application/json; charset=utf-8",
            )

        def _bytes(
            self, status: HTTPStatus, contents: bytes, content_type: str
        ) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(contents)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header(
                "Content-Security-Policy", "default-src 'self'; script-src 'self'"
            )
            self.end_headers()
            self.wfile.write(contents)

        def log_message(self, format: str, *args: object) -> None:
            return

    return WorkspaceHandler


def _manifest_assets() -> set[str]:
    """Return only paths Vite declared for the packaged application."""
    try:
        manifest = json.loads((_ASSETS / "asset-manifest.json").read_text())
    except (OSError, json.JSONDecodeError):
        return set()
    if not isinstance(manifest, dict):
        return set()
    assets = {"index.html"}
    for value in manifest.values():
        if not isinstance(value, dict):
            continue
        for field in ("file", "css", "assets", "imports"):
            item = value.get(field)
            if isinstance(item, str):
                assets.add(item)
            elif isinstance(item, list):
                assets.update(part for part in item if isinstance(part, str))
    return assets
