"""Pure shared contract for one closed synthetic execution observation."""

from __future__ import annotations

import ast
import copy
import importlib
import inspect
import json

import pytest


def _module():
    return importlib.import_module("human_feedback.runtime_execution_observation")


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
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("ascii")
        + b"\n"
    )


def _canonical(value=None):
    return json.dumps(
        _observation() if value is None else value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")


def _imported_modules(source: str) -> frozenset[str]:
    result = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            result.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            result.add(node.module)
    return frozenset(result)


def test_shared_observation_module_is_pure_and_adapter_reexports_the_same_callable():
    module = _module()
    from human_feedback.adapters import _laya_synthetic_probe as adapter

    assert module.__all__ == ("validate_synthetic_probe_observation",)
    assert (
        adapter.validate_synthetic_probe_observation is module.validate_synthetic_probe_observation
    )
    hostile = _imported_modules(
        "import socket\n"
        "from os import path\n"
        "from human_feedback.adapters import _laya_synthetic_probe\n"
    )
    assert hostile == frozenset({"socket", "os", "human_feedback.adapters"})

    imports = _imported_modules(inspect.getsource(module))
    assert not any(name.startswith("human_feedback.adapters") for name in imports)
    assert not any(
        name.split(".")[0]
        in {"docker", "os", "pathlib", "shutil", "socket", "subprocess", "tempfile"}
        for name in imports
    )


def test_shared_validator_returns_deterministic_immutable_canonical_bytes():
    validate = _module().validate_synthetic_probe_observation
    first = validate(_encoded())
    second = validate(_encoded())

    assert type(first) is bytes
    assert first == second == _canonical()
    assert not first.endswith(b"\n")


@pytest.mark.parametrize(
    "mutation",
    [
        "wrong_schema",
        "extra_root",
        "extra_prediction",
        "unknown_category",
        "nondeterministic",
    ],
)
def test_shared_validator_preserves_the_closed_schema(mutation):
    validate = _module().validate_synthetic_probe_observation
    value = _observation()
    if mutation == "wrong_schema":
        value["schema_version"] = "future-schema"
    elif mutation == "extra_root":
        value["timestamp"] = "2026-10-17T00:00:00Z"
    elif mutation == "extra_prediction":
        value["predictions"][0]["text"] = "private"
        value["predictions"][1] = copy.deepcopy(value["predictions"][0])
    elif mutation == "unknown_category":
        probabilities = value["predictions"][0]["probabilities"]
        probabilities["unclassified"] = probabilities.pop("other")
        value["predictions"][1] = copy.deepcopy(value["predictions"][0])
    elif mutation == "nondeterministic":
        value["predictions"][1]["answer_confidence"] = 0.44

    with pytest.raises(ValueError, match="synthetic execution probe"):
        validate(_encoded(value))


def test_shared_validator_preserves_argmax_and_rounded_tie_semantics():
    validate = _module().validate_synthetic_probe_observation
    invalid = _observation()
    invalid["predictions"][0]["choice"] = "other"
    invalid["predictions"][1] = copy.deepcopy(invalid["predictions"][0])
    with pytest.raises(ValueError, match="synthetic execution probe"):
        validate(_encoded(invalid))

    for choice in ("data_quality", "model_behavior"):
        tied = _observation()
        prediction = tied["predictions"][0]
        prediction["choice"] = choice
        prediction["probabilities"] = {
            "data_quality": 0.3,
            "model_behavior": 0.3,
            "agronomic_context": 0.2,
            "usability": 0.1,
            "other": 0.1,
        }
        tied["predictions"][1] = copy.deepcopy(prediction)
        assert validate(_encoded(tied)) == _canonical(tied)


def test_shared_validator_rejects_duplicate_keys_nonfinite_values_and_oversize():
    validate = _module().validate_synthetic_probe_observation
    duplicate = (
        b'{"schema_version":"laya-synthetic-execution-probe-v1",'
        b'"schema_version":"laya-synthetic-execution-probe-v1","predictions":[]}\n'
    )
    nonfinite = _encoded().replace(b'"confidence":0.0756', b'"confidence":NaN')
    for payload in (duplicate, nonfinite, b" " * (1024 * 1024)):
        with pytest.raises(ValueError, match="synthetic execution probe"):
            validate(payload)


@pytest.mark.parametrize(
    "payload",
    [
        b'{"private_canary":"DO_NOT_DISCLOSE_SHARED_7f31"',
        b"\xffDO_NOT_DISCLOSE_SHARED_7f31",
    ],
)
def test_shared_parser_failures_do_not_retain_child_stdout(payload):
    validate = _module().validate_synthetic_probe_observation
    with pytest.raises(ValueError, match="synthetic execution probe") as caught:
        validate(payload)

    error = caught.value
    assert error.__cause__ is None
    assert error.__context__ is None
    assert error.__suppress_context__ is True
    rendered = repr((error.args, str(error), repr(error)))
    assert "DO_NOT_DISCLOSE_SHARED_7f31" not in rendered
