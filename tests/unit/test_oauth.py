"""Tests for local, session-only OAuth onboarding."""

import socket
import threading
from collections.abc import Callable
from urllib.parse import parse_qs, urlparse
from urllib.request import urlopen

import httpx
import pytest
import respx

from social_media_agent.errors import ConfigurationError
from social_media_agent.oauth import OAuthSettings, connect, format_exports


def test_connect_x_exchanges_a_pkce_callback_for_session_export() -> None:
    callback_uri = _callback_uri("x")
    settings = OAuthSettings(
        x_client_id="x-client",
        x_redirect_uri=callback_uri,
        linkedin_client_id=None,
        linkedin_redirect_uri=None,
        linkedin_version=None,
    )
    authorization_urls: list[str] = []

    with respx.mock(assert_all_called=True) as mocked:
        token_route = mocked.post("https://api.x.com/2/oauth2/token").mock(
            return_value=httpx.Response(200, json={"access_token": "x-token"})
        )
        result = connect(
            "x", settings, browser_open=_callback_opener(authorization_urls)
        )

    assert result[0].values == {"X_ACCESS_TOKEN": "x-token"}
    request = token_route.calls[0].request
    token_data = parse_qs(request.content.decode())
    assert token_data["code"] == ["approved-code"]
    assert token_data["code_verifier"]
    query = parse_qs(urlparse(authorization_urls[0]).query)
    assert query["code_challenge_method"] == ["S256"]
    assert query["scope"] == ["tweet.read tweet.write users.read media.write"]
    assert "export X_ACCESS_TOKEN=x-token" in format_exports(result)


def test_connect_linkedin_derives_the_person_urn() -> None:
    callback_uri = _callback_uri("linkedin")
    settings = OAuthSettings(
        x_client_id=None,
        x_redirect_uri=None,
        linkedin_client_id="linkedin-client",
        linkedin_redirect_uri=callback_uri,
        linkedin_version="202608",
    )

    with respx.mock(assert_all_called=True) as mocked:
        mocked.post("https://www.linkedin.com/oauth/v2/accessToken").mock(
            return_value=httpx.Response(200, json={"access_token": "linkedin-token"})
        )
        mocked.get("https://api.linkedin.com/v2/userinfo").mock(
            return_value=httpx.Response(200, json={"sub": "member"})
        )
        authorization_urls: list[str] = []
        result = connect(
            "linkedin", settings, browser_open=_callback_opener(authorization_urls)
        )

    assert result[0].values == {
        "LINKEDIN_ACCESS_TOKEN": "linkedin-token",
        "LINKEDIN_AUTHOR_URN": "urn:li:person:member",
        "LINKEDIN_API_VERSION": "202608",
    }
    assert urlparse(authorization_urls[0]).path == "/oauth/native-pkce/authorization"


@pytest.mark.parametrize(
    "redirect_uri",
    (
        "https://example.com/callback",
        "http://localhost:8765/callback",
        "http://[::1]:8765/callback",
    ),
)
def test_connect_rejects_non_ipv4_loopback_redirects_before_opening_a_browser(
    redirect_uri: str,
) -> None:
    settings = OAuthSettings(
        x_client_id="x-client",
        x_redirect_uri=redirect_uri,
        linkedin_client_id=None,
        linkedin_redirect_uri=None,
        linkedin_version=None,
    )

    with pytest.raises(ConfigurationError, match="loopback"):
        connect("x", settings, browser_open=lambda _: pytest.fail("opened browser"))


def _callback_uri(path: str) -> str:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return f"http://127.0.0.1:{listener.getsockname()[1]}/{path}"


def _callback_opener(authorization_urls: list[str]) -> Callable[[str], bool]:
    def open_browser(authorization_url: str) -> bool:
        authorization_urls.append(authorization_url)
        query = parse_qs(urlparse(authorization_url).query)
        callback = query["redirect_uri"][0]
        request_url = f"{callback}?code=approved-code&state={query['state'][0]}"
        threading.Thread(
            target=_send_callback, args=(request_url,), daemon=True
        ).start()
        return True

    return open_browser


def _send_callback(request_url: str) -> None:
    with urlopen(request_url, timeout=5):
        pass
