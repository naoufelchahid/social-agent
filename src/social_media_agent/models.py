"""Strict domain models shared by pipeline stages."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator


class JobStage(StrEnum):
    """Persisted stages in the local sequential workflow."""

    PENDING = "pending"
    EXTRACTING = "extracting"
    DRAFTING = "drafting"
    VALIDATING = "validating"
    GENERATING_IMAGE = "generating_image"
    VALIDATING_IMAGE = "validating_image"
    HUMAN_REVIEW = "human_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    FAILED = "failed"
    INTERRUPTED = "interrupted"


class SourceType(StrEnum):
    """Supported source families with dedicated extraction behavior."""

    GENERAL = "general"
    GITHUB = "github"
    REDDIT = "reddit"
    YOUTUBE = "youtube"


class ExtractionMethod(StrEnum):
    """Concrete mechanisms retained as extraction provenance."""

    FIRECRAWL = "firecrawl"
    GENERAL_HTTP = "general_http"
    GITHUB_API = "github_api"
    REDDIT_JSON = "reddit_json"
    REDDIT_HTML = "reddit_html"
    YOUTUBE_TRANSCRIPT = "youtube_transcript"


class FirecrawlFallbackReason(StrEnum):
    """Stable, non-sensitive reasons for using a local source fallback."""

    MISSING_CONFIGURATION = "missing_configuration"
    TIMEOUT = "timeout"
    RATE_LIMIT = "rate_limit"
    MALFORMED_RESPONSE = "malformed_response"
    UNUSABLE_RESPONSE = "unusable_response"
    SERVICE_ERROR = "service_error"


class QueueItem(BaseModel):
    """One URL and its optional human-authored generation context."""

    model_config = ConfigDict(frozen=True)

    id: str
    original_url: str
    normalized_url: str
    checked: bool
    source_line: int
    angle: str | None = None
    audience: str | None = None


class ExtractedSource(BaseModel):
    """Versioned, human-readable evidence produced by any extractor."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    canonical_url: str
    source_type: SourceType
    title: str = Field(min_length=1)
    author: str | None = None
    published_at: datetime | None = None
    content: str = Field(min_length=1)
    metadata: dict[str, JsonValue] = Field(default_factory=dict)
    extraction_method: ExtractionMethod
    extracted_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class DraftPackage(BaseModel):
    """One concept with platform-specific copy and a shared image brief."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    concept: str = Field(min_length=1)
    linkedin: str = Field(min_length=1)
    x: str = Field(min_length=1)
    image_brief: str = Field(min_length=1)


class AgentReview(BaseModel):
    """Strict independent semantic review returned by a local reviewer."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    passed: bool
    summary: str = Field(min_length=1)
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    suggested_fix: str | None = None


class ValidationCode(StrEnum):
    """Stable machine-readable reasons for deterministic text rejection."""

    REQUIRED_FIELD = "required_field"
    URL = "url"
    AGENT_MARKUP = "agent_markup"
    FORBIDDEN_PHRASE = "forbidden_phrase"
    IDENTICAL_RENDERINGS = "identical_renderings"
    DUPLICATE_RENDERINGS = "duplicate_renderings"
    LANGUAGE_MISMATCH = "language_mismatch"
    X_LENGTH = "x_length"
    LINKEDIN_TARGET_LENGTH = "linkedin_target_length"
    LINKEDIN_PARAGRAPH_SPACING = "linkedin_paragraph_spacing"
    LINKEDIN_MAX_LENGTH = "linkedin_max_length"


class ValidationIssue(BaseModel):
    """One safe, typed validation finding."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: ValidationCode
    field: str | None = None
    message: str = Field(min_length=1)


class TextValidationMetrics(BaseModel):
    """Deterministic measurements retained with a text validation report."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    concept_characters: int = Field(ge=0)
    linkedin_characters: int = Field(ge=0)
    x_characters: int = Field(ge=0)
    image_brief_characters: int = Field(ge=0)
    rendering_similarity: float = Field(ge=0.0, le=1.0)
    source_language: str | None = None
    expected_language: str | None = None
    rendering_languages: dict[str, str | None]


class ValidationReport(BaseModel):
    """Versioned deterministic text-validation evidence."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    policy_version: str = Field(min_length=1)
    passed: bool
    errors: list[ValidationIssue] = Field(default_factory=list)
    warnings: list[ValidationIssue] = Field(default_factory=list)
    metrics: TextValidationMetrics
    suggested_fix: str | None = None


class ImageGenerationRequest(BaseModel):
    """Versioned production request passed to Codex image generation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    image_brief: str = Field(min_length=1)
    use_case: Literal["stylized-concept"] = "stylized-concept"
    asset_type: Literal["shared social-media post image"] = (
        "shared social-media post image"
    )
    style_medium: Literal["editorial technical illustration"] = (
        "editorial technical illustration"
    )
    width: Literal[1536] = 1536
    height: Literal[1024] = 1024
    constraints: tuple[str, str, str] = (
        "no embedded text",
        "no logos or trademarks",
        "no watermarks",
    )
    regeneration_feedback: str | None = None


class ImageGenerationResult(BaseModel):
    """Strict final response from one Codex image-generation attempt."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    path: str = Field(min_length=1)
    final_prompt: str = Field(min_length=1)
    generator_identity: str = Field(min_length=1)


class ImageFileMetadata(BaseModel):
    """Locally verified properties of a confined generated image."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    path: str = Field(min_length=1)
    mime_type: Literal["image/png"] = "image/png"
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    size_bytes: int = Field(gt=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class ImageSemanticReview(BaseModel):
    """Strict read-only Codex review of one attached generated image."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    passed: bool
    relevance: bool
    no_unwanted_text: bool
    no_logos: bool
    no_watermarks: bool
    consistent_with_post: bool
    summary: str = Field(min_length=1)
    feedback: str | None = None

    @model_validator(mode="after")
    def _passed_matches_criteria(self) -> ImageSemanticReview:
        criteria_pass = all(
            (
                self.relevance,
                self.no_unwanted_text,
                self.no_logos,
                self.no_watermarks,
                self.consistent_with_post,
            )
        )
        if self.passed != criteria_pass:
            raise ValueError("Image review pass state must match all criteria")
        return self


class ImageArtifact(BaseModel):
    """Resumable final image contract retained with an approved draft package."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    path: str = Field(min_length=1)
    mime_type: Literal["image/png"] = "image/png"
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    size_bytes: int = Field(gt=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    prompt: str = Field(min_length=1)
    generator_identity: str = Field(min_length=1)
    generation_attempt: int = Field(ge=1, le=3)
    validation_result: ImageSemanticReview


class ApprovedManifest(BaseModel):
    """Immutable local snapshot created at the human approval boundary."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    post_id: str = Field(min_length=1)
    source: ExtractedSource
    draft: DraftPackage
    deterministic_validation: ValidationReport
    semantic_review: AgentReview
    image: ImageArtifact
    approved_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class JobRecord(BaseModel):
    """Durable state for one URL as it moves through the pipeline."""

    model_config = ConfigDict(frozen=True)

    post_id: str
    normalized_url: str
    stage: JobStage = JobStage.PENDING
    failed_stage: JobStage | None = None
    resume_stage: JobStage | None = None
    attempts: dict[str, int] = Field(default_factory=dict)
    artifacts: dict[str, str] = Field(default_factory=dict)
    last_error: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class PipelineState(BaseModel):
    """Versioned root document for all local pipeline progress."""

    model_config = ConfigDict(frozen=True)

    schema_version: Literal[1] = 1
    jobs: dict[str, JobRecord] = Field(default_factory=dict)
    active_job_id: str | None = None
