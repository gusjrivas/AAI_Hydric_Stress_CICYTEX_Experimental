import pytest
from human_feedback.adapters.laya_http import LayaDecisionPolicyEngine

from human_feedback.decision_policy import (
    DecisionPolicyUnavailable,
    FeedbackTriageInput,
    PolicySuggestion,
)


class StubJsonTransport:
    def __init__(self, response: dict | None = None, error: Exception | None = None) -> None:
        self.response = response
        self.error = error
        self.calls: list[dict] = []

    def post_json(
        self,
        url: str,
        payload: dict,
        *,
        timeout_seconds: float,
        headers: dict[str, str],
    ) -> dict:
        self.calls.append(
            {
                "url": url,
                "payload": payload,
                "timeout_seconds": timeout_seconds,
                "headers": headers,
            }
        )
        if self.error is not None:
            raise self.error
        assert self.response is not None
        return self.response


def test_laya_adapter_maps_the_typed_choice_response_and_records_model_revision():
    transport = StubJsonTransport(
        {
            "model": "laya-multilingual",
            "answers": {
                "feedback_category": {
                    "type": "choice",
                    "choice": "data_quality",
                    "answer_confidence": 0.92,
                    "probabilities": {
                        "data_quality": 0.92,
                        "model_behavior": 0.03,
                        "agronomic_context": 0.03,
                        "usability": 0.01,
                        "other": 0.01,
                    },
                }
            },
        }
    )
    engine = LayaDecisionPolicyEngine(
        "http://laya:8000",
        model_revision="hf-checkpoint-sha",
        timeout_seconds=0.75,
        api_key="local-secret",
        transport=transport,
    )

    result = engine.classify_feedback(
        FeedbackTriageInput(
            site_id="cicytex",
            comment="La sonda muestra un salto imposible respecto del perfil.",
        )
    )

    assert result == PolicySuggestion(
        category="data_quality",
        confidence=0.92,
        provider="laya-http",
        model_revision="hf-checkpoint-sha",
    )
    assert transport.calls == [
        {
            "url": "http://laya:8000/v1/systemone",
            "payload": {
                "state": {
                    "site_id": "cicytex",
                    "comment": "La sonda muestra un salto imposible respecto del perfil.",
                },
                "model": "multilingual",
                "questions": {
                    "feedback_category": {
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
                },
            },
            "timeout_seconds": 0.75,
            "headers": {"Authorization": "Bearer local-secret"},
        }
    ]


@pytest.mark.parametrize(
    "response",
    [
        {},
        {"answers": {}},
        {
            "answers": {
                "feedback_category": {
                    "type": "choice",
                    "choice": "not-an-allowed-category",
                    "answer_confidence": 0.99,
                }
            }
        },
    ],
)
def test_laya_adapter_fails_closed_on_an_invalid_response(response: dict):
    engine = LayaDecisionPolicyEngine(
        "http://laya:8000", model_revision="sha", transport=StubJsonTransport(response)
    )

    with pytest.raises(DecisionPolicyUnavailable):
        engine.classify_feedback(
            FeedbackTriageInput(site_id="pergamino", comment="Comentario para revisar.")
        )


def test_laya_adapter_translates_transport_timeouts_into_optional_engine_unavailability():
    engine = LayaDecisionPolicyEngine(
        "http://laya:8000",
        model_revision="sha",
        transport=StubJsonTransport(error=TimeoutError("slow sidecar")),
    )

    with pytest.raises(DecisionPolicyUnavailable):
        engine.classify_feedback(
            FeedbackTriageInput(site_id="melchor-romero", comment="Comentario para revisar.")
        )
