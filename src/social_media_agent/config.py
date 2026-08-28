"""Application configuration resolved from a workspace root."""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel, ConfigDict


class Settings(BaseModel):
    """Filesystem and external-command settings for one workspace."""

    model_config = ConfigDict(frozen=True)

    workspace: Path
    input_path: Path
    brand_path: Path
    output_path: Path
    state_path: Path
    candidates_path: Path = Path("content/candidates.md")
    research_sources_path: Path = Path("content/research-sources.md")
    firecrawl_api_key: str | None = None
    github_token: str | None = None
    x_access_token: str | None = None
    linkedin_access_token: str | None = None
    linkedin_author_urn: str | None = None
    linkedin_version: str | None = None
    x_client_id: str | None = None
    x_redirect_uri: str | None = None
    linkedin_client_id: str | None = None
    linkedin_redirect_uri: str | None = None

    @classmethod
    def from_workspace(cls, workspace: Path) -> Settings:
        """Load settings, resolving relative overrides from ``workspace``."""
        root = workspace.expanduser().resolve()
        input_path = _resolve_from(
            root, os.getenv("SOCIAL_AGENT_INPUT", "content/urls.md")
        )
        brand_path = _resolve_from(
            root, os.getenv("SOCIAL_AGENT_BRAND", "content/brand.md")
        )
        output_path = _resolve_from(root, os.getenv("SOCIAL_AGENT_OUTPUT", "output"))

        return cls(
            workspace=root,
            input_path=input_path,
            brand_path=brand_path,
            output_path=output_path,
            state_path=output_path / "state.json",
            candidates_path=_resolve_from(
                root, os.getenv("SOCIAL_AGENT_CANDIDATES", "content/candidates.md")
            ),
            research_sources_path=_resolve_from(
                root,
                os.getenv(
                    "SOCIAL_AGENT_RESEARCH_SOURCES", "content/research-sources.md"
                ),
            ),
            firecrawl_api_key=os.getenv("FIRECRAWL_API_KEY"),
            github_token=os.getenv("GITHUB_TOKEN"),
            x_access_token=os.getenv("X_ACCESS_TOKEN"),
            linkedin_access_token=os.getenv("LINKEDIN_ACCESS_TOKEN"),
            linkedin_author_urn=os.getenv("LINKEDIN_AUTHOR_URN"),
            linkedin_version=os.getenv("LINKEDIN_API_VERSION"),
            x_client_id=os.getenv("X_CLIENT_ID"),
            x_redirect_uri=os.getenv("X_REDIRECT_URI"),
            linkedin_client_id=os.getenv("LINKEDIN_CLIENT_ID"),
            linkedin_redirect_uri=os.getenv("LINKEDIN_REDIRECT_URI"),
        )


def _resolve_from(workspace: Path, value: str) -> Path:
    """Resolve an absolute path or a path relative to the workspace."""
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = workspace / path
    return path.resolve()
