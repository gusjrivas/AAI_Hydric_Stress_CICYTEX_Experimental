from human_feedback.decision_policy import (
    DecisionPolicyUnavailable,
    FeedbackTriageInput,
    PolicySuggestion,
)


class DisabledDecisionPolicyEngine:
    """Explicit adapter used when optional decision support is not configured."""

    def classify_feedback(self, request: FeedbackTriageInput) -> PolicySuggestion:
        raise DecisionPolicyUnavailable("decision support is disabled")
