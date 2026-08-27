import base64
import json
from collections.abc import Awaitable, Callable

import httpx
import pytest

from arcade_social_publisher.publishers import (
    LinkedInImagePublisher,
    PublicationError,
    XImagePublisher,
    decode_png,
)

PNG_BYTES = b"\x89PNG\r\n\x1a\nimage"
Handler = Callable[[httpx.Request], Awaitable[httpx.Response] | httpx.Response]


def _client(handler: Handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def test_decode_png_accepts_base64_encoded_png_only() -> None:
    encoded = base64.b64encode(PNG_BYTES).decode("ascii")

    assert decode_png(encoded, media_type="image/png") == PNG_BYTES
    with pytest.raises(PublicationError, match="PNG"):
        decode_png(encoded, media_type="image/jpeg")
    with pytest.raises(PublicationError, match="base64"):
        decode_png("not base64", media_type="image/png")


@pytest.mark.asyncio
async def test_x_publisher_uploads_image_then_creates_post() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/2/media/upload":
            return httpx.Response(200, json={"data": {"id": "media-1"}})
        return httpx.Response(201, json={"data": {"id": "post-1"}})

    async with _client(handler) as client:
        receipt = await XImagePublisher(client).publish(
            access_token="x-token",
            text="Approved X copy",
            image_bytes=PNG_BYTES,
        )

    assert receipt.post_id == "post-1"
    assert receipt.post_url == "https://x.com/i/web/status/post-1"
    assert json.loads(requests[0].content) == {
        "media": base64.b64encode(PNG_BYTES).decode("ascii"),
        "media_category": "tweet_image",
        "media_type": "image/png",
    }
    assert json.loads(requests[1].content) == {
        "text": "Approved X copy",
        "media": {"media_ids": ["media-1"]},
    }


@pytest.mark.asyncio
async def test_linkedin_publisher_uploads_image_then_creates_post() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/rest/images":
            return httpx.Response(
                200,
                json={
                    "value": {
                        "uploadUrl": "https://uploads.linkedin.test/image-1",
                        "image": "urn:li:image:image-1",
                    }
                },
            )
        if request.url.host == "uploads.linkedin.test":
            return httpx.Response(201)
        return httpx.Response(201, headers={"x-restli-id": "urn:li:share:post-1"})

    async with _client(handler) as client:
        receipt = await LinkedInImagePublisher(client).publish(
            access_token="linkedin-token",
            author_urn="urn:li:person:member-1",
            text="Approved LinkedIn copy",
            image_bytes=PNG_BYTES,
        )

    assert receipt.post_id == "urn:li:share:post-1"
    assert receipt.post_url == "https://www.linkedin.com/feed/update/urn:li:share:post-1"
    assert json.loads(requests[0].content) == {
        "initializeUploadRequest": {"owner": "urn:li:person:member-1"}
    }
    assert requests[1].content == PNG_BYTES
    assert json.loads(requests[2].content)["content"] == {"media": {"id": "urn:li:image:image-1"}}
