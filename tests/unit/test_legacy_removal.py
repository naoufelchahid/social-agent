"""Regression boundary for the approved Phase 8 legacy removal."""

import subprocess
from pathlib import Path

ROOT = Path(__file__).parents[2]


def test_phase_8_removes_legacy_runtime_surface() -> None:
    """Only the local Python replacement should retain executable source."""
    legacy_paths = (
        "src/agents",
        "src/clients",
        "src/evals",
        "src/tests",
        "src/utils",
        "scripts",
        "memory-v2",
        "slack-messaging",
        "static",
        "package.json",
        "yarn.lock",
        "tsconfig.json",
        "eslint.config.js",
        ".eslintrc.cjs",
        "jest.config.js",
        "jest.setup.cjs",
        "langgraph.json",
        ".dockerignore",
    )

    assert all(not (ROOT / path).exists() for path in legacy_paths)
    assert (ROOT / "src/social_media_agent").is_dir()
    assert (ROOT / "tests/e2e/test_local_pipeline.py").is_file()


def test_dependabot_tracks_only_retained_package_ecosystems() -> None:
    """Dependency automation must not reference removed Node or memory projects."""
    configuration = (ROOT / ".github/dependabot.yml").read_text()

    assert 'package-ecosystem: "uv"' in configuration
    assert 'package-ecosystem: "github-actions"' in configuration
    assert 'package-ecosystem: "npm"' in configuration
    assert 'package-ecosystem: "pip"' not in configuration
    assert "memory-v2" not in configuration


def test_root_contains_only_the_retained_local_python_surface() -> None:
    """The checked-in root surface must match in worktrees and exports."""
    expected = {
        ".env.example",
        ".github",
        ".gitignore",
        ".python-version",
        ".agents",
        "AGENTS.md",
        "CONTEXT.md",
        "LICENSE",
        "README.md",
        "content",
        "docs",
        "output",
        "pyproject.toml",
        "skills-lock.json",
        "src",
        "tests",
        "uv.lock",
        "web",
    }
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=ROOT,
        capture_output=True,
        text=False,
    )
    if result.returncode == 0:
        top_level = {
            Path(path).parts[0] for path in result.stdout.decode().split("\0") if path
        }
        assert top_level == expected
        return

    runtime_entries = {
        ".coverage",
        ".env",
        ".git",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".venv",
    }
    assert {path.name for path in ROOT.iterdir()} <= expected | runtime_entries
