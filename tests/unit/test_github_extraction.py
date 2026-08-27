"""Tests for the bounded GitHub REST fallback."""

import httpx
import pytest
import respx

from social_media_agent.errors import ExtractionError
from social_media_agent.extraction import ExtractionRequest, GitHubRepositoryExtractor
from social_media_agent.models import ExtractionMethod, SourceType

API_ROOT = "https://api.github.com/repos/octo/example"
REPOSITORY = {
    "full_name": "octo/example",
    "html_url": "https://github.com/octo/example",
    "description": "A useful fixture repository",
    "default_branch": "main",
    "language": "Python",
    "stargazers_count": 42,
    "topics": ["agents", "python"],
    "created_at": "2025-01-02T03:04:05Z",
    "updated_at": "2026-08-24T12:00:00Z",
    "owner": {"login": "octo"},
}


def _request(url: str = "https://github.com/octo/example") -> ExtractionRequest:
    return ExtractionRequest(normalized_url=url, source_type=SourceType.GITHUB)


def _mock_repository() -> None:
    respx.get(API_ROOT).mock(return_value=httpx.Response(200, json=REPOSITORY))


@respx.mock
@pytest.mark.asyncio
async def test_github_fallback_collects_metadata_readme_and_small_manifests() -> None:
    """The fallback should fetch useful repository evidence without cloning."""
    _mock_repository()
    readme = respx.get(f"{API_ROOT}/readme").mock(
        return_value=httpx.Response(200, text="# Example\n\nRepository overview.")
    )
    respx.get(f"{API_ROOT}/contents").mock(
        return_value=httpx.Response(
            200,
            json=[
                {"type": "file", "name": "pyproject.toml", "size": 120},
                {"type": "file", "name": "package.json", "size": 90_000},
                {"type": "file", "name": "notes.txt", "size": 20},
                {"type": "dir", "name": "src", "size": 0},
            ],
        )
    )
    manifest = respx.get(f"{API_ROOT}/contents/pyproject.toml").mock(
        return_value=httpx.Response(
            200,
            text='[project]\nname = "example"',
        )
    )
    extractor = GitHubRepositoryExtractor(
        max_manifest_bytes=1_000,
        max_manifests=2,
    )

    source = await extractor.extract(_request("https://github.com/octo/example/issues"))

    assert source.canonical_url == "https://github.com/octo/example"
    assert source.title == "octo/example"
    assert source.author == "octo"
    assert source.published_at is not None
    assert source.extraction_method is ExtractionMethod.GITHUB_API
    assert "A useful fixture repository" in source.content
    assert "# Example" in source.content
    assert "## pyproject.toml" in source.content
    assert 'name = "example"' in source.content
    assert "package.json" not in source.content
    assert source.metadata == {
        "github": {
            "default_branch": "main",
            "language": "Python",
            "manifests": ["pyproject.toml"],
            "readme": True,
            "stargazers_count": 42,
            "topics": ["agents", "python"],
        }
    }
    assert respx.calls[0].request.headers["x-github-api-version"] == "2026-03-10"
    assert respx.calls[0].request.headers["user-agent"] == "social-media-agent"
    assert "authorization" not in respx.calls[0].request.headers
    assert readme.calls[0].request.headers["accept"] == (
        "application/vnd.github.raw+json"
    )
    assert manifest.called
    assert not respx.calls.last.request.url.path.endswith("package.json")


@respx.mock
@pytest.mark.asyncio
async def test_github_fallback_uses_optional_bearer_token_on_every_request() -> None:
    """A configured token should authenticate API reads without entering output."""
    _mock_repository()
    respx.get(f"{API_ROOT}/readme").mock(return_value=httpx.Response(404))
    respx.get(f"{API_ROOT}/contents").mock(return_value=httpx.Response(200, json=[]))
    extractor = GitHubRepositoryExtractor(token=" secret-token ")

    source = await extractor.extract(_request())

    assert len(respx.calls) == 3
    assert all(
        call.request.headers["authorization"] == "Bearer secret-token"
        for call in respx.calls
    )
    assert "secret-token" not in source.model_dump_json()


@respx.mock
@pytest.mark.asyncio
async def test_github_fallback_allows_missing_readme_and_empty_repository() -> None:
    """Repository metadata remains usable when optional content is absent."""
    _mock_repository()
    respx.get(f"{API_ROOT}/readme").mock(return_value=httpx.Response(404))
    respx.get(f"{API_ROOT}/contents").mock(return_value=httpx.Response(404))

    source = await GitHubRepositoryExtractor().extract(_request())

    assert "A useful fixture repository" in source.content
    assert source.metadata["github"]["readme"] is False
    assert source.metadata["github"]["manifests"] == []


@respx.mock
@pytest.mark.asyncio
async def test_github_fallback_rejects_repository_http_failure_safely() -> None:
    """Required metadata failures should not expose the API response body."""
    respx.get(API_ROOT).mock(
        return_value=httpx.Response(403, text="private rate limit details")
    )

    with pytest.raises(ExtractionError, match="HTTP status 403") as raised:
        await GitHubRepositoryExtractor().extract(_request())

    assert "private rate limit" not in str(raised.value)


@respx.mock
@pytest.mark.asyncio
async def test_github_fallback_rejects_malformed_repository_metadata() -> None:
    """A successful but incomplete API response is not trustworthy evidence."""
    respx.get(API_ROOT).mock(
        return_value=httpx.Response(200, json={"full_name": ["not", "text"]})
    )

    with pytest.raises(ExtractionError, match="malformed repository metadata"):
        await GitHubRepositoryExtractor().extract(_request())


@pytest.mark.asyncio
async def test_github_fallback_rejects_non_repository_url_before_network() -> None:
    """A GitHub profile URL does not identify a repository."""
    extractor = GitHubRepositoryExtractor()

    with pytest.raises(ExtractionError, match="owner and repository"):
        await extractor.extract(_request("https://github.com/octo"))


def test_github_fallback_rejects_invalid_resource_bounds() -> None:
    """Manifest and HTTP limits must be positive and finite."""
    with pytest.raises(ValueError, match="timeout"):
        GitHubRepositoryExtractor(timeout_seconds=0)
    with pytest.raises(ValueError, match="manifest count"):
        GitHubRepositoryExtractor(max_manifests=0)
    with pytest.raises(ValueError, match="manifest size"):
        GitHubRepositoryExtractor(max_manifest_bytes=0)
