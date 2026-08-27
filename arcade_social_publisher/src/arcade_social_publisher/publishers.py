"""Direct platform adapters for image-complete social publication."""

from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass

import httpx


class PublicationError(Exception):
    """Raised when a platform response cannot prove a published post."""


@dataclass(frozen=True)
class PublicationReceipt:
    """The durable remote identity returned by one successful publication."""

    post_id: str
    post_url: str | None


class XImagePublisher:
    """Publish one PNG image and post through X's v2 media and post endpoints."""

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def publish(
        self,
        *,
        access_token: str,
        text: str,
        image_bytes: bytes,
    ) -> PublicationReceipt:
        headers = _bearer_headers(access_token)
        upload = await self._client.post(
            "https://api.x.com/2/media/upload",
            headers=headers,
            json={
                "media": base64.b64encode(image_bytes).decode("ascii"),
                "media_category": "tweet_image",
                "media_type": "image/png",
            },
        )
        upload.raise_for_status()
        media_id = _required_string(upload.json(), "data", "id")

        post = await self._client.post(
            "https://api.x.com/2/tweets",
            headers=headers,
            json={"text": text, "media": {"media_ids": [media_id]}},
        )
        post.raise_for_status()
        post_id = _required_string(post.json(), "data", "id")
        return PublicationReceipt(
            post_id=post_id,
            post_url=f"https://x.com/i/web/status/{post_id}",
        )


class LinkedInImagePublisher:
    """Publish one PNG image and post through LinkedIn's Images and Posts APIs."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        api_version: str = "202608",
    ) -> None:
        self._client = client
        self._api_version = api_version

    async def publish(
        self,
        *,
        access_token: str,
        author_urn: str,
        text: str,
        image_bytes: bytes,
    ) -> PublicationReceipt:
        headers = {
            **_bearer_headers(access_token),
            "Linkedin-Version": self._api_version,
            "X-Restli-Protocol-Version": "2.0.0",
        }
        initialized = await self._client.post(
            "https://api.linkedin.com/rest/images?action=initializeUpload",
            headers=headers,
            json={"initializeUploadRequest": {"owner": author_urn}},
        )
        initialized.raise_for_status()
        upload_url = _required_string(initialized.json(), "value", "uploadUrl")
        image_urn = _required_string(initialized.json(), "value", "image")

        upload = await self._client.put(
            upload_url,
            content=image_bytes,
            headers={"Content-Type": "image/png"},
        )
        upload.raise_for_status()

        post = await self._client.post(
            "https://api.linkedin.com/rest/posts",
            headers=headers,
            json={
                "author": author_urn,
                "commentary": text,
                "visibility": "PUBLIC",
                "distribution": {
                    "feedDistribution": "MAIN_FEED",
                    "targetEntities": [],
                    "thirdPartyDistributionChannels": [],
                },
                "content": {"media": {"id": image_urn}},
                "lifecycleState": "PUBLISHED",
                "isReshareDisabledByAuthor": False,
            },
        )
        post.raise_for_status()
        post_id = post.headers.get("x-restli-id")
        if not post_id:
            raise PublicationError("LinkedIn did not return an x-restli-id receipt")
        return PublicationReceipt(
            post_id=post_id,
            post_url=f"https://www.linkedin.com/feed/update/{post_id}",
        )


def _bearer_headers(access_token: str) -> dict[str, str]:
    if not access_token.strip():
        raise PublicationError("Missing platform OAuth access token")
    return {"Authorization": f"Bearer {access_token}"}


def decode_png(image_base64: str, *, media_type: str) -> bytes:
    """Decode exactly one PNG image from the private tool contract."""
    if media_type != "image/png":
        raise PublicationError("Only PNG images are supported")
    try:
        image_bytes = base64.b64decode(image_base64, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise PublicationError("Image payload is not valid base64") from exc
    if not image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        raise PublicationError("Image payload is not a PNG")
    return image_bytes


def _required_string(payload: object, *path: str) -> str:
    current: object = payload
    for segment in path:
        if not isinstance(current, dict):
            raise PublicationError(f"Missing platform receipt field: {'.'.join(path)}")
        current = current.get(segment)
    if not isinstance(current, str) or not current:
        raise PublicationError(f"Missing platform receipt field: {'.'.join(path)}")
    return current
