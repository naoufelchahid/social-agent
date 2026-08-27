"""Direct OAuth 2.0 publication of an approved PNG and platform-specific text."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from enum import StrEnum

import httpx


class PublicationPlatform(StrEnum):
    """Personal social platforms supported by the local publisher."""

    X = "x"
    LINKEDIN = "linkedin"


class PublicationState(StrEnum):
    """Durable state of one platform-specific publication attempt."""

    PENDING = "pending"
    PUBLISHED = "published"
    FAILED = "failed"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class PublisherSettings:
    """In-memory OAuth configuration; callers must not persist these values."""

    x_access_token: str
    linkedin_access_token: str
    linkedin_author_urn: str
    linkedin_version: str


@dataclass(frozen=True)
class PublicationRequest:
    """Exact approved renderings and bytes to publish once."""

    post_id: str
    x_text: str
    linkedin_text: str
    image_bytes: bytes


@dataclass(frozen=True)
class PublicationAttempt:
    """Safe, non-secret evidence for one platform attempt."""

    platform: PublicationPlatform
    state: PublicationState
    remote_id: str | None = None
    remote_url: str | None = None
    error: str | None = None


@dataclass(frozen=True)
class PublicationResult:
    """Ordered results; later platforms are absent after an X failure."""

    attempts: tuple[PublicationAttempt, ...]


class UnconfiguredPublisher:
    """Record a known no-write failure until direct OAuth is configured."""

    async def publish(self, request: PublicationRequest) -> PublicationResult:
        del request
        return PublicationResult(
            attempts=(
                PublicationAttempt(
                    platform=PublicationPlatform.X,
                    state=PublicationState.FAILED,
                    error="Direct publication is not configured",
                ),
            )
        )


class DirectOAuthPublisher:
    """Publish X first, then LinkedIn, using direct OAuth 2.0 user tokens."""

    def __init__(
        self,
        settings: PublisherSettings,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._settings = settings
        self._transport = transport

    async def publish(self, request: PublicationRequest) -> PublicationResult:
        """Create image-complete posts without retrying uncertain submissions."""
        if not request.image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
            raise ValueError("Publication requires exact PNG image bytes")
        async with httpx.AsyncClient(transport=self._transport, timeout=30.0) as client:
            x_attempt = await self._publish_x(client, request)
            if x_attempt.state is not PublicationState.PUBLISHED:
                return PublicationResult(attempts=(x_attempt,))
            linkedin_attempt = await self._publish_linkedin(client, request)
        return PublicationResult(attempts=(x_attempt, linkedin_attempt))

    async def _publish_x(
        self, client: httpx.AsyncClient, request: PublicationRequest
    ) -> PublicationAttempt:
        headers = {"Authorization": f"Bearer {self._settings.x_access_token}"}
        try:
            upload = await client.post(
                "https://api.x.com/2/media/upload",
                headers=headers,
                json={
                    "media": base64.b64encode(request.image_bytes).decode("ascii"),
                    "media_category": "tweet_image",
                    "media_type": "image/png",
                },
            )
            upload.raise_for_status()
            media_id = _required_string(upload.json(), "data", "id")
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            return _failed(PublicationPlatform.X, exc)
        try:
            post = await client.post(
                "https://api.x.com/2/tweets",
                headers={**headers, "Content-Type": "application/json"},
                json={"text": request.x_text, "media": {"media_ids": [media_id]}},
            )
            post.raise_for_status()
            post_id = _required_string(post.json(), "data", "id")
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            return _unknown(PublicationPlatform.X, exc)
        return PublicationAttempt(
            platform=PublicationPlatform.X,
            state=PublicationState.PUBLISHED,
            remote_id=post_id,
            remote_url=f"https://x.com/i/web/status/{post_id}",
        )

    async def _publish_linkedin(
        self, client: httpx.AsyncClient, request: PublicationRequest
    ) -> PublicationAttempt:
        headers = {
            "Authorization": f"Bearer {self._settings.linkedin_access_token}",
            "Linkedin-Version": self._settings.linkedin_version,
            "X-Restli-Protocol-Version": "2.0.0",
        }
        try:
            initialize = await client.post(
                "https://api.linkedin.com/rest/images?action=initializeUpload",
                headers={**headers, "Content-Type": "application/json"},
                json={
                    "initializeUploadRequest": {
                        "owner": self._settings.linkedin_author_urn,
                    }
                },
            )
            initialize.raise_for_status()
            image_urn = _required_string(initialize.json(), "value", "image")
            upload_url = _required_string(initialize.json(), "value", "uploadUrl")
            image_upload = await client.put(
                upload_url,
                content=request.image_bytes,
                headers={"Content-Type": "image/png"},
            )
            image_upload.raise_for_status()
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            return _failed(PublicationPlatform.LINKEDIN, exc)
        try:
            post = await client.post(
                "https://api.linkedin.com/rest/posts",
                headers={**headers, "Content-Type": "application/json"},
                json={
                    "author": self._settings.linkedin_author_urn,
                    "commentary": request.linkedin_text,
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
                raise ValueError("LinkedIn post response omitted x-restli-id")
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            return _unknown(PublicationPlatform.LINKEDIN, exc)
        return PublicationAttempt(
            platform=PublicationPlatform.LINKEDIN,
            state=PublicationState.PUBLISHED,
            remote_id=post_id,
        )


def _required_string(value: object, *keys: str) -> str:
    current = value
    for key in keys:
        if not isinstance(current, dict):
            raise ValueError("Publication response did not match the provider contract")
        current = current.get(key)
    if not isinstance(current, str) or not current:
        raise ValueError("Publication response omitted a required identifier")
    return current


def _failed(platform: PublicationPlatform, error: Exception) -> PublicationAttempt:
    return PublicationAttempt(
        platform=platform,
        state=PublicationState.FAILED,
        error=_safe_error(error),
    )


def _unknown(platform: PublicationPlatform, error: Exception) -> PublicationAttempt:
    return PublicationAttempt(
        platform=platform,
        state=PublicationState.UNKNOWN,
        error=_safe_error(error),
    )


def _safe_error(error: Exception) -> str:
    if isinstance(error, httpx.HTTPStatusError):
        return f"Provider returned HTTP {error.response.status_code}"
    if isinstance(error, httpx.RequestError):
        return "Provider request did not complete"
    return str(error)
