"""Local OAuth 2.0 onboarding for the single local operator."""

from __future__ import annotations

import base64
import hashlib
import secrets
import shlex
import time
import webbrowser
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Literal
from urllib.parse import parse_qs, urlencode, urlparse

import httpx

from social_media_agent.errors import ConfigurationError, SocialAgentError

ConnectPlatform = Literal["x", "linkedin", "all"]

_X_AUTHORIZE_URL = "https://x.com/i/oauth2/authorize"
_X_TOKEN_URL = "https://api.x.com/2/oauth2/token"
_LINKEDIN_AUTHORIZE_URL = "https://www.linkedin.com/oauth/native-pkce/authorization"
_LINKEDIN_TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
_LINKEDIN_USERINFO_URL = "https://api.linkedin.com/v2/userinfo"


@dataclass(frozen=True, slots=True)
class OAuthSettings:
    """Non-secret OAuth application registration supplied by the operator."""

    x_client_id: str | None
    x_redirect_uri: str | None
    linkedin_client_id: str | None
    linkedin_redirect_uri: str | None
    linkedin_version: str | None


@dataclass(frozen=True, slots=True)
class ConnectedPlatform:
    """Ephemeral values to export into the current terminal session."""

    platform: Literal["x", "linkedin"]
    values: Mapping[str, str]


def connect(
    platform: ConnectPlatform,
    settings: OAuthSettings,
    *,
    timeout_seconds: float = 300.0,
    browser_open: Callable[[str], bool] = webbrowser.open,
) -> tuple[ConnectedPlatform, ...]:
    """Authorize selected platforms locally without persisting OAuth secrets."""
    if timeout_seconds <= 0:
        raise ConfigurationError("OAuth callback timeout must be greater than zero")
    platforms = ("x", "linkedin") if platform == "all" else (platform,)
    results: list[ConnectedPlatform] = []
    for selected in platforms:
        if selected == "x":
            results.append(_connect_x(settings, timeout_seconds, browser_open))
        else:
            results.append(_connect_linkedin(settings, timeout_seconds, browser_open))
    return tuple(results)


def format_exports(results: tuple[ConnectedPlatform, ...]) -> str:
    """Return shell-safe, session-only export commands for the new tokens."""
    lines = ["Run these commands in this terminal session:"]
    for result in results:
        for name, value in result.values.items():
            lines.append(f"export {name}={shlex.quote(value)}")
    return "\n".join(lines)


def _connect_x(
    settings: OAuthSettings,
    timeout_seconds: float,
    browser_open: Callable[[str], bool],
) -> ConnectedPlatform:
    client_id, redirect_uri = _required_registration(
        "X", settings.x_client_id, settings.x_redirect_uri
    )
    verifier = _code_verifier()
    state = secrets.token_urlsafe(32)
    authorization_url = _authorization_url(
        _X_AUTHORIZE_URL,
        client_id=client_id,
        redirect_uri=redirect_uri,
        scopes=("tweet.read", "tweet.write", "users.read", "media.write"),
        state=state,
        code_challenge=_code_challenge(verifier),
    )
    callback = _receive_callback(
        redirect_uri, state, authorization_url, timeout_seconds, browser_open
    )
    token = _exchange_token(
        _X_TOKEN_URL,
        {
            "grant_type": "authorization_code",
            "code": _callback_code(callback),
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "code_verifier": verifier,
        },
    )
    return ConnectedPlatform("x", {"X_ACCESS_TOKEN": token})


def _connect_linkedin(
    settings: OAuthSettings,
    timeout_seconds: float,
    browser_open: Callable[[str], bool],
) -> ConnectedPlatform:
    client_id, redirect_uri = _required_registration(
        "LINKEDIN", settings.linkedin_client_id, settings.linkedin_redirect_uri
    )
    if not settings.linkedin_version:
        raise ConfigurationError("LINKEDIN_API_VERSION is required for LinkedIn")
    verifier = _code_verifier()
    state = secrets.token_urlsafe(32)
    authorization_url = _authorization_url(
        _LINKEDIN_AUTHORIZE_URL,
        client_id=client_id,
        redirect_uri=redirect_uri,
        scopes=("openid", "profile", "w_member_social"),
        state=state,
        code_challenge=_code_challenge(verifier),
    )
    callback = _receive_callback(
        redirect_uri, state, authorization_url, timeout_seconds, browser_open
    )
    token = _exchange_token(
        _LINKEDIN_TOKEN_URL,
        {
            "grant_type": "authorization_code",
            "code": _callback_code(callback),
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "code_verifier": verifier,
        },
    )
    member_id = _linkedin_member_id(token)
    return ConnectedPlatform(
        "linkedin",
        {
            "LINKEDIN_ACCESS_TOKEN": token,
            "LINKEDIN_AUTHOR_URN": f"urn:li:person:{member_id}",
            "LINKEDIN_API_VERSION": settings.linkedin_version,
        },
    )


