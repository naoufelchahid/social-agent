"""Tests for direct OAuth 2.0 image publication."""

import base64
import json

import httpx
import pytest

from social_media_agent.publication import (
    DirectOAuthPublisher,
    PublicationRequest,
    PublisherSettings,
)


@pytest.mark.asyncio
async def test_publisher_posts_exact_png_to_x_before_linkedin() -> None:
    png = b"\x89PNG\r\n\x1a\nimage-bytes"
    calls: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if request.url == "https://api.x.com/2/media/upload":
            assert request.headers["authorization"] == "Bearer x-token"
            assert json.loads(request.content) == {
                "media": base64.b64encode(png).decode("ascii"),
                "media_category": "tweet_image",
                "media_type": "image/png",
            }
            return httpx.Response(200, json={"data": {"id": "x-media"}})
        if request.url == "https://api.x.com/2/tweets":
            assert json.loads(request.content) == {
                "text": "X-specific copy",
                "media": {"media_ids": ["x-media"]},
            }
            return httpx.Response(201, json={"data": {"id": "x-post"}})
        if (
            request.url
            == "https://api.linkedin.com/rest/images?action=initializeUpload"
        ):
            assert request.headers["authorization"] == "Bearer linkedin-token"
            assert json.loads(request.content) == {
                "initializeUploadRequest": {"owner": "urn:li:person:member"}
            }
            return httpx.Response(
                200,
                json={
                    "value": {
                        "image": "urn:li:image:asset",
                        "uploadUrl": "https://upload.linkedin.example/image",
                    }
                },
            )
        if request.url == "https://upload.linkedin.example/image":
            assert request.content == png
            assert request.headers["content-type"] == "image/png"
            return httpx.Response(201)
        if request.url == "https://api.linkedin.com/rest/posts":
            assert json.loads(request.content) == {
                "author": "urn:li:person:member",
                "commentary": "LinkedIn-specific copy",
                "visibility": "PUBLIC",
                "distribution": {
                    "feedDistribution": "MAIN_FEED",
                    "targetEntities": [],
                    "thirdPartyDistributionChannels": [],
                },
                "content": {"media": {"id": "urn:li:image:asset"}},
                "lifecycleState": "PUBLISHED",
                "isReshareDisabledByAuthor": False,
            }
            return httpx.Response(201, headers={"x-restli-id": "urn:li:share:post"})
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    publisher = DirectOAuthPublisher(
        PublisherSettings(
            x_access_token="x-token",
            linkedin_access_token="linkedin-token",
            linkedin_author_urn="urn:li:person:member",
            linkedin_version="202608",
        ),
        transport=httpx.MockTransport(handler),
    )

    result = await publisher.publish(
        PublicationRequest(
            post_id="post-1",
            x_text="X-specific copy",
            linkedin_text="LinkedIn-specific copy",
            image_bytes=png,
        )
    )

    assert [attempt.platform for attempt in result.attempts] == ["x", "linkedin"]
    assert [attempt.state for attempt in result.attempts] == ["published", "published"]
    assert result.attempts[0].remote_id == "x-post"
    assert result.attempts[1].remote_id == "urn:li:share:post"
    assert [request.url.host for request in calls] == [
        "api.x.com",
        "api.x.com",
        "api.linkedin.com",
        "upload.linkedin.example",
        "api.linkedin.com",
    ]


@pytest.mark.asyncio
async def test_uncertain_x_post_does_not_start_linkedin_or_retry() -> None:
    calls: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if request.url == "https://api.x.com/2/media/upload":
            return httpx.Response(200, json={"data": {"id": "x-media"}})
        if request.url == "https://api.x.com/2/tweets":
            return httpx.Response(503)
        raise AssertionError("LinkedIn must not start after an uncertain X post")

    publisher = DirectOAuthPublisher(
        PublisherSettings(
            x_access_token="x-token",
            linkedin_access_token="linkedin-token",
            linkedin_author_urn="urn:li:person:member",
            linkedin_version="202608",
        ),
        transport=httpx.MockTransport(handler),
    )

    result = await publisher.publish(
        PublicationRequest(
            post_id="post-1",
            x_text="X-specific copy",
            linkedin_text="LinkedIn-specific copy",
            image_bytes=b"\x89PNG\r\n\x1a\nimage-bytes",
        )
    )

    assert result.attempts[0].state == "unknown"
    assert [request.url.host for request in calls] == ["api.x.com", "api.x.com"]
