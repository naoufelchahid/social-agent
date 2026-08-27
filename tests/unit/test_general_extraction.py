"""Tests for the bounded general-page HTTP fallback."""

import httpx
import pytest
import respx

from social_media_agent.errors import ExtractionError
from social_media_agent.extraction import ExtractionRequest, GeneralPageExtractor
from social_media_agent.models import ExtractionMethod, SourceType

ARTICLE_HTML = """
<html>
  <head>
    <title>Fixture page</title>
    <meta name="author" content="Ada Example">
  </head>
  <body>
    <nav>Navigation that should not become the article.</nav>
    <article>
      <h1>Useful heading</h1>
      <p>This is meaningful source evidence for the local draft workflow.</p>
      <p>It contains a second grounded paragraph for readable extraction.</p>
    </article>
  </body>
</html>
"""


class UnknownLengthStream(httpx.AsyncByteStream):
    """Async response body that deliberately omits Content-Length."""

    async def __aiter__(self):  # type: ignore[no-untyped-def]
        yield b"<article>source "
        yield b"text larger than cap</article>"


def _request(url: str = "https://example.com/article") -> ExtractionRequest:
    return ExtractionRequest(normalized_url=url, source_type=SourceType.GENERAL)


@respx.mock
@pytest.mark.asyncio
async def test_general_fallback_streams_and_extracts_readable_text() -> None:
    """A bounded fetch should retain final-URL and readable-text provenance."""
    respx.get("https://example.com/article").mock(
        return_value=httpx.Response(
            302,
            headers={"location": "https://example.com/canonical"},
        )
    )
    respx.get("https://example.com/canonical").mock(
        return_value=httpx.Response(
            200,
            headers={"content-type": "text/html; charset=utf-8"},
            text=ARTICLE_HTML,
        )
    )
    extractor = GeneralPageExtractor(
        timeout_seconds=2,
        max_redirects=2,
        max_response_bytes=10_000,
    )

    source = await extractor.extract(_request())

    assert source.canonical_url == "https://example.com/canonical"
    assert source.source_type is SourceType.GENERAL
    assert source.title == "Useful heading"
    assert source.author == "Ada Example"
    assert "Useful heading" in source.content
    assert "meaningful source evidence" in source.content
    assert "Navigation" not in source.content
    assert source.extraction_method is ExtractionMethod.GENERAL_HTTP
    assert source.metadata == {
        "http": {
            "content_type": "text/html; charset=utf-8",
            "status_code": 200,
        }
    }


@respx.mock
@pytest.mark.asyncio
async def test_general_fallback_enforces_redirect_limit() -> None:
    """Redirect loops must terminate at the configured client boundary."""
    respx.get("https://example.com/article").mock(
        return_value=httpx.Response(
            302,
            headers={"location": "https://example.com/article"},
        )
    )
    extractor = GeneralPageExtractor(max_redirects=1)

    with pytest.raises(ExtractionError, match="redirect limit"):
        await extractor.extract(_request())


@respx.mock
@pytest.mark.asyncio
async def test_general_fallback_rejects_oversized_streamed_response() -> None:
    """The byte cap must apply while reading, even without Content-Length."""
    respx.get("https://example.com/article").mock(
        return_value=httpx.Response(
            200,
            headers={"content-type": "text/html"},
            stream=UnknownLengthStream(),
        )
    )
    extractor = GeneralPageExtractor(max_response_bytes=16)

    with pytest.raises(ExtractionError, match="response size limit"):
        await extractor.extract(_request())


@respx.mock
@pytest.mark.asyncio
async def test_general_fallback_reports_timeout_without_upstream_detail() -> None:
    """Transport timeouts should become stable extraction errors."""
    respx.get("https://example.com/article").mock(
        side_effect=httpx.ReadTimeout("sensitive transport detail")
    )
    extractor = GeneralPageExtractor(timeout_seconds=0.1)

    with pytest.raises(ExtractionError, match="timed out") as raised:
        await extractor.extract(_request())

    assert "sensitive" not in str(raised.value)


@respx.mock
@pytest.mark.asyncio
async def test_general_fallback_reports_http_failure() -> None:
    """Non-success status codes should fail before body extraction."""
    respx.get("https://example.com/article").mock(
        return_value=httpx.Response(503, text="private upstream response")
    )
    extractor = GeneralPageExtractor()

    with pytest.raises(ExtractionError, match="HTTP status 503") as raised:
        await extractor.extract(_request())

    assert "private upstream" not in str(raised.value)


@respx.mock
@pytest.mark.asyncio
async def test_general_fallback_rejects_page_without_readable_text() -> None:
    """A successful fetch is unusable when Trafilatura finds no evidence."""
    respx.get("https://example.com/article").mock(
        return_value=httpx.Response(
            200,
            headers={"content-type": "text/html"},
            text="<html><head><title>Empty</title></head><body></body></html>",
        )
    )
    extractor = GeneralPageExtractor()

    with pytest.raises(ExtractionError, match="no readable content"):
        await extractor.extract(_request())


def test_general_fallback_rejects_invalid_bounds() -> None:
    """Invalid resource bounds should fail before network access."""
    with pytest.raises(ValueError, match="timeout"):
        GeneralPageExtractor(timeout_seconds=0)
    with pytest.raises(ValueError, match="redirect"):
        GeneralPageExtractor(max_redirects=-1)
    with pytest.raises(ValueError, match="response size"):
        GeneralPageExtractor(max_response_bytes=0)
