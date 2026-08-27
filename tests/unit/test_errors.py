"""Tests for the public application error hierarchy."""

from social_media_agent.errors import (
    ConfigurationError,
    ExternalCommandError,
    PipelineStateError,
    SocialAgentError,
)


def test_expected_errors_share_one_application_base() -> None:
    """CLI boundaries should be able to catch all expected failures uniformly."""
    assert issubclass(ConfigurationError, SocialAgentError)
    assert issubclass(PipelineStateError, SocialAgentError)
    assert issubclass(ExternalCommandError, SocialAgentError)
