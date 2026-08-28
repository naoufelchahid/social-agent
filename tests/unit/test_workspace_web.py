"""Tests for the loopback-only workspace transport."""

import http.client
from pathlib import Path
from threading import Thread

from social_media_agent.config import Settings
from social_media_agent.operator_workspace import OperatorWorkspace
from social_media_agent.workspace_web import build_workspace_server


def test_loopback_transport_serves_snapshot_and_rejects_traversal(
    tmp_path: Path,
) -> None:
    """The browser can read the workspace but cannot request arbitrary files."""
    server = build_workspace_server(
        OperatorWorkspace(Settings.from_workspace(tmp_path))
    )
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        connection = http.client.HTTPConnection("127.0.0.1", server.server_port)
        connection.request("GET", "/api/snapshot")
        response = connection.getresponse()
        assert response.status == 200
        assert b'"posts": []' in response.read()

        connection.request("GET", "/api/posts/../state.json/image")
        assert connection.getresponse().status == 404
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
