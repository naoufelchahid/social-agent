"""Canonical URL identity for queue deduplication and post IDs."""

from __future__ import annotations

from hashlib import sha256
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from social_media_agent.errors import ConfigurationError


class InvalidUrlError(ConfigurationError):
    """Raised when a queue URL is unsupported or unsafe."""


_TRACKING_KEYS = {"fbclid", "gclid", "mc_cid", "mc_eid"}
_YOUTUBE_HOSTS = {"m.youtube.com", "www.youtube.com", "youtube.com"}
_REDDIT_HOSTS = {"np.reddit.com", "old.reddit.com", "www.reddit.com"}


def normalize_url(raw_url: str) -> str:
    """Return a stable HTTP URL while preserving content-significant parts."""
    try:
        parsed = urlsplit(raw_url.strip())
        port = parsed.port
    except ValueError as exc:
        raise InvalidUrlError(f"Invalid URL: {raw_url}") from exc

    scheme = parsed.scheme.lower()
    if scheme not in {"http", "https"} or not parsed.hostname:
        raise InvalidUrlError(f"Expected an HTTP URL: {raw_url}")
    if parsed.username is not None or parsed.password is not None:
        raise InvalidUrlError("URLs containing credentials are not allowed")

    host = parsed.hostname.lower()
    path = parsed.path or "/"
    query_items = _without_tracking(parse_qsl(parsed.query, keep_blank_values=True))

    if host == "youtu.be":
        video_id = path.strip("/")
        if not video_id:
            raise InvalidUrlError("YouTube short URL is missing a video ID")
        host = "youtube.com"
        path = "/watch"
        query_items = [(key, value) for key, value in query_items if key != "v"]
        query_items.append(("v", video_id))
    elif host in _YOUTUBE_HOSTS:
        host = "youtube.com"
    elif host in _REDDIT_HOSTS:
        host = "reddit.com"

    if path != "/":
        path = path.rstrip("/")

    default_port = (scheme == "https" and port == 443) or (
        scheme == "http" and port == 80
    )
    netloc = host if port is None or default_port else f"{host}:{port}"
    query = urlencode(sorted(query_items))
    return urlunsplit((scheme, netloc, path, query, ""))


def post_id_for_url(raw_url: str) -> str:
    """Return a stable short identifier for a canonical URL."""
    normalized = normalize_url(raw_url)
    return sha256(normalized.encode("utf-8")).hexdigest()[:16]


def _without_tracking(items: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Remove known marketing parameters without discarding useful queries."""
    return [
        (key, value)
        for key, value in items
        if not key.lower().startswith("utm_") and key.lower() not in _TRACKING_KEYS
    ]
