from app.dependencies import get_feedback_triage
from app.main import app
from fastapi.testclient import TestClient

from human_feedback.decision_policy import (
    FeedbackTriageInput,
    FeedbackTriageResult,
)


class StubFeedbackTriage:
    def __init__(self) -> None:
        self.requests: list[FeedbackTriageInput] = []

    def execute(self, request: FeedbackTriageInput) -> FeedbackTriageResult:
        self.requests.append(request)
        return FeedbackTriageResult(
            category="data_quality",
            confidence=0.91,
            provider="laya-http",
            model_revision="checkpoint-sha",
            abstained=False,
            reason=None,
        )


def test_feedback_triage_endpoint_is_advisory_and_dependency_injectable():
    triage = StubFeedbackTriage()
    app.dependency_overrides[get_feedback_triage] = lambda: triage
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v2/feedback/triage",
                json={
                    "site_id": "cicytex",
                    "comment": "La sonda muestra un salto imposible respecto del perfil.",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "category": "data_quality",
        "confidence": 0.91,
        "provider": "laya-http",
        "model_revision": "checkpoint-sha",
        "abstained": False,
        "reason": None,
        "human_review_required": True,
    }
    assert triage.requests == [
        FeedbackTriageInput(
            site_id="cicytex",
            comment="La sonda muestra un salto imposible respecto del perfil.",
        )
    ]


def test_feedback_triage_defaults_to_a_non_blocking_fallback_when_laya_is_disabled(
    monkeypatch,
):
    monkeypatch.delenv("LAYA_DECISION_URL", raising=False)
    monkeypatch.delenv("LAYA_MODEL_REVISION", raising=False)

    with TestClient(app) as client:
        response = client.post(
            "/api/v2/feedback/triage",
            json={"site_id": "pergamino", "comment": "Revisar observación de campo."},
        )

    assert response.status_code == 200
    assert response.json() == {
        "category": "unclassified",
        "confidence": 0.0,
        "provider": "deterministic-fallback",
        "model_revision": None,
        "abstained": True,
        "reason": "engine_unavailable",
        "human_review_required": True,
    }
