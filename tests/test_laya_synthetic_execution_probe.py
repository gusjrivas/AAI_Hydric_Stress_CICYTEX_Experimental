"""Closed synthetic execution observation; no private corpus or real inference in tests."""

import copy
import json
import math

import pytest

CATEGORIES = (
    "data_quality",
    "model_behavior",
    "agronomic_context",
    "usability",
    "other",
)


def _prediction():
    return {
        "choice": "data_quality",
        "probabilities": {
            "data_quality": 0.4,
            "model_behavior": 0.2,
            "agronomic_context": 0.15,
            "usability": 0.15,
            "other": 0.1,
        },
        "confidence": 0.0756,
        "answer_confidence": 0.43,
    }


def _observation():
    prediction = _prediction()
    return {
        "schema_version": "laya-synthetic-execution-probe-v1",
        "predictions": [prediction, copy.deepcopy(prediction)],
    }


def _encoded(value=None):
    return (
        json.dumps(
            _observation() if value is None else value,
            ensure_ascii=True,
            allow_nan=True,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("ascii")
        + b"\n"
    )


def _canonical_bytes(value=None):
    return json.dumps(
        _observation() if value is None else value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")


def _validate(value=None):
    from human_feedback.adapters._laya_synthetic_probe import (
        validate_synthetic_probe_observation,
    )

    return validate_synthetic_probe_observation(_encoded(value))


def test_program_and_environment_are_fixed_cpu_offline_contracts():
    from human_feedback.adapters import _laya_runtime_probe as load_probe
    from human_feedback.adapters import _laya_synthetic_probe as probe

    assert type(probe.SYNTHETIC_PROBE_ARGUMENTS) is tuple
    assert probe.SYNTHETIC_PROBE_ARGUMENTS[:3] == ("-I", "-B", "-c")
    assert len(probe.SYNTHETIC_PROBE_ARGUMENTS) == 4
    program = probe.SYNTHETIC_PROBE_ARGUMENTS[-1]
    assert type(program) is str
    assert program.isascii()
    compile(program, "<fixed synthetic Laya execution probe>", "exec")
    assert "build_router" in program
    assert "router.predict" in program
    assert "multilingual" in program
    assert all(category in program for category in CATEGORIES)
    assert "sys.argv" not in program
    assert "input(" not in program
    assert type(probe.SYNTHETIC_PROBE_ENVIRONMENT) is tuple
    assert probe.SYNTHETIC_PROBE_ENVIRONMENT == load_probe.PROBE_ENVIRONMENT
    assert "LAYA_DEVICE=cpu" in probe.SYNTHETIC_PROBE_ENVIRONMENT
    assert "HF_HUB_OFFLINE=1" in probe.SYNTHETIC_PROBE_ENVIRONMENT
    assert "NUM_THREADS=2" in probe.SYNTHETIC_PROBE_ENVIRONMENT


def test_validator_accepts_only_two_identical_canonical_predictions():
    result = _validate()
    assert type(result) is bytes
    assert result == _canonical_bytes()


@pytest.mark.parametrize("count", [0, 1, 3])
def test_validator_requires_exactly_two_predictions(count):
    value = _observation()
    value["predictions"] = [_prediction() for _ in range(count)]
    with pytest.raises(ValueError, match="synthetic execution probe"):
        _validate(value)


def test_validator_rejects_nondeterministic_second_prediction():
    value = _observation()
    value["predictions"][1]["answer_confidence"] = 0.44
    with pytest.raises(ValueError, match="synthetic execution probe"):
        _validate(value)


@pytest.mark.parametrize(
    ("scope", "field", "value"),
    [
        ("root", "timestamp", "2026-10-17T00:00:00Z"),
        ("root", "path", "/opt/private"),
        ("root", "id", "sample-1"),
        ("prediction", "text", "private feedback"),
        ("prediction", "routing", {"model": "multilingual"}),
        ("prediction", "usage", {"input_tokens": 1}),
    ],
)
def test_validator_rejects_all_noncontract_fields(scope, field, value):
    observation = _observation()
    target = observation if scope == "root" else observation["predictions"][0]
    target[field] = value
    observation["predictions"][1] = copy.deepcopy(observation["predictions"][0])
    with pytest.raises(ValueError, match="synthetic execution probe"):
        _validate(observation)


@pytest.mark.parametrize("mutation", ["missing", "extra"])
def test_probability_categories_are_exact(mutation):
    observation = _observation()
    probabilities = observation["predictions"][0]["probabilities"]
    if mutation == "missing":
        probabilities.pop("other")
    elif mutation == "extra":
        probabilities["unclassified"] = 0.0
    observation["predictions"][1] = copy.deepcopy(observation["predictions"][0])
    with pytest.raises(ValueError, match="synthetic execution probe"):
        _validate(observation)


def test_declared_choice_must_be_one_of_the_closed_categories():
    observation = _observation()
    observation["predictions"][0]["choice"] = "unclassified"
    observation["predictions"][1] = copy.deepcopy(observation["predictions"][0])
    with pytest.raises(ValueError, match="synthetic execution probe"):
        _validate(observation)


@pytest.mark.parametrize("bad", [-0.0001, 1.0001, math.nan, math.inf, -math.inf, True])
def test_probabilities_must_be_finite_real_values_in_closed_unit_interval(bad):
    observation = _observation()
    observation["predictions"][0]["probabilities"]["data_quality"] = bad
    observation["predictions"][1] = copy.deepcopy(observation["predictions"][0])
    with pytest.raises(ValueError, match="synthetic execution probe"):
        _validate(observation)


def test_probability_mass_allows_four_decimal_rounding_only():
    observation = _observation()
    observation["predictions"][0]["probabilities"]["other"] = 0.1002
    observation["predictions"][1] = copy.deepcopy(observation["predictions"][0])
    assert _validate(observation) == _canonical_bytes(observation)

    observation["predictions"][0]["probabilities"]["other"] = 0.101
    observation["predictions"][1] = copy.deepcopy(observation["predictions"][0])
    with pytest.raises(ValueError, match="synthetic execution probe"):
        _validate(observation)


@pytest.mark.parametrize("field", ["confidence", "answer_confidence"])
@pytest.mark.parametrize("bad", [-0.0001, 1.0001, math.nan, math.inf, True])
def test_both_confidence_fields_are_distinct_finite_unit_interval_values(field, bad):
    observation = _observation()
    observation["predictions"][0][field] = bad
    observation["predictions"][1] = copy.deepcopy(observation["predictions"][0])
    with pytest.raises(ValueError, match="synthetic execution probe"):
        _validate(observation)


def test_entropy_confidence_and_calibrated_answer_confidence_remain_separate_fields():
    observation = _observation()
    observation["predictions"][0]["confidence"] = 0.43
    observation["predictions"][1] = copy.deepcopy(observation["predictions"][0])
    assert _validate(observation) == _canonical_bytes(observation)


@pytest.mark.parametrize(
    "payload",
    [
        b"",
        b"[]\n",
        b"{}\n",
        b'{"schema_version":"laya-synthetic-execution-probe-v1"}\n',
        b"{}\n{}\n",
        b"\xff",
    ],
)
def test_validator_rejects_malformed_or_noncanonical_json(payload):
    from human_feedback.adapters._laya_synthetic_probe import (
        validate_synthetic_probe_observation,
    )

    with pytest.raises(ValueError, match="synthetic execution probe"):
        validate_synthetic_probe_observation(payload)


def test_validator_rejects_duplicate_json_keys_and_oversized_stdout():
    from human_feedback.adapters._laya_synthetic_probe import (
        validate_synthetic_probe_observation,
    )

    duplicate = (
        b'{"schema_version":"laya-synthetic-execution-probe-v1",'
        b'"schema_version":"laya-synthetic-execution-probe-v1","predictions":[]}\n'
    )
    with pytest.raises(ValueError, match="synthetic execution probe"):
        validate_synthetic_probe_observation(duplicate)
    with pytest.raises(ValueError, match="synthetic execution probe"):
        validate_synthetic_probe_observation(b" " * (1024 * 1024))
