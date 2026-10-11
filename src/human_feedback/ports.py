from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from human_feedback.decision_policy import FeedbackTriageInput, PolicySuggestion


class DecisionPolicyEngine(Protocol):
    """Advisory classifier boundary; implementations may never apply decisions."""

    def classify_feedback(self, request: FeedbackTriageInput) -> PolicySuggestion: ...
