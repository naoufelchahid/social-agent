"""Tests for public Reddit JSON extraction and readable-HTML fallback."""

import httpx
import pytest
import respx

from social_media_agent.errors import ExtractionError
from social_media_agent.extraction import ExtractionRequest, RedditPostExtractor
from social_media_agent.models import ExtractionMethod, SourceType

POST_URL = "https://reddit.com/r/python/comments/abc123/useful_post"
JSON_URL = f"{POST_URL}.json"
OLD_URL = "https://old.reddit.com/r/python/comments/abc123/useful_post"


def _request(url: str = POST_URL) -> ExtractionRequest:
    return ExtractionRequest(normalized_url=url, source_type=SourceType.REDDIT)


def _listing(*, title: object = "Useful post") -> list[object]:
    return [
        {
            "kind": "Listing",
            "data": {
                "children": [
                    {
                        "kind": "t3",
                        "data": {
                            "title": title,
                            "selftext": "Grounded post body.",
                            "author": "post_author",
                            "created_utc": 1_735_776_245,
                            "permalink": ("/r/python/comments/abc123/useful_post/"),
                            "subreddit": "python",
                            "score": 123,
                            "upvote_ratio": 0.97,
                        },
                    }
                ]
            },
        },
        {
            "kind": "Listing",
            "data": {
                "children": [
                    {
                        "kind": "t1",
                        "data": {
                            "author": "first",
                            "body": "First top-level insight.",
                            "replies": {
                                "kind": "Listing",
                                "data": {
                                    "children": [
                                        {
                                            "kind": "t1",
                                            "data": {
                                                "author": "nested",
                                                "body": "Nested reply to ignore.",
                                            },
                                        }
                                    ]
                                },
                            },
                        },
                    },
                    {
                        "kind": "more",
                        "data": {"children": ["later"]},
                    },
                    {
                        "kind": "t1",
                        "data": {
                            "author": "second",
                            "body": "Second top-level insight.",
                        },
                    },
                    {
                        "kind": "t1",
                        "data": {
                            "author": "third",
                            "body": "Third comment beyond the local cap.",
                        },
                    },
                ]
            },
        },
    ]


@respx.mock
@pytest.mark.asyncio
async def test_reddit_json_extracts_post_and_bounded_top_level_comments() -> None:
    """JSON should provide post evidence without traversing reply trees."""
    route = respx.get(JSON_URL).mock(return_value=httpx.Response(200, json=_listing()))
    extractor = RedditPostExtractor(max_comments=2)

    source = await extractor.extract(_request())

    assert source.canonical_url == POST_URL
    assert source.title == "Useful post"
    assert source.author == "post_author"
    assert source.published_at is not None
    assert source.extraction_method is ExtractionMethod.REDDIT_JSON
    assert "Grounded post body." in source.content
    assert "first: First top-level insight." in source.content
    assert "second: Second top-level insight." in source.content
    assert "Nested reply" not in source.content
    assert "Third comment" not in source.content
    assert source.metadata == {
        "reddit": {
            "comment_count": 2,
            "score": 123,
            "subreddit": "python",
            "upvote_ratio": 0.97,
        }
    }
    assert dict(route.calls[0].request.url.params) == {
        "depth": "1",
        "limit": "2",
        "raw_json": "1",
        "sort": "top",
    }
    assert route.calls[0].request.headers["user-agent"] == "social-media-agent"


@respx.mock
@pytest.mark.asyncio
async def test_reddit_http_failure_uses_readable_html_fallback() -> None:
    """Unavailable public JSON should fall back to old Reddit HTML."""
    respx.get(JSON_URL).mock(
        return_value=httpx.Response(403, text="private JSON failure")
    )
    respx.get(OLD_URL).mock(
        return_value=httpx.Response(
            200,
            headers={"content-type": "text/html; charset=utf-8"},
            text="""
            <html><body><article>
              <h1>Readable Reddit post</h1>
              <p>This HTML fallback contains grounded discussion evidence.</p>
              <p>A second paragraph makes the article extractable.</p>
            </article></body></html>
            """,
        )
    )

    source = await RedditPostExtractor().extract(_request())

    assert source.extraction_method is ExtractionMethod.REDDIT_HTML
    assert "grounded discussion evidence" in source.content
    assert source.metadata["reddit"] == {"json_fallback_reason": "http_status"}
    assert "private JSON failure" not in source.model_dump_json()


@respx.mock
@pytest.mark.asyncio
async def test_reddit_malformed_json_uses_readable_html_fallback() -> None:
    """A response outside the two-listing contract should not be trusted."""
    respx.get(JSON_URL).mock(return_value=httpx.Response(200, json={"data": []}))
    respx.get(OLD_URL).mock(
        return_value=httpx.Response(
            200,
            text="""
            <html><body><article><h1>HTML title</h1>
            <p>Fallback body with enough meaningful readable source content
            about a concrete technical discussion and its practical context.</p>
            <p>A second grounded paragraph records the useful conclusion from
            the discussion for later drafting and independent review.</p>
            </article></body></html>
            """,
        )
    )

    source = await RedditPostExtractor().extract(_request())

    assert source.extraction_method is ExtractionMethod.REDDIT_HTML
    assert source.metadata["reddit"] == {"json_fallback_reason": "malformed_response"}


@respx.mock
@pytest.mark.asyncio
async def test_reddit_unusable_post_json_uses_html_fallback() -> None:
    """A structurally valid listing still needs a usable post title."""
    respx.get(JSON_URL).mock(
        return_value=httpx.Response(200, json=_listing(title="   "))
    )
    respx.get(OLD_URL).mock(
        return_value=httpx.Response(
            200,
            text="""
            <html><body><article><h1>Recovered title</h1>
            <p>Recovered readable evidence from the HTML representation with
            enough detail to describe the post's technical subject clearly.</p>
            <p>This second grounded paragraph preserves another useful point
            from the public discussion for the downstream writing stage.</p>
            </article></body></html>
            """,
        )
    )

    source = await RedditPostExtractor().extract(_request())

    assert source.metadata["reddit"] == {"json_fallback_reason": "unusable_response"}


@respx.mock
@pytest.mark.asyncio
async def test_reddit_reports_failure_when_json_and_html_are_unavailable() -> None:
    """Dual fallback failure should remain stable and non-sensitive."""
    respx.get(JSON_URL).mock(return_value=httpx.Response(429, text="secret JSON"))
    respx.get(OLD_URL).mock(return_value=httpx.Response(503, text="secret HTML"))

    with pytest.raises(
        ExtractionError, match="JSON and HTML fallbacks failed"
    ) as raised:
        await RedditPostExtractor().extract(_request())

    assert "secret" not in str(raised.value)


@pytest.mark.asyncio
async def test_reddit_rejects_non_post_url_before_network() -> None:
    """Subreddit listings do not identify one post for this workflow."""
    extractor = RedditPostExtractor()

    with pytest.raises(ExtractionError, match="Reddit post URL"):
        await extractor.extract(_request("https://reddit.com/r/python"))


def test_reddit_rejects_invalid_resource_bounds() -> None:
    """HTTP and comment bounds must be positive."""
    with pytest.raises(ValueError, match="timeout"):
        RedditPostExtractor(timeout_seconds=0)
    with pytest.raises(ValueError, match="comment count"):
        RedditPostExtractor(max_comments=0)
    with pytest.raises(ValueError, match="response size"):
        RedditPostExtractor(max_response_bytes=0)
