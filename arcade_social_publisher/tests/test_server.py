from arcade_social_publisher.server import _server_run_config


def test_server_uses_arcade_deploy_http_transport_arguments() -> None:
    deployed = _server_run_config(["--transport", "http", "--port", "8765"])
    local = _server_run_config([])

    assert (deployed.transport, deployed.port) == ("http", 8765)
    assert (local.transport, local.port) == ("stdio", 8000)
