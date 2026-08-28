"""Tests for the loopback-only workspace transport."""

import http.client
import re
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


def test_page_loads_same_origin_script_under_a_restrictive_csp(tmp_path: Path) -> None:
    """The dynamic workspace can run without permitting inline browser scripts."""
    server = build_workspace_server(
        OperatorWorkspace(Settings.from_workspace(tmp_path))
    )
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        connection = http.client.HTTPConnection("127.0.0.1", server.server_port)
        connection.request("GET", "/")
        page = connection.getresponse()

        contents = page.read()
        assert b'<script type="module" crossorigin src="/assets/' in contents
        assert (
            page.getheader("Content-Security-Policy")
            == "default-src 'self'; script-src 'self'"
        )

        asset = re.search(
            rb'<script type="module" crossorigin src="/([^\"]+)"></script>',
            contents,
        )
        assert asset is not None
        connection.request("GET", f"/{asset.group(1).decode()}")
        script = connection.getresponse()
        assert script.status == 200
        assert (
            script.getheader("Content-Type") == "application/javascript; charset=utf-8"
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_v1_transport_rejects_unknown_static_assets(tmp_path: Path) -> None:
    """Only frontend manifest assets are served; filenames never become file paths."""
    server = build_workspace_server(
        OperatorWorkspace(Settings.from_workspace(tmp_path))
    )
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        connection = http.client.HTTPConnection("127.0.0.1", server.server_port)
        connection.request("GET", "/assets/../../pyproject.toml")
        assert connection.getresponse().status == 404

        connection.request("GET", "/api/v1/snapshot")
        assert connection.getresponse().status == 200
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
