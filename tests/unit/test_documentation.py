"""Cutover documentation and CI contract tests."""

from pathlib import Path

ROOT = Path(__file__).parents[2]


def test_readme_documents_the_complete_local_cli_boundary() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    for required in (
        "uv sync",
        "agy --print",
        "codex login status",
        "social-agent run",
        "social-agent resume",
        "social-agent status",
        "social-agent retry-failed",
        "social-agent review",
        "content/urls.md",
        "content/brand.md",
        "output/posts/<post-id>/approved-manifest.json",
        "Firecrawl is optional",
        "direct OAuth 2.0 developer APIs",
    ):
        assert required in readme
    for obsolete in ("yarn install", "LangGraph server", "Agent Inbox", "Supabase"):
        assert obsolete not in readme


def test_environment_example_contains_only_supported_local_inputs() -> None:
    example = (ROOT / ".env.example").read_text(encoding="utf-8")

    for supported in (
        "FIRECRAWL_API_KEY=",
        "GITHUB_TOKEN=",
        "SOCIAL_AGENT_INPUT=content/urls.md",
        "SOCIAL_AGENT_BRAND=content/brand.md",
        "SOCIAL_AGENT_OUTPUT=output",
    ):
        assert supported in example
    for obsolete in (
        "LANGSMITH",
        "SUPABASE",
        "SLACK",
        "ARCADE",
    ):
        assert obsolete not in example


def test_default_ci_is_uv_only_and_never_runs_live_agents() -> None:
    workflows = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((ROOT / ".github/workflows").glob("*.yml"))
    )

    for required in (
        "astral-sh/setup-uv@v9",
        "uv sync --locked",
        "uv run ruff format --check src tests",
        "uv run ruff check src tests",
        "uv run mypy",
        'uv run pytest -m "not live"',
    ):
        assert required in workflows
    for obsolete in ("setup-node", "yarn ", "npm ", "SOCIAL_AGENT_LIVE"):
        assert obsolete not in workflows


def test_legacy_setup_documents_and_config_are_removed() -> None:
    """Retained setup surfaces should describe only the local Python product."""
    obsolete_paths = (
        "FEATURES.md",
        ".env.full.example",
        ".env.quickstart.example",
        ".vscode/settings.json",
        ".codespellignore",
    )

    assert all(not (ROOT / path).exists() for path in obsolete_paths)

    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    for required in (".venv/", ".pytest_cache/", "output/*"):
        assert required in gitignore
    for obsolete in (
        ".yarn",
        ".turbo",
        ".eslintcache",
        "src/agents",
        "src/clients",
        ".langgraph_api",
    ):
        assert obsolete not in gitignore
