"""Tests for YouTube public metadata and transcript extraction."""

from dataclasses import dataclass, field

import httpx
import pytest
import respx
from youtube_transcript_api import FetchedTranscript, FetchedTranscriptSnippet
from youtube_transcript_api._errors import TranscriptsDisabled

from social_media_agent.errors import ExtractionError
from social_media_agent.extraction import (
    ExtractionRequest,
    YouTubeTranscriptExtractor,
    YouTubeTranscriptUnavailableError,
    youtube_video_id,
)
from social_media_agent.models import ExtractionMethod, SourceType

VIDEO_ID = "AbC123def45"
WATCH_URL = f"https://youtube.com/watch?v={VIDEO_ID}"
OEMBED_URL = "https://www.youtube.com/oembed"


@dataclass
class FakeTranscriptClient:
    """Synchronous transcript-library fake used through the thread adapter."""

    result: object | None = None
    error: Exception | None = None
    calls: list[tuple[str, tuple[str, ...]]] = field(default_factory=list)

    def fetch(self, video_id: str, languages: tuple[str, ...]) -> object:
        self.calls.append((video_id, languages))
        if self.error is not None:
            raise self.error
        return self.result


def _request(url: str = WATCH_URL) -> ExtractionRequest:
    return ExtractionRequest(normalized_url=url, source_type=SourceType.YOUTUBE)


def _transcript() -> FetchedTranscript:
    return FetchedTranscript(
        snippets=[
            FetchedTranscriptSnippet("First grounded sentence.", 0.0, 2.0),
            FetchedTranscriptSnippet("Second grounded sentence.", 2.0, 3.0),
        ],
        video_id=VIDEO_ID,
        language="English",
        language_code="en",
        is_generated=False,
    )


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        (WATCH_URL, VIDEO_ID),
        (f"https://youtu.be/{VIDEO_ID}", VIDEO_ID),
        (f"https://youtube.com/shorts/{VIDEO_ID}", VIDEO_ID),
        (f"https://youtube.com/embed/{VIDEO_ID}", VIDEO_ID),
        (f"https://youtube.com/live/{VIDEO_ID}", VIDEO_ID),
    ],
)
def test_youtube_video_id_supports_public_url_forms(url: str, expected: str) -> None:
    """Known watch, short, embed, and live forms should yield one stable ID."""
    assert youtube_video_id(url) == expected


@respx.mock
@pytest.mark.asyncio
async def test_youtube_fallback_combines_oembed_metadata_and_transcript() -> None:
    """Public metadata and transcript snippets should form source evidence."""
    metadata = respx.get(OEMBED_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "title": "Fixture video",
                "author_name": "Fixture channel",
                "author_url": "https://www.youtube.com/@fixture",
                "provider_name": "YouTube",
                "type": "video",
            },
        )
    )
    client = FakeTranscriptClient(result=_transcript())
    extractor = YouTubeTranscriptExtractor(
        transcript_client=client,
        languages=("en", "fr"),
    )

    source = await extractor.extract(_request())

    assert source.canonical_url == WATCH_URL
    assert source.title == "Fixture video"
    assert source.author == "Fixture channel"
    assert source.content == ("First grounded sentence.\nSecond grounded sentence.")
    assert source.extraction_method is ExtractionMethod.YOUTUBE_TRANSCRIPT
    assert source.metadata == {
        "youtube": {
            "generated_transcript": False,
            "language": "English",
            "language_code": "en",
            "video_id": VIDEO_ID,
        }
    }
    assert client.calls == [(VIDEO_ID, ("en", "fr"))]
    assert dict(metadata.calls[0].request.url.params) == {
        "format": "json",
        "url": WATCH_URL,
    }


@respx.mock
@pytest.mark.asyncio
async def test_youtube_transcript_unavailable_has_precise_error() -> None:
    """Missing captions must fail explicitly instead of producing empty evidence."""
    respx.get(OEMBED_URL).mock(
        return_value=httpx.Response(
            200,
            json={"title": "No captions", "author_name": "Channel"},
        )
    )
    client = FakeTranscriptClient(error=TranscriptsDisabled(VIDEO_ID))
    extractor = YouTubeTranscriptExtractor(transcript_client=client)

    with pytest.raises(
        YouTubeTranscriptUnavailableError,
        match="transcript unavailable",
    ) as raised:
        await extractor.extract(_request())

    assert VIDEO_ID in str(raised.value)
    assert "invent" not in str(raised.value).lower()


@respx.mock
@pytest.mark.asyncio
async def test_youtube_empty_transcript_is_unavailable() -> None:
    """A transcript object without usable text is not source evidence."""
    respx.get(OEMBED_URL).mock(
        return_value=httpx.Response(
            200,
            json={"title": "Empty captions", "author_name": "Channel"},
        )
    )
    empty = FetchedTranscript(
        snippets=[FetchedTranscriptSnippet("   ", 0.0, 1.0)],
        video_id=VIDEO_ID,
        language="English",
        language_code="en",
        is_generated=True,
    )
    extractor = YouTubeTranscriptExtractor(
        transcript_client=FakeTranscriptClient(result=empty)
    )

    with pytest.raises(YouTubeTranscriptUnavailableError):
        await extractor.extract(_request())


@respx.mock
@pytest.mark.asyncio
async def test_youtube_metadata_http_failure_is_non_sensitive() -> None:
    """A missing video should fail before transcript retrieval."""
    respx.get(OEMBED_URL).mock(
        return_value=httpx.Response(404, text="private upstream response")
    )
    client = FakeTranscriptClient(result=_transcript())

    with pytest.raises(ExtractionError, match=r"metadata.*HTTP status 404") as raised:
        await YouTubeTranscriptExtractor(transcript_client=client).extract(_request())

    assert "private upstream" not in str(raised.value)
    assert client.calls == []


def test_youtube_rejects_invalid_video_url_and_bounds() -> None:
    """Invalid IDs and timeouts should fail before external work."""
    with pytest.raises(ExtractionError, match="video ID"):
        youtube_video_id("https://youtube.com/watch")
    with pytest.raises(ValueError, match="timeout"):
        YouTubeTranscriptExtractor(timeout_seconds=0)
    with pytest.raises(ValueError, match="language"):
        YouTubeTranscriptExtractor(languages=())