def _required_registration(
    provider: str, client_id: str | None, redirect_uri: str | None
) -> tuple[str, str]:
    missing = [
        name
        for name, value in (
            (f"{provider}_CLIENT_ID", client_id),
            (f"{provider}_REDIRECT_URI", redirect_uri),
        )
        if not value
    ]
    if missing:
        raise ConfigurationError(
            "OAuth registration is not configured; set " + ", ".join(missing)
        )
    assert client_id is not None
    assert redirect_uri is not None
    _validate_loopback_redirect_uri(redirect_uri)
    return client_id, redirect_uri


def _validate_loopback_redirect_uri(redirect_uri: str) -> None:
    parsed = urlparse(redirect_uri)
    if (
        parsed.scheme != "http"
        or parsed.hostname != "127.0.0.1"
        or parsed.port is None
        or parsed.query
        or parsed.fragment
    ):
        raise ConfigurationError(
            "OAuth redirect URI must be an exact http://127.0.0.1:<port>/... "
            "loopback callback"
        )


def _code_verifier() -> str:
    return secrets.token_urlsafe(64)


def _code_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def _authorization_url(
    endpoint: str,
    *,
    client_id: str,
    redirect_uri: str,
    scopes: tuple[str, ...],
    state: str,
    code_challenge: str,
) -> str:
    parameters = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": " ".join(scopes),
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    return f"{endpoint}?{urlencode(parameters)}"


def _receive_callback(
    redirect_uri: str,
    state: str,
    authorization_url: str,
    timeout_seconds: float,
    browser_open: Callable[[str], bool],
) -> dict[str, str]:
    parsed = urlparse(redirect_uri)
    assert parsed.hostname is not None
    assert parsed.port is not None
    received: dict[str, str] = {}

    class CallbackHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            request = urlparse(self.path)
            if request.path != parsed.path:
                self.send_error(404)
                return
            values = parse_qs(request.query)
            received.update(
                {name: value[0] for name, value in values.items() if len(value) == 1}
            )
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"Authorization received. You can close this window.")

        def log_message(self, format: str, *args: object) -> None:
            del format, args

    try:
        server = HTTPServer((parsed.hostname, parsed.port), CallbackHandler)
    except OSError as exc:
        raise ConfigurationError(
            "Could not start the local OAuth callback server"
        ) from exc
    with server:
        server.timeout = min(timeout_seconds, 1.0)
        browser_open(authorization_url)
        deadline = time.monotonic() + timeout_seconds
        while not received and time.monotonic() < deadline:
            server.handle_request()
    if not received:
        raise SocialAgentError("OAuth authorization timed out without a callback")
    if received.get("state") != state:
        raise SocialAgentError(
            "OAuth callback state did not match the authorization request"
        )
    if "error" in received:
        raise SocialAgentError("OAuth authorization was not granted")
    return received


def _callback_code(callback: Mapping[str, str]) -> str:
    code = callback.get("code")
    if not code:
        raise SocialAgentError("OAuth callback did not include an authorization code")
    return code


def _exchange_token(endpoint: str, data: Mapping[str, str]) -> str:
    try:
        response = httpx.post(endpoint, data=data, timeout=30.0)
        response.raise_for_status()
        token = response.json().get("access_token")
    except (httpx.HTTPError, TypeError, ValueError) as exc:
        raise SocialAgentError("OAuth token exchange did not complete") from exc
    if not isinstance(token, str) or not token:
        raise SocialAgentError("OAuth token response did not include an access token")
    return token


def _linkedin_member_id(token: str) -> str:
    try:
        response = httpx.get(
            _LINKEDIN_USERINFO_URL,
            headers={"Authorization": f"Bearer {token}"},
            timeout=30.0,
        )
        response.raise_for_status()
        member_id = response.json().get("sub")
    except (httpx.HTTPError, TypeError, ValueError) as exc:
        raise SocialAgentError(
            "Could not retrieve the LinkedIn member identity"
        ) from exc
    if not isinstance(member_id, str) or not member_id:
        raise SocialAgentError("LinkedIn userinfo response did not include a member ID")
    return member_id
