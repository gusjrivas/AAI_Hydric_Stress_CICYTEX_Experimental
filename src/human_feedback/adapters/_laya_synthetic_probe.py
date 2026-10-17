"""Fixed offline synthetic Laya execution probe and closed observation parser."""

from __future__ import annotations

from human_feedback.adapters._laya_runtime_probe import PROBE_ENVIRONMENT
from human_feedback.runtime_execution_observation import (
    validate_synthetic_probe_observation as validate_synthetic_probe_observation,
)

SYNTHETIC_PROBE_ENVIRONMENT = PROBE_ENVIRONMENT

_SYNTHETIC_PROGRAM = r"""
import json

from laya.serve import build_router

STATE = "Synthetic offline runtime execution check; no field observation is present."
QUESTIONS = {
    "synthetic_category": {
        "type": "choice",
        "instructions": "Classify this synthetic runtime check.",
        "criteria": {
            "data_quality": "synthetic data-quality category",
            "model_behavior": "synthetic model-behavior category",
            "agronomic_context": "synthetic agronomic-context category",
            "usability": "synthetic usability category",
            "other": "synthetic other category",
        },
    }
}


def project(result):
    answer = result["answers"]["synthetic_category"]
    return {
        "choice": answer["choice"],
        "probabilities": answer["probabilities"],
        "confidence": answer["confidence"],
        "answer_confidence": answer["answer_confidence"],
    }


router = build_router()
first = project(router.predict(STATE, QUESTIONS, model="multilingual"))
second = project(router.predict(STATE, QUESTIONS, model="multilingual"))
print(
    json.dumps(
        {
            "schema_version": "laya-synthetic-execution-probe-v1",
            "predictions": [first, second],
        },
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )
)
""".strip()

SYNTHETIC_PROBE_ARGUMENTS = ("-I", "-B", "-c", _SYNTHETIC_PROGRAM)
