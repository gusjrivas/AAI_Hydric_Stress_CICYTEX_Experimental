from human_feedback.decision_policy import (
    DecisionPolicyUnavailable,
    FeedbackTriageInput,
    PolicySuggestion,
    TriageFeedback,
)


class StubDecisionPolicyEngine:
    def __init__(
        self,
        suggestion: PolicySuggestion | None = None,
        error: Exception | None = None,
    ) -> None:
        self.suggestion = suggestion
        self.error = error
        self.requests: list[FeedbackTriageInput] = []

    def classify_feedback(self, request: FeedbackTriageInput) -> PolicySuggestion:
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        assert self.suggestion is not None
        return self.suggestion


def test_feedback_triage_is_advisory_and_keeps_human_review_mandatory():
    engine = StubDecisionPolicyEngine(
        PolicySuggestion(
            category="data_quality",
            confidence=0.93,
            provider="laya",
            model_revision="checkpoint-sha",
        )
    )

    result = TriageFeedback(engine, minimum_confidence=0.85).execute(
        FeedbackTriageInput(
            site_id="cicytex",
            comment="La sonda CP1 presenta saltos incompatibles con el resto del perfil.",
        )
    )

    assert engine.requests == [
        FeedbackTriageInput(
            site_id="cicytex",
            comment="La sonda CP1 presenta saltos incompatibles con el resto del perfil.",
        )
    ]
    assert result.category == "data_quality"
    assert result.confidence == 0.93
    assert result.provider == "laya"
    assert result.model_revision == "checkpoint-sha"
    assert result.abstained is False
    assert result.human_review_required is True


def test_feedback_triage_abstains_when_model_confidence_is_below_policy_threshold():
    engine = StubDecisionPolicyEngine(
        PolicySuggestion(
            category="agronomic_context",
            confidence=0.61,
            provider="laya",
            model_revision="checkpoint-sha",
        )
    )

    result = TriageFeedback(engine, minimum_confidence=0.85).execute(
        FeedbackTriageInput(site_id="pergamino", comment="Hubo una labor entre mediciones.")
    )

    assert result.category == "unclassified"
    assert result.confidence == 0.61
    assert result.abstained is True
    assert result.reason == "below_confidence_threshold"
    assert result.human_review_required is True


def test_feedback_triage_falls_back_without_blocking_when_the_engine_is_unavailable():
    engine = StubDecisionPolicyEngine(error=DecisionPolicyUnavailable("timeout"))

    result = TriageFeedback(engine).execute(
        FeedbackTriageInput(site_id="melchor-romero", comment="Revisar este comentario.")
    )

    assert result.category == "unclassified"
    assert result.confidence == 0.0
    assert result.provider == "deterministic-fallback"
    assert result.model_revision is None
    assert result.abstained is True
    assert result.reason == "engine_unavailable"
    assert result.human_review_required is True
