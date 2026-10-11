from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from human_feedback.ports import DecisionPolicyEngine

FeedbackCategory = Literal[
    "data_quality",
    "model_behavior",
    "agronomic_context",
    "usability",
    "other",
    "unclassified",
]


class DecisionPolicyUnavailable(RuntimeError):
    """The optional decision engine could not produce a suggestion."""


@dataclass(frozen=True)
class FeedbackTriageInput:
    site_id: str
    comment: str

    def __post_init__(self) -> None:
        if not self.site_id.strip():
            raise ValueError("site_id must not be empty")
        if not self.comment.strip():
            raise ValueError("comment must not be empty")


@dataclass(frozen=True)
class PolicySuggestion:
    category: FeedbackCategory
    confidence: float
    provider: str
    model_revision: str | None

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")


@dataclass(frozen=True)
class FeedbackTriageResult:
    category: FeedbackCategory
    confidence: float
    provider: str
    model_revision: str | None
    abstained: bool
    reason: str | None
    human_review_required: bool = True


class TriageFeedback:
    """Produce a non-authoritative suggestion for the human feedback queue."""

    def __init__(
        self,
        engine: DecisionPolicyEngine,
        *,
        minimum_confidence: float = 0.85,
    ) -> None:
        if not 0.0 <= minimum_confidence <= 1.0:
            raise ValueError("minimum_confidence must be between 0 and 1")
        self._engine = engine
        self._minimum_confidence = minimum_confidence

    def execute(self, request: FeedbackTriageInput) -> FeedbackTriageResult:
        try:
            suggestion = self._engine.classify_feedback(request)
        except DecisionPolicyUnavailable:
            return self._fallback()

        if suggestion.confidence < self._minimum_confidence:
            return FeedbackTriageResult(
                category="unclassified",
                confidence=suggestion.confidence,
                provider=suggestion.provider,
                model_revision=suggestion.model_revision,
                abstained=True,
                reason="below_confidence_threshold",
            )

        return FeedbackTriageResult(
            category=suggestion.category,
            confidence=suggestion.confidence,
            provider=suggestion.provider,
            model_revision=suggestion.model_revision,
            abstained=False,
            reason=None,
        )

    @staticmethod
    def _fallback() -> FeedbackTriageResult:
        return FeedbackTriageResult(
            category="unclassified",
            confidence=0.0,
            provider="deterministic-fallback",
            model_revision=None,
            abstained=True,
            reason="engine_unavailable",
        )
