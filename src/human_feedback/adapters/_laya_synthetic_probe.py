"""Fixed offline synthetic Laya execution probe and closed observation parser."""

from __future__ import annotations

import json
import math

from human_feedback.adapters._laya_runtime_probe import PROBE_ENVIRONMENT

_SCHEMA_VERSION = "laya-synthetic-execution-probe-v1"
_CATEGORIES = (
    "data_quality",
    "model_behavior",
    "agronomic_context",
    "usability",
    "other",
)
_PREDICTION_FIELDS = frozenset({"choice", "probabilities", "confidence", "answer_confidence"})
_MAX_STDOUT_BYTES = 64 * 1024
_MASS_TOLERANCE = 5 * 0.5e-4 + 1e-12

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


def _fail() -> None:
    error = ValueError("synthetic execution probe validation failed")
    error.__suppress_context__ = True
    raise error from None


def _closed_object(pairs):
    result = {}
    for key, value in pairs:
        if type(key) is not str or key in result:
            _fail()
        result[key] = value
    return result


def _reject_nonfinite(_value):
    _fail()


def _finite_probability(value) -> bool:
    return type(value) in {int, float} and math.isfinite(value) and 0.0 <= value <= 1.0


def _validate_prediction(value) -> None:
    if type(value) is not dict or set(value) != _PREDICTION_FIELDS:
        _fail()
    if type(value["choice"]) is not str or value["choice"] not in _CATEGORIES:
        _fail()
    probabilities = value["probabilities"]
    if type(probabilities) is not dict or set(probabilities) != set(_CATEGORIES):
        _fail()
    values = tuple(probabilities[category] for category in _CATEGORIES)
    if not all(_finite_probability(item) for item in values):
        _fail()
    if not math.isclose(sum(values), 1.0, rel_tol=0.0, abs_tol=_MASS_TOLERANCE):
        _fail()
    if probabilities[value["choice"]] != max(values):
        _fail()
    if not _finite_probability(value["confidence"]):
        _fail()
    if not _finite_probability(value["answer_confidence"]):
        _fail()


def _validated_observation(stdout: bytes) -> bytes:
    if type(stdout) is not bytes or not 0 < len(stdout) <= _MAX_STDOUT_BYTES:
        _fail()
    decoded = stdout.decode("ascii")
    observation = json.loads(
        decoded,
        object_pairs_hook=_closed_object,
        parse_constant=_reject_nonfinite,
    )
    if type(observation) is not dict or set(observation) != {
        "schema_version",
        "predictions",
    }:
        _fail()
    if observation["schema_version"] != _SCHEMA_VERSION:
        _fail()
    predictions = observation["predictions"]
    if type(predictions) is not list or len(predictions) != 2:
        _fail()
    for prediction in predictions:
        _validate_prediction(prediction)
    first = json.dumps(
        predictions[0],
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    second = json.dumps(
        predictions[1],
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    if first != second:
        _fail()
    return json.dumps(
        observation,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")


def validate_synthetic_probe_observation(stdout: bytes) -> bytes:
    """Validate bounded child output and return immutable canonical observation bytes."""

    try:
        return _validated_observation(stdout)
    except Exception:
        pass
    # Raise outside the handler so parser exceptions cannot retain child bytes
    # through ``__context__`` even when traceback rendering ignores suppression.
    _fail()
