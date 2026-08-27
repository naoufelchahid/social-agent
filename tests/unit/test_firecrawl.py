"""Tests for Firecrawl-first extraction and recoverable fallback policy."""

from dataclasses import dataclass, field
from typing import Any

import pytest
from firecrawl.v2.types import Document, DocumentMetadata

from social_media_agent.extraction import (
    ExtractionDispatcher,
    ExtractionRequest,
    FirecrawlExtractor,
    FirecrawlFallbackError,
)
from social_media_agent.models import (
    ExtractedSource,
    ExtractionMethod,
    FirecrawlFallbackReason,
    SourceType,
)


@dataclass
class FakeFirecrawlClient:
    """Synchronous SDK-shaped fake used without external HTTP."""

    result: object | None = None
    error: Exception | None = None
    calls: list[tuple[str, dict[str, Any]]] = field(default_factory=list)

    def scrape(self, url: str, **kwargs: Any) -> object:
        self.calls.append((url, kwargs))
        if self.error is not None:
            raise self.error
        return self.result


@dataclass
class RecordingFallback:
    """Fallback extractor that returns evidence suitable for annotation."""

    calls: list[ExtractionRequest] = field(default_factory=list)

    async def extract(self, request: ExtractionRequest) -> ExtractedSource:
        self.calls.append(request)
        return ExtractedSource(
            canonical_url=request.normalized_url,
            source_type=request.source_type,
            title="Fallback title",
            content="Fallback content",
            extraction_method=ExtractionMethod.GENERAL_HTTP,
            metadata={"fallback": "general"},
        )


class StatusError(Exception):
    """SDK-like failure carrying an HTTP response status."""

    def __init__(self, status_code: int) -> None:
        super().__init__(f"sensitive upstream detail for {status_code}")
        self.status_code = status_code


@pytest.mark.asyncio
async def test_firecrawl_adapter_maps_a_document_to_source_provenance() -> None:
    """Usable Markdown and metadata should become the common source model."""
    client = FakeFirecrawlClient(
        result=Document(
            markdown="  # Useful evidence\n\nA grounded paragraph.  ",
            metadata=DocumentMetadata(
                title="Firecrawl title",
                source_url="https://example.com/canonical",
                published_time="2026-08-24T12:30:00Z",
                status_code=200,
                author="Ada Example",
            ),
        )
    )
    extractor = FirecrawlExtractor(
        api_key="test-key",
        client=client,
        timeout_seconds=12,
    )
    request = ExtractionRequest(
        normalized_url="https://example.com/requested",
        source_type=SourceType.GENERAL,
    )

    source = await extractor.extract(request)

    assert source.canonical_url == "https://example.com/canonical"
    assert source.title == "Firecrawl title"
    assert source.author == "Ada Example"
    assert source.published_at is not None
    assert source.content == "# Useful evidence\n\nA grounded paragraph."
    assert source.extraction_method is ExtractionMethod.FIRECRAWL
    assert source.metadata["firecrawl"] == {
        "attempted": True,
        "status_code": 200,
    }
    assert client.calls == [
        (
            "https://example.com/requested",
            {
                "formats": ["markdown"],
                "only_main_content": True,
                "timeout": 12000,
            },
        )
    ]


@pytest.mark.parametrize(
    ("client", "expected_reason"),
    [
        (
            FakeFirecrawlClient(error=TimeoutError("secret timeout detail")),
            FirecrawlFallbackReason.TIMEOUT,
        ),
        (
            FakeFirecrawlClient(error=StatusError(408)),
            FirecrawlFallbackReason.TIMEOUT,
        ),
        (
            FakeFirecrawlClient(error=StatusError(429)),
            FirecrawlFallbackReason.RATE_LIMIT,
        ),
        (
            FakeFirecrawlClient(result={"markdown": "not an SDK document"}),
            FirecrawlFallbackReason.MALFORMED_RESPONSE,
        ),
        (
            FakeFirecrawlClient(result=Document(markdown="   ")),
            FirecrawlFallbackReason.UNUSABLE_RESPONSE,
        ),
        (
            FakeFirecrawlClient(error=StatusError(500)),
            FirecrawlFallbackReason.SERVICE_ERROR,
        ),
    ],
)
@pytest.mark.asyncio
async def test_firecrawl_adapter_categorizes_recoverable_failures(
    client: FakeFirecrawlClient,
    expected_reason: FirecrawlFallbackReason,
) -> None:
    """SDK and response failures should cross one typed policy boundary."""
    extractor = FirecrawlExtractor(api_key="test-key", client=client)
    request = ExtractionRequest(
        normalized_url="https://example.com/article",
        source_type=SourceType.GENERAL,
    )

    with pytest.raises(FirecrawlFallbackError) as raised:
        await extractor.extract(request)

    assert raised.value.reason is expected_reason
    assert "secret" not in str(raised.value)
    assert "sensitive" not in str(raised.value)


@pytest.mark.asyncio
async def test_dispatcher_records_missing_configuration_on_fallback() -> None:
    """No API key should skip Firecrawl and remain visible in provenance."""
    fallback = RecordingFallback()
    dispatcher = ExtractionDispatcher(fallbacks={SourceType.GENERAL: fallback})

    source = await dispatcher.extract("https://example.com/article")

    assert source.metadata == {
        "fallback": "general",
        "firecrawl": {
            "attempted": False,
            "fallback_reason": "missing_configuration",
        },
        "content_processing": {
            "original_chars": 16,
            "sanitized_chars": 16,
            "stored_chars": 16,
            "truncated": False,
        },
    }
    assert len(fallback.calls) == 1


@pytest.mark.asyncio
async def test_dispatcher_records_primary_failure_and_invokes_fallback() -> None:
    """A recoverable Firecrawl failure should route once to the same source type."""
    fallback = RecordingFallback()
    firecrawl = FirecrawlExtractor(
        api_key="test-key",
        client=FakeFirecrawlClient(error=StatusError(429)),
    )
    dispatcher = ExtractionDispatcher(
        fallbacks={SourceType.GENERAL: fallback},
        firecrawl=firecrawl,
    )

    source = await dispatcher.extract("https://example.com/article")

    assert source.extraction_method is ExtractionMethod.GENERAL_HTTP
    assert source.metadata["firecrawl"] == {
        "attempted": True,
        "fallback_reason": "rate_limit",
    }
    assert len(fallback.calls) == 1
