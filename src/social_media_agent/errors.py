"""Typed application errors presented by the CLI."""


class SocialAgentError(Exception):
    """Base class for expected application failures."""


class ConfigurationError(SocialAgentError):
    """Raised when required local configuration is invalid."""


class PipelineStateError(SocialAgentError):
    """Raised when persisted workflow state cannot be trusted."""


class ExtractionError(SocialAgentError):
    """Raised when source extraction cannot produce trustworthy evidence."""


class ExternalCommandError(SocialAgentError):
    """Raised when a local agent command fails or times out."""

    def __init__(self, message: str, *, result: object | None = None) -> None:
        self.result = result
        super().__init__(message)


class AgentOutputError(SocialAgentError):
    """Raised when a local agent does not satisfy its JSON contract."""


class TextValidationExhaustedError(SocialAgentError):
    """Raised after a draft remains invalid following two total rewrites."""


class ImageValidationError(SocialAgentError):
    """Raised when a generated image or its persisted evidence is unsafe."""

    def __init__(self, message: str, *, code: str = "invalid_image") -> None:
        self.code = code
        super().__init__(message)


class ImageValidationExhaustedError(SocialAgentError):
    """Raised when no valid image exists after two regenerations."""


class HumanReviewError(SocialAgentError):
    """Raised when a local human-review action cannot be completed safely."""
