"""Loopback HTTP presentation for the local operator workspace."""

from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from social_media_agent.operator_workspace import OperatorWorkspace


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
                self._bytes(HTTPStatus.OK, _PAGE.encode(), "text/html; charset=utf-8")
                return
            if parsed.path == "/workspace.js":
                self._bytes(
                    HTTPStatus.OK,
                    _SCRIPT.encode(),
                    "application/javascript; charset=utf-8",
                )
                return
            if parsed.path == "/api/snapshot":
                self._snapshot(parsed.query)
                return
            parts = parsed.path.split("/")
            if (
                len(parts) == 5
                and parts[:3] == ["", "api", "posts"]
                and parts[4] == "image"
            ):
                self._image(parts[3])
                return
            self._json(HTTPStatus.NOT_FOUND, {"ok": False, "message": "Not found"})

        def do_POST(self) -> None:
            if urlparse(self.path).path != "/api/commands":
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
            self.send_header("Content-Security-Policy", "default-src 'self'")
            self.end_headers()
            self.wfile.write(contents)

        def log_message(self, format: str, *args: object) -> None:
            return

    return WorkspaceHandler


_PAGE = """<!doctype html>
<html lang="en">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Social Agent · Local workspace</title>
<body>
<main>
  <h1>Local operator workspace</h1>
  <p id="notice" aria-live="polite"></p>
  <section><h2>Pipeline</h2><p id="pipeline"></p><div id="posts"></div></section>
  <section><h2>Candidate portfolio</h2><div id="candidates"></div></section>
  <section><h2>Research intake</h2><pre id="report"></pre></section>
</main>
<script src="/workspace.js"></script>
</body>
</html>"""


_SCRIPT = """const text = (value) => String(value ?? "");

function postCard(post) {
  return `<article><h3>${text(post.post_id)} — ${text(post.stage)}</h3>`
    + `<p>${text(post.url)}</p><p>${text(post.last_error)}</p></article>`;
}

function candidateCard(candidate) {
  return `<article><h3>${text(candidate.title)}</h3>`
    + `<p>${text(candidate.status)} · ${text(candidate.score)}/10</p>`
    + `<p>${text(candidate.angle)}</p></article>`;
}

async function loadWorkspace() {
  const response = await fetch("/api/snapshot");
  const snapshot = await response.json();
  document.querySelector("#pipeline").textContent = snapshot.active_post_id
    ? `Active: ${snapshot.active_post_id}`
    : "No active post";
  document.querySelector("#posts").innerHTML = snapshot.posts.map(postCard).join("");
  document.querySelector("#candidates").innerHTML = snapshot.candidates
    .map(candidateCard)
    .join("");
  document.querySelector("#report").textContent = snapshot.research.latest_report
    || "No intake report.";
}

loadWorkspace();
"""
