"""RED contract for the pure, gold-blind offline-v2 adapter boundary.

This module tests only canonical bytes and the inference-port seam.  It does
not execute Laya, Docker, a real corpus, or any scientific holdout.
"""

from __future__ import annotations

import inspect
import json
import math
from dataclasses import fields

import pytest
from human_feedback.loso_offline_adapter import (
    GoldBlindOfflineInput,
    GoldBlindOfflinePort,
    canonical_laya_loso_offline_request_bytes,
    validate_laya_loso_offline_response,
)

CATEGORIES = (
    "data_quality",
    "model_behavior",
    "agronomic_context",
    "usability",
    "other",
)


def _inputs():
    return (
        GoldBlindOfflineInput(opaque_token="a" * 64, comment="Observation one"),
        GoldBlindOfflineInput(opaque_token="b" * 64, comment="Observación dos"),
    )


def _prediction(ordinal: int):
    return {
        "ordinal": ordinal,
        "category": "data_quality",
        "probabilities": {
            "data_quality": 0.4,
            "model_behavior": 0.2,
            "agronomic_context": 0.15,
            "usability": 0.15,
            "other": 0.1,
        },
        "usage": {
            "state_tokens": 12,
            "state_tokens_dropped": 0,
            "truncated": False,
        },
    }


def _response(*, count: int = 2):
    return {
        "schema_version": "laya-gold-blind-offline-response-v2",
        "predictions": [_prediction(ordinal) for ordinal in range(count)],
    }


