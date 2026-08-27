"""Deterministic, offline validation for generated social-media copy."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator

from social_media_agent.artifacts import ArtifactRepository
from social_media_agent.errors import TextValidationExhaustedError
from social_media_agent.models import (
    AgentReview,
    DraftPackage,
    ExtractedSource,
    TextValidationMetrics,
    ValidationCode,
    ValidationIssue,
    ValidationReport,
)

TEXT_VALIDATION_POLICY_VERSION = "text-validation-v1"
X_MAX_CHARACTERS = 260
LINKEDIN_TARGET_MIN_CHARACTERS = 600
LINKEDIN_TARGET_MAX_CHARACTERS = 1_300
LINKEDIN_PLATFORM_MAX_CHARACTERS = 3_000
MAX_TEXT_REWRITES = 2

_URL_PATTERN = re.compile(
    r"(?ix)(?:"
    r"\bhttps?://[^\s<>()]+|"
    r"\bwww\.[^\s<>()]+|"
    r"(?<!@)\b(?:[a-z0-9](?:[a-z0-9-]{0,62})\.)+"
    r"(?:ai|app|be|cloud|co|com|dev|edu|gg|gov|info|io|ly|me|net|online|org|"
    r"site|social|tech|tv|xyz)(?:[/?:#][^\s<>()]*)?"
    r")"
)
_AGENT_MARKUP_PATTERNS = (
    re.compile(r"```", re.IGNORECASE),
    re.compile(
        r"</?\s*(?:analysis|assistant|system|user|tool|thinking|final|answer)\b[^>]*>",
        re.IGNORECASE,
    ),
    re.compile(r"<\|\s*(?:im_start|im_end|assistant|system|user)\s*\|>", re.IGNORECASE),
    re.compile(r"\bas an ai(?: language model)?\b", re.IGNORECASE),
)
_WORD_PATTERN = re.compile(r"[^\W\d_]+", re.UNICODE)
_LANGUAGE_NAMES = {
    "arabic": "ar",
    "english": "en",
    "french": "fr",
    "spanish": "es",
    "german": "de",
    "portuguese": "pt",
    "russian": "ru",
    "chinese": "zh",
    "japanese": "ja",
    "korean": "ko",
}
_LANGUAGE_MARKERS = {
    "en": frozenset(
        {
            "a",
            "an",
            "and",
            "are",
            "each",
            "for",
            "from",
            "is",
            "make",
            "of",
            "the",
            "this",
            "to",
            "with",
            "work",
        }
    ),
    "fr": frozenset(
        {
            "à",
            "avec",
            "chaque",
            "dans",
            "de",
            "des",
            "et",
            "facile",
            "la",
            "le",
            "les",
            "pour",
            "rendent",
            "restent",
            "une",
        }
    ),
    "es": frozenset(
        {
            "cada",
            "con",
            "de",
            "el",
            "en",
            "es",
            "la",
            "las",
            "los",
            "para",
            "por",
            "que",
            "un",
            "una",
            "y",
        }
    ),
}


class TextValidationPolicy(BaseModel):
    """Runtime inputs for deterministic validation policy version 1."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    forbidden_phrases: tuple[str, ...] = ()
    output_language: str | None = None
    duplicate_similarity_threshold: float = Field(default=0.9, ge=0.0, le=1.0)

    @field_validator("forbidden_phrases")
    @classmethod
    def _forbidden_phrases_are_nonempty(
        cls, values: tuple[str, ...]
    ) -> tuple[str, ...]:
        if any(not value.strip() for value in values):
            raise ValueError("Forbidden phrases cannot be empty")
        return values

    @field_validator("output_language")
    @classmethod
    def _normalize_output_language(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = _normalize_language(value)
        if normalized is None:
            raise ValueError("Output language cannot be empty")
        return normalized


class DraftRewriter(Protocol):
    """Narrow interface for a fresh Agy validation rewrite."""

    async def rewrite(
        self,
        *,
        post_id: str,
        source_path: Path,
        brand_path: Path,
        draft_path: Path,
        feedback_path: Path,
        rewrite_number: int,
    ) -> DraftPackage:
        """Return a new draft informed by persisted validation evidence."""
        ...


class SemanticReviewer(Protocol):
    """Narrow interface for an independent semantic review."""

    async def review(
        self,
        *,
        post_id: str,
        source_path: Path,
        brand_path: Path,
        draft_path: Path,
    ) -> AgentReview:
        """Review a persisted deterministic-valid draft."""
        ...


@dataclass(frozen=True)
class TextValidationOutcome:
    """Successful final draft and its terminal validation evidence."""

    passed: bool
    draft: DraftPackage
    deterministic_report: ValidationReport
    semantic_review: AgentReview
    rewrite_count: int


async def validate_with_rewrites(
    *,
    post_id: str,
    draft: DraftPackage,
    source: ExtractedSource,
    source_path: Path,
    brand_path: Path,
    artifacts: ArtifactRepository,
    rewriter: DraftRewriter,
    reviewer: SemanticReviewer,
    policy: TextValidationPolicy | None = None,
) -> TextValidationOutcome:
    """Validate and rewrite a draft using one shared two-rewrite budget."""
    current = draft
    rewrite_count = 0
    attempt_artifacts: list[str] = []

    while True:
        attempt_number = rewrite_count + 1
        draft_name = f"text-draft-attempt-{attempt_number}.json"
        draft_reference = artifacts.write_json(
            post_id,
            draft_name,
            current.model_dump(mode="json"),
        )
        draft_path = artifacts.workspace / draft_reference
        deterministic = validate_draft(current, source=source, policy=policy)
        report_name = f"text-validation-attempt-{attempt_number}.json"
        artifacts.write_json(
            post_id,
            report_name,
            deterministic.model_dump(mode="json"),
        )
        attempt_artifacts.append(report_name)

        semantic: AgentReview | None = None
        failed_stage = "deterministic"
        if deterministic.passed:
            semantic = await reviewer.review(
                post_id=post_id,
                source_path=source_path,
                brand_path=brand_path,
                draft_path=draft_path,
            )
            artifacts.write_json(
                post_id,
                f"semantic-review-attempt-{attempt_number}.json",
                semantic.model_dump(mode="json"),
            )
            failed_stage = "semantic"
            if semantic.passed:
                outcome = TextValidationOutcome(
                    passed=True,
                    draft=current,
                    deterministic_report=deterministic,
                    semantic_review=semantic,
                    rewrite_count=rewrite_count,
                )
                artifacts.write_json(
                    post_id,
                    "text-validation-success.json",
                    {
                        "schema_version": 1,
                        "passed": True,
                        "rewrite_count": rewrite_count,
                        "deterministic_report": report_name,
                        "semantic_review": (
                            f"semantic-review-attempt-{attempt_number}.json"
                        ),
                        "final_draft": draft_name,
                    },
                )
                return outcome

        if rewrite_count >= MAX_TEXT_REWRITES:
            artifacts.write_json(
                post_id,
                "text-validation-failure.json",
                {
                    "schema_version": 1,
                    "passed": False,
                    "rewrite_count": rewrite_count,
                    "failed_stage": failed_stage,
                    "attempts": attempt_artifacts,
                },
            )
            raise TextValidationExhaustedError(
                "Draft validation failed after two rewrites"
            )

        rewrite_count += 1
        feedback_reference = artifacts.write_json(
            post_id,
            f"rewrite-feedback-{rewrite_count}.json",
            {
                "schema_version": 1,
                "rewrite_number": rewrite_count,
                "deterministic_report": deterministic.model_dump(mode="json"),
                "semantic_review": (
                    semantic.model_dump(mode="json") if semantic is not None else None
                ),
            },
        )
        current = await rewriter.rewrite(
            post_id=post_id,
            source_path=source_path,
            brand_path=brand_path,
            draft_path=draft_path,
            feedback_path=artifacts.workspace / feedback_reference,
            rewrite_number=rewrite_count,
        )


def validate_draft(
    draft: DraftPackage,
    *,
    source: ExtractedSource,
    policy: TextValidationPolicy | None = None,
) -> ValidationReport:
    """Apply P4.1 rules and return complete deterministic evidence."""
    active_policy = policy or TextValidationPolicy()
    errors: list[ValidationIssue] = []
    warnings: list[ValidationIssue] = []
    fields = {
        "concept": draft.concept,
        "linkedin": draft.linkedin,
        "x": draft.x,
        "image_brief": draft.image_brief,
    }

    for field, value in fields.items():
        if not value.strip():
            errors.append(
                _issue(
                    ValidationCode.REQUIRED_FIELD,
                    field,
                    "Required draft field is blank.",
                )
            )

    for field, value in fields.items():
        if field in {"linkedin", "x"} and _contains_url(value):
            errors.append(
                _issue(
                    ValidationCode.URL,
                    field,
                    "Platform rendering contains a URL or domain reference.",
                )
            )
        if any(pattern.search(value) for pattern in _AGENT_MARKUP_PATTERNS):
            errors.append(
                _issue(
                    ValidationCode.AGENT_MARKUP,
                    field,
                    "Platform rendering contains agent or response markup.",
                )
            )
        normalized_value = _normalized_text(value)
        if any(
            _normalized_text(phrase) in normalized_value
            for phrase in active_policy.forbidden_phrases
        ):
            errors.append(
                _issue(
                    ValidationCode.FORBIDDEN_PHRASE,
                    field,
                    "Platform rendering contains a configured forbidden phrase.",
                )
            )

    linkedin_normalized = _normalized_text(draft.linkedin)
    x_normalized = _normalized_text(draft.x)
    similarity = SequenceMatcher(
        None,
        linkedin_normalized,
        x_normalized,
        autojunk=False,
    ).ratio()
    if linkedin_normalized and linkedin_normalized == x_normalized:
        errors.append(
            _issue(
                ValidationCode.IDENTICAL_RENDERINGS,
                None,
                "LinkedIn and X renderings must be distinct.",
            )
        )
    elif similarity >= active_policy.duplicate_similarity_threshold:
        errors.append(
            _issue(
                ValidationCode.DUPLICATE_RENDERINGS,
                None,
                "LinkedIn and X renderings are insufficiently adapted.",
            )
        )

    source_language = _source_language(source)
    expected_language = active_policy.output_language or source_language
    rendering_languages = {
        "linkedin": _detect_language(draft.linkedin),
        "x": _detect_language(draft.x),
    }
    if expected_language is not None:
        for field, detected in rendering_languages.items():
            if detected is not None and detected != expected_language:
                errors.append(
                    _issue(
                        ValidationCode.LANGUAGE_MISMATCH,
                        field,
                        "Platform rendering does not match the expected language.",
                    )
                )

    if len(draft.x) > X_MAX_CHARACTERS:
        errors.append(
            _issue(
                ValidationCode.X_LENGTH,
                "x",
                "X rendering exceeds the configured character limit.",
            )
        )

    linkedin_characters = len(draft.linkedin)
    if linkedin_characters > LINKEDIN_PLATFORM_MAX_CHARACTERS:
        errors.append(
            _issue(
                ValidationCode.LINKEDIN_MAX_LENGTH,
                "linkedin",
                "LinkedIn rendering exceeds the platform character limit.",
            )
        )
    elif not (
        LINKEDIN_TARGET_MIN_CHARACTERS
        <= linkedin_characters
        <= LINKEDIN_TARGET_MAX_CHARACTERS
    ):
        warnings.append(
            _issue(
                ValidationCode.LINKEDIN_TARGET_LENGTH,
                "linkedin",
                "LinkedIn rendering is outside the configured target range.",
            )
        )
    if "\n\n" not in draft.linkedin:
        warnings.append(
            _issue(
                ValidationCode.LINKEDIN_PARAGRAPH_SPACING,
                "linkedin",
                "LinkedIn rendering should use blank lines between paragraphs.",
            )
        )

    metrics = TextValidationMetrics(
        concept_characters=len(draft.concept),
        linkedin_characters=len(draft.linkedin),
        x_characters=len(draft.x),
        image_brief_characters=len(draft.image_brief),
        rendering_similarity=similarity,
        source_language=source_language,
        expected_language=expected_language,
        rendering_languages=rendering_languages,
    )
    return ValidationReport(
        policy_version=TEXT_VALIDATION_POLICY_VERSION,
        passed=not errors,
        errors=errors,
        warnings=warnings,
        metrics=metrics,
        suggested_fix=_suggested_fix(errors),
    )


def _issue(code: ValidationCode, field: str | None, message: str) -> ValidationIssue:
    return ValidationIssue(code=code, field=field, message=message)


def _normalized_text(value: str) -> str:
    decomposed = unicodedata.normalize("NFKC", value).casefold()
    return " ".join(_WORD_PATTERN.findall(decomposed))


def _contains_url(value: str) -> bool:
    inspection_value = "".join(
        character
        for character in unicodedata.normalize("NFKC", value)
        if unicodedata.category(character) != "Cf"
    )
    return _URL_PATTERN.search(inspection_value) is not None


def _source_language(source: ExtractedSource) -> str | None:
    for key in ("language_code", "content_language"):
        value = source.metadata.get(key)
        if isinstance(value, str):
            normalized = _normalize_language(value)
            if normalized is not None:
                return normalized
    return _detect_language(f"{source.title}\n{source.content}")


def _normalize_language(value: str) -> str | None:
    normalized = value.strip().casefold().replace("_", "-")
    if not normalized:
        return None
    normalized = _LANGUAGE_NAMES.get(normalized, normalized)
    return normalized.split("-", maxsplit=1)[0]


def _detect_language(value: str) -> str | None:
    letters = [character for character in value if character.isalpha()]
    if not letters:
        return None
    if sum("\u0600" <= character <= "\u06ff" for character in letters) >= 2:
        return "ar"
    if sum("\u0400" <= character <= "\u04ff" for character in letters) >= 2:
        return "ru"
    if sum("\u4e00" <= character <= "\u9fff" for character in letters) >= 2:
        return "zh"
    if sum("\u3040" <= character <= "\u30ff" for character in letters) >= 2:
        return "ja"
    if sum("\uac00" <= character <= "\ud7af" for character in letters) >= 2:
        return "ko"

    words = _WORD_PATTERN.findall(unicodedata.normalize("NFKC", value).casefold())
    scores = {
        language: sum(word in markers for word in words)
        for language, markers in _LANGUAGE_MARKERS.items()
    }
    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    if not ranked or ranked[0][1] < 2:
        return None
    if len(ranked) > 1 and ranked[0][1] == ranked[1][1]:
        return None
    return ranked[0][0]


def _suggested_fix(errors: list[ValidationIssue]) -> str | None:
    if not errors:
        return None
    codes = {issue.code for issue in errors}
    actions: list[str] = []
    if ValidationCode.REQUIRED_FIELD in codes:
        actions.append("complete every required field")
    if ValidationCode.URL in codes:
        actions.append("remove all links and domain references")
    if ValidationCode.AGENT_MARKUP in codes:
        actions.append("remove agent response markup")
    if ValidationCode.FORBIDDEN_PHRASE in codes:
        actions.append("replace configured forbidden wording")
    if codes & {
        ValidationCode.IDENTICAL_RENDERINGS,
        ValidationCode.DUPLICATE_RENDERINGS,
    }:
        actions.append("adapt the two renderings distinctly")
    if ValidationCode.LANGUAGE_MISMATCH in codes:
        actions.append("rewrite in the expected language")
    if ValidationCode.X_LENGTH in codes:
        actions.append("shorten the X rendering to 260 characters or fewer")
    if ValidationCode.LINKEDIN_MAX_LENGTH in codes:
        actions.append("shorten the LinkedIn rendering to 3,000 characters or fewer")
    return "Revise the draft to " + ", ".join(actions) + "."
