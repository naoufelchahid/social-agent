"""Tests for canonical URL identity."""

import pytest

from social_media_agent.urls import InvalidUrlError, normalize_url, post_id_for_url


@pytest.mark.parametrize(
    ("raw_url", "expected"),
    [
        (
            "HTTPS://Example.COM:443/path/?b=2&utm_campaign=x&a=1#fragment",
            "https://example.com/path?a=1&b=2",
        ),
        (
            "https://youtu.be/AbC123?t=30&utm_source=x",
            "https://youtube.com/watch?t=30&v=AbC123",
        ),
        (
            "https://old.reddit.com/r/Python/comments/abc/Post/",
            "https://reddit.com/r/Python/comments/abc/Post",
        ),
        ("http://example.com:80/", "http://example.com/"),
    ],
)
def test_normalize_url_canonicalizes_identity(raw_url: str, expected: str) -> None:
    """Equivalent URL forms should collapse without changing path semantics."""
    assert normalize_url(raw_url) == expected


@pytest.mark.parametrize(
    "raw_url",
    [
        "ftp://example.com/file",
        "https://user:password@example.com/private",
        "https:///missing-host",
    ],
)
def test_normalize_url_rejects_unsafe_or_unsupported_urls(raw_url: str) -> None:
    """Only credential-free HTTP URLs are valid queue inputs."""
    with pytest.raises(InvalidUrlError):
        normalize_url(raw_url)


def test_post_id_is_stable_for_equivalent_urls() -> None:
    """Tracking variants of a URL should map to one persisted job identity."""
    first = post_id_for_url("https://example.com/post?utm_source=a")
    second = post_id_for_url("https://EXAMPLE.com/post/#heading")

    assert first == second
    assert len(first) == 16