def _encoded(value=None, *, allow_nan: bool = False):
    return (
        json.dumps(
            _response() if value is None else value,
            ensure_ascii=False,
            allow_nan=allow_nan,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        + b"\n"
    )


def _canonical(value=None):
    return json.dumps(
        _response() if value is None else value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _private_failure(error: BaseException, *private_values: object) -> None:
    assert error.__cause__ is None
    assert error.__context__ is None
    assert error.__suppress_context__ is True
    rendered = repr((error.args, str(error), repr(error)))
    for value in private_values:
        assert str(value) not in rendered


def test_public_surface_is_minimal_and_has_no_caller_controlled_execution_profile():
    import human_feedback.loso_offline_adapter as module

    assert set(module.__all__) == {
        "GoldBlindOfflineInput",
        "GoldBlindOfflinePort",
        "canonical_laya_loso_offline_request_bytes",
        "validate_laya_loso_offline_response",
    }
    assert tuple(field.name for field in fields(GoldBlindOfflineInput)) == (
        "opaque_token",
        "comment",
    )
    assert tuple(inspect.signature(canonical_laya_loso_offline_request_bytes).parameters) == (
        "items",
    )
    assert tuple(inspect.signature(validate_laya_loso_offline_response).parameters) == (
        "stdout",
        "expected_count",
    )
    assert tuple(inspect.signature(GoldBlindOfflinePort.predict).parameters) == (
        "self",
        "canonical_request",
    )


def test_request_is_bounded_canonical_and_contains_only_opaque_tokens_and_comments():
    items = _inputs()
    first = canonical_laya_loso_offline_request_bytes(items)
    second = canonical_laya_loso_offline_request_bytes(items)
    decoded = json.loads(first)

    assert type(first) is bytes
    assert first == second
    assert decoded == {
        "schema_version": "laya-gold-blind-offline-request-v2",
        "items": [
            {"token": items[0].opaque_token, "comment": items[0].comment},
            {"token": items[1].opaque_token, "comment": items[1].comment},
        ],
    }
    assert all(set(item) == {"token", "comment"} for item in decoded["items"])
    forbidden_keys = {"example_id", "group_id", "site_id", "gold", "model", "task", "command"}
    assert not forbidden_keys.intersection(decoded)
    assert all(not forbidden_keys.intersection(item) for item in decoded["items"])
    assert items[0].opaque_token not in repr(items[0])
    assert items[0].comment not in repr(items[0])


def test_request_rejects_invalid_duplicate_empty_and_oversized_inputs_privately():
    valid = _inputs()[0]
    invalid_calls = (
        lambda: canonical_laya_loso_offline_request_bytes([valid]),
        lambda: canonical_laya_loso_offline_request_bytes(()),
        lambda: canonical_laya_loso_offline_request_bytes(
            (GoldBlindOfflineInput(opaque_token="not-canonical", comment="private"),)
        ),
        lambda: canonical_laya_loso_offline_request_bytes(
            (GoldBlindOfflineInput(opaque_token="c" * 64, comment=""),)
        ),
        lambda: canonical_laya_loso_offline_request_bytes((valid, valid)),
        lambda: canonical_laya_loso_offline_request_bytes(
            (
                GoldBlindOfflineInput(
                    opaque_token="d" * 64,
                    comment="X" * (1024 * 1024),
                ),
            )
        ),
    )

    for call in invalid_calls:
        with pytest.raises((TypeError, ValueError)) as caught:
            call()
        _private_failure(caught.value, "not-canonical", "private", "X" * 64)


def test_response_validator_returns_only_immutable_canonical_bytes():
    result = validate_laya_loso_offline_response(_encoded(), expected_count=2)

    assert type(result) is bytes
    assert result == _canonical()
    assert json.loads(result)["predictions"][1]["ordinal"] == 1


def test_response_ordinals_are_exact_ordered_and_cover_expected_batch_once():
    invalid = []
    missing = _response(count=1)
    invalid.append((missing, 2))
    duplicate = _response()
    duplicate["predictions"][1]["ordinal"] = 0
    invalid.append((duplicate, 2))
    reordered = _response()
    reordered["predictions"].reverse()
    invalid.append((reordered, 2))
    extra = _response(count=3)
    invalid.append((extra, 2))

    for response, expected_count in invalid:
        with pytest.raises((TypeError, ValueError)):
            validate_laya_loso_offline_response(_encoded(response), expected_count=expected_count)


def test_response_schema_probabilities_and_category_are_closed_and_finite():
    invalid = []
    extra = _response()
    extra["predictions"][0]["text"] = "PRIVATE-OUTPUT-CANARY"
    invalid.append(extra)
    missing_category = _response()
    missing_category["predictions"][0]["probabilities"].pop("other")
    invalid.append(missing_category)
    wrong_choice = _response()
    wrong_choice["predictions"][0]["category"] = "other"
    invalid.append(wrong_choice)
    bad_mass = _response()
    bad_mass["predictions"][0]["probabilities"]["other"] = 0.2
    invalid.append(bad_mass)
    nonfinite = _response()
    nonfinite["predictions"][0]["probabilities"]["other"] = math.nan
    invalid.append(nonfinite)

    for response in invalid:
        with pytest.raises((TypeError, ValueError)) as caught:
            validate_laya_loso_offline_response(
                _encoded(response, allow_nan=True), expected_count=2
            )
        _private_failure(caught.value, "PRIVATE-OUTPUT-CANARY")


def test_usage_must_prove_no_truncation_no_dropped_tokens_and_fixed_host_limit():
    import human_feedback.loso_offline_adapter as module

    assert type(module._MAX_STATE_TOKENS) is int and module._MAX_STATE_TOKENS > 0
    mutations = (
        ("truncated", True),
        ("state_tokens_dropped", 1),
        ("state_tokens", module._MAX_STATE_TOKENS + 1),
    )
    for name, invalid in mutations:
        response = _response()
        response["predictions"][0]["usage"][name] = invalid
        with pytest.raises((TypeError, ValueError)):
            validate_laya_loso_offline_response(_encoded(response), expected_count=2)

    missing = _response()
    missing["predictions"][0]["usage"].pop("state_tokens_dropped")
    with pytest.raises((TypeError, ValueError)):
        validate_laya_loso_offline_response(_encoded(missing), expected_count=2)


@pytest.mark.parametrize(
    "payload",
    (
        b"",
        b"[]",
        b"{}\n{}",
        b"\xffPRIVATE-STDOUT-CANARY",
        (
            b'{"schema_version":"laya-gold-blind-offline-response-v2",'
            b'"schema_version":"PRIVATE-STDOUT-CANARY","predictions":[]}'
        ),
        b" " * (1024 * 1024),
    ),
    ids=("empty", "array", "multiple-json", "invalid-utf8", "duplicate-key", "oversized"),
)
def test_malformed_duplicate_and_oversized_stdout_fail_without_retaining_payload(payload):
    with pytest.raises((TypeError, ValueError)) as caught:
        validate_laya_loso_offline_response(payload, expected_count=2)
    _private_failure(caught.value, "PRIVATE-STDOUT-CANARY")


def test_pure_seam_does_not_import_runtime_engine_or_execution_adapters():
    import human_feedback.loso_offline_adapter as module

    source = inspect.getsource(module)
    assert "local_docker_engine" not in source
    assert "runtime_execution" not in source
    assert "human_feedback.adapters" not in source
    assert "subprocess" not in source
    assert "docker" not in source.lower()
