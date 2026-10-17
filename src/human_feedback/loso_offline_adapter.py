"""Pure byte contract for a future gold-blind offline LOSO adapter.

This module only projects private inputs into a closed request and validates a
closed response.  It performs no inference and grants no scientific authority.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from typing import Protocol

__all__ = (
    "GoldBlindOfflineInput",
    "GoldBlindOfflinePort",
    "canonical_laya_loso_offline_request_bytes",
    "validate_laya_loso_offline_response",
)

_REQUEST_SCHEMA_VERSION = "laya-gold-blind-offline-request-v2"
_RESPONSE_SCHEMA_VERSION = "laya-gold-blind-offline-response-v2"
_CATEGORIES = (
    "data_quality",
    "model_behavior",
    "agronomic_context",
    "usability",
    "other",
)
_TOKEN = re.compile(r"[0-9a-f]{64}\Z")
_REQUEST_FIELDS = frozenset({"schema_version", "items"})
_REQUEST_ITEM_FIELDS = frozenset({"token", "comment"})
_RESPONSE_FIELDS = frozenset({"schema_version", "predictions"})
_PREDICTION_FIELDS = frozenset({"ordinal", "category", "probabilities", "usage"})
_USAGE_FIELDS = frozenset({"state_tokens", "state_tokens_dropped", "truncated"})
_MAX_ITEMS = 512
_MAX_COMMENT_BYTES = 32 * 1024
_MAX_REQUEST_BYTES = 64 * 1024
_MAX_STDOUT_BYTES = 64 * 1024

# The pinned multilingual checkpoint declares max_len=1024.  This is only a
# technical upper bound: fitting is proved separately by zero dropped tokens
# and an explicit false truncation flag from the pinned implementation.
_MAX_STATE_TOKENS = 1024
_MASS_TOLERANCE = 5 * 0.5e-4 + 1e-12


def _fail() -> None:
    error = ValueError("gold-blind offline LOSO byte contract is invalid")
    error.__suppress_context__ = True
    raise error from None


def _valid_token(value: object) -> bool:
    return type(value) is str and _TOKEN.fullmatch(value) is not None


def _valid_comment(value: object) -> bool:
    if type(value) is not str or not value:
        return False
    try:
        return len(value.encode("utf-8")) <= _MAX_COMMENT_BYTES
    except UnicodeError:
        return False


@dataclass(frozen=True, slots=True, repr=False)
class GoldBlindOfflineInput:
    """One private opaque token and comment; never a scientific identifier."""

    opaque_token: str
    comment: str

    def __post_init__(self) -> None:
        if not _valid_token(self.opaque_token) or not _valid_comment(self.comment):
            _fail()


class GoldBlindOfflinePort(Protocol):
    """Minimal byte seam implemented by a later closed execution adapter."""

    def predict(self, canonical_request: bytes) -> bytes:
        """Return bounded response bytes for one already-canonical request."""


def canonical_laya_loso_offline_request_bytes(
    items: tuple[GoldBlindOfflineInput, ...],
) -> bytes:
    """Serialize a bounded batch without site, group, example or gold fields."""

    if (
        type(items) is not tuple
        or not 0 < len(items) <= _MAX_ITEMS
        or any(type(item) is not GoldBlindOfflineInput for item in items)
    ):
        _fail()
    tokens = tuple(item.opaque_token for item in items)
    if len(set(tokens)) != len(tokens):
        _fail()
    try:
        payload = json.dumps(
            {
                "schema_version": _REQUEST_SCHEMA_VERSION,
                "items": [{"token": item.opaque_token, "comment": item.comment} for item in items],
            },
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except Exception:
        payload = b""
    if not payload or len(payload) > _MAX_REQUEST_BYTES:
        _fail()
    return payload


def _closed_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, item in pairs:
        if type(key) is not str or key in value:
            _fail()
        value[key] = item
    return value


def _reject_nonfinite(_value: str) -> None:
    _fail()


def _finite_probability(value: object) -> bool:
    return type(value) in {int, float} and math.isfinite(value) and 0.0 <= value <= 1.0


def _valid_usage(value: object) -> bool:
    if type(value) is not dict or set(value) != _USAGE_FIELDS:
        return False
    state_tokens = value["state_tokens"]
    dropped = value["state_tokens_dropped"]
    truncated = value["truncated"]
    return (
        type(state_tokens) is int
        and 0 < state_tokens <= _MAX_STATE_TOKENS
        and type(dropped) is int
        and dropped == 0
        and type(truncated) is bool
        and truncated is False
    )


def _valid_prediction(value: object, *, ordinal: int) -> bool:
    if type(value) is not dict or set(value) != _PREDICTION_FIELDS:
        return False
    if type(value["ordinal"]) is not int or value["ordinal"] != ordinal:
        return False
    category = value["category"]
    if type(category) is not str or category not in _CATEGORIES:
        return False
    probabilities = value["probabilities"]
    if type(probabilities) is not dict or set(probabilities) != set(_CATEGORIES):
        return False
    amounts = tuple(probabilities[item] for item in _CATEGORIES)
    return (
        all(_finite_probability(item) for item in amounts)
        and math.isclose(sum(amounts), 1.0, rel_tol=0.0, abs_tol=_MASS_TOLERANCE)
        and probabilities[category] == max(amounts)
        and _valid_usage(value["usage"])
    )


def _validated_response(stdout: bytes, *, expected_count: int) -> bytes:
    if (
        type(stdout) is not bytes
        or not 0 < len(stdout) <= _MAX_STDOUT_BYTES
        or type(expected_count) is not int
        or not 0 < expected_count <= _MAX_ITEMS
    ):
        _fail()
    decoded = stdout.decode("utf-8")
    response = json.loads(
        decoded,
        object_pairs_hook=_closed_object,
        parse_constant=_reject_nonfinite,
    )
    if type(response) is not dict or set(response) != _RESPONSE_FIELDS:
        _fail()
    if response["schema_version"] != _RESPONSE_SCHEMA_VERSION:
        _fail()
    predictions = response["predictions"]
    if type(predictions) is not list or len(predictions) != expected_count:
        _fail()
    if not all(
        _valid_prediction(prediction, ordinal=ordinal)
        for ordinal, prediction in enumerate(predictions)
    ):
        _fail()
    return json.dumps(
        response,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def validate_laya_loso_offline_response(stdout: bytes, *, expected_count: int) -> bytes:
    """Validate child bytes and return an immutable canonical response."""

    try:
        return _validated_response(stdout, expected_count=expected_count)
    except Exception:
        pass
    # Raise outside the handler so parser failures cannot retain private child
    # output through exception context or traceback object graphs.
    _fail()
