"""Private Arcade MCP tools for image-complete social publication."""

import argparse
import os
import sys
from dataclasses import dataclass
from typing import Annotated, Literal, cast

import httpx
from arcade_mcp_server import Context, MCPApp
from arcade_mcp_server.auth import LinkedIn, X
from arcade_mcp_server.metadata import (
    Behavior,
    Classification,
    Operation,
    ServiceDomain,
    ToolMetadata,
)

from arcade_social_publisher.publishers import (
    LinkedInImagePublisher,
    XImagePublisher,
    decode_png,
)

app = MCPApp(
    name="arcade_social_publisher",
    version="0.1.0",
    instructions=("Publish only supplied, already-approved PNG images and platform-specific text."),
)

_PUBLISH_METADATA = ToolMetadata(
    classification=Classification(service_domains=[ServiceDomain.SOCIAL_MEDIA]),
    behavior=Behavior(
        operations=[Operation.CREATE],
        read_only=False,
        destructive=False,
        idempotent=False,
        open_world=True,
    ),
)


@dataclass(frozen=True)
class ServerRunConfig:
    """The launch settings supplied by Arcade's local and cloud runners."""

    transport: Literal["http", "stdio"]
    port: int


def _server_run_config(arguments: list[str]) -> ServerRunConfig:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--transport", choices=("http", "stdio"), default="stdio")
    parser.add_argument("--port", type=int, default=8000)
    parsed, remaining = parser.parse_known_args(arguments)
    transport = (
        remaining[0] if remaining and remaining[0] in {"http", "stdio"} else parsed.transport
    )
    return ServerRunConfig(
        transport=cast(Literal["http", "stdio"], transport),
        port=parsed.port,
    )


@app.tool(  # type: ignore[arg-type]
    requires_auth=X(scopes=["tweet.read", "tweet.write", "users.read"]),
    metadata=_PUBLISH_METADATA,
)
async def publish_x_image(
    context: Context,
    text: Annotated[str, "Approved X post text."],
    image_base64: Annotated[str, "Base64-encoded approved PNG image."],
    media_type: Annotated[str, "Must be image/png."],
) -> Annotated[dict[str, str], "Published X post ID and URL."]:
    """Publish the approved X text with the exact approved PNG image."""
    image_bytes = decode_png(image_base64, media_type=media_type)
    async with httpx.AsyncClient(timeout=30.0) as client:
        receipt = await XImagePublisher(client).publish(
            access_token=context.get_auth_token_or_empty(),
            text=text,
            image_bytes=image_bytes,
        )
    return {"post_id": receipt.post_id, "post_url": receipt.post_url or ""}


@app.tool(  # type: ignore[arg-type]
    requires_auth=LinkedIn(scopes=["w_member_social"]),
    metadata=_PUBLISH_METADATA,
)
async def publish_linkedin_image(
    context: Context,
    text: Annotated[str, "Approved LinkedIn post text."],
    image_base64: Annotated[str, "Base64-encoded approved PNG image."],
    media_type: Annotated[str, "Must be image/png."],
    author_urn: Annotated[str, "Personal LinkedIn member URN, urn:li:person:<id>."],
) -> Annotated[dict[str, str], "Published LinkedIn post ID and URL."]:
    """Publish approved LinkedIn text with the exact approved PNG image."""
    image_bytes = decode_png(image_base64, media_type=media_type)
    api_version = os.environ.get("LINKEDIN_VERSION", "202608")
    async with httpx.AsyncClient(timeout=30.0) as client:
        receipt = await LinkedInImagePublisher(client, api_version=api_version).publish(
            access_token=context.get_auth_token_or_empty(),
            author_urn=author_urn,
            text=text,
            image_bytes=image_bytes,
        )
    return {"post_id": receipt.post_id, "post_url": receipt.post_url or ""}


if __name__ == "__main__":
    config = _server_run_config(sys.argv[1:])
    app.run(transport=config.transport, host="127.0.0.1", port=config.port)
