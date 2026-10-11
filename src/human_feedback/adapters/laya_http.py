from __future__ import annotations

import json
from typing import Protocol, cast
from urllib.request import Request, urlopen

from human_feedback.decision_policy import (
    DecisionPolicyUnavailable,
    FeedbackCategory,
    FeedbackTriageInput,
    PolicySuggestion,
)

ALLOWED_CATEGORIES: tuple[FeedbackCategory, ...] = (
    "data_quality",
    "model_behavior",
    "agronomic_context",
    "usability",
    "other",
)

FEEDBACK_CATEGORY_QUESTION = {
    "type": "choice",
    "instructions": "Classify this agricultural-system feedback.",
    "criteria": {
        "data_quality": "sensor gaps, spikes, drift or suspect measurements",
        "model_behavior": "forecast, probability or model behavior",
        "agronomic_context": "field work, irrigation, crop or weather context",
        "usability": "interface, explanation or workflow usability",
        "other": "feedback outside the previous categories",
    },
}


class JsonTransport(Protocol):
    def post_json(
        self,
        url: str,
        payload: dict,
        *,
        timeout_seconds: float,
        headers: dict[str, str],
    ) -> dict: ...


class UrllibJsonTransport:
    def post_json(
        self,
        url: str,
        payload: dict,
        *,
        timeout_seconds: float,
        headers: dict[str, str],
    ) -> dict:
        request = Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", **headers},
            method="POST",
        )
        with urlopen(request, timeout=timeout_seconds) as response:
            decoded = json.loads(response.read().decode("utf-8"))
        if not isinstance(decoded, dict):
            raise ValueError("Laya response must be a JSON object")
        return decoded


class LayaDecisionPolicyEngine:
    """Translate feedback triage into Laya's typed-decision HTTP contract."""

    def __init__(
        self,
        base_url: str,
        *,
        model_revision: str,
        timeout_seconds: float = 0.8,
        api_key: str | None = None,
        transport: JsonTransport | None = None,
    ) -> None:
        if not base_url.strip():
            raise ValueError("base_url must not be empty")
        if not model_revision.strip():
            raise ValueError("model_revision must not be empty")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self._endpoint = f"{base_url.rstrip('/')}/v1/systemone"
        self._model_revision = model_revision
        self._timeout_seconds = timeout_seconds
        self._api_key = api_key
        self._transport = transport or UrllibJsonTransport()

    def classify_feedback(self, request: FeedbackTriageInput) -> PolicySuggestion:
        headers = {"Authorization": f"Bearer {self._api_key}"} if self._api_key is not None else {}
        payload = {
            "state": {"site_id": request.site_id, "comment": request.comment},
            "model": "multilingual",
            "questions": {"feedback_category": FEEDBACK_CATEGORY_QUESTION},
        }
        try:
            response = self._transport.post_json(
                self._endpoint,
                payload,
                timeout_seconds=self._timeout_seconds,
                headers=headers,
            )
            return self._parse_suggestion(response)
        except DecisionPolicyUnavailable:
            raise
        except (OSError, TimeoutError, TypeError, ValueError, KeyError) as error:
            raise DecisionPolicyUnavailable("Laya decision service unavailable") from error

    def _parse_suggestion(self, response: dict) -> PolicySuggestion:
        answers = response.get("answers")
        if not isinstance(answers, dict):
            raise DecisionPolicyUnavailable("Laya response has no answers")
        answer = answers.get("feedback_category")
        if not isinstance(answer, dict) or answer.get("type") != "choice":
            raise DecisionPolicyUnavailable("Laya response has no category choice")

        choice = answer.get("choice")
        if choice not in ALLOWED_CATEGORIES:
            raise DecisionPolicyUnavailable("Laya returned an unknown category")

        confidence = answer.get("answer_confidence")
        if confidence is None:
            probabilities = answer.get("probabilities")
            if not isinstance(probabilities, dict):
                raise DecisionPolicyUnavailable("Laya response has no answer confidence")
            confidence = probabilities.get(choice)
        if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
            raise DecisionPolicyUnavailable("Laya answer confidence is invalid")

        return PolicySuggestion(
            category=cast(FeedbackCategory, choice),
            confidence=float(confidence),
            provider="laya-http",
            model_revision=self._model_revision,
        )
