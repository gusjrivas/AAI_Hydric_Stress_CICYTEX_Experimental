"""Fixed stdin-only Laya program for bounded offline LOSO batches."""

from __future__ import annotations

from human_feedback.adapters._laya_runtime_probe import PROBE_ENVIRONMENT

OFFLINE_PROBE_ENVIRONMENT = PROBE_ENVIRONMENT

_OFFLINE_PROGRAM = r"""
import json
import math
import re
import sys

from laya.serve import build_router


REQUEST_SCHEMA = "laya-gold-blind-offline-request-v2"
RESPONSE_SCHEMA = "laya-gold-blind-offline-response-v2"
CATEGORIES = (
    "data_quality",
    "model_behavior",
    "agronomic_context",
    "usability",
    "other",
)
QUESTIONS = {
    "feedback_category": {
        "type": "choice",
        "instructions": "Classify this human feedback for consultative review.",
        "criteria": {
            "data_quality": "feedback about data quality",
            "model_behavior": "feedback about model behavior",
            "agronomic_context": "feedback about agronomic context",
            "usability": "feedback about usability",
            "other": "feedback outside the other categories",
        },
    }
}
TOKEN = re.compile(r"[0-9a-f]{64}\Z")
MAX_INPUT_BYTES = 64 * 1024
MAX_OUTPUT_BYTES = 64 * 1024
MAX_COMMENT_BYTES = 32 * 1024
MAX_ITEMS = 512
MAX_STATE_TOKENS = 1024
MASS_TOLERANCE = 5 * 0.5e-4 + 1e-12


def fail():
    raise ValueError("fixed offline Laya program rejected its input or result") from None


def closed_object(pairs):
    value = {}
    for key, item in pairs:
        if type(key) is not str or key in value:
            fail()
        value[key] = item
    return value


def reject_nonfinite(_value):
    fail()


def canonical_json(value):
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def valid_probability(value):
    return (
        type(value) in (int, float)
        and math.isfinite(value)
        and 0.0 <= value <= 1.0
    )


def parse_request(raw):
    if not raw or len(raw) > MAX_INPUT_BYTES:
        fail()
    decoded = raw.decode("utf-8")
    request = json.loads(
        decoded,
        object_pairs_hook=closed_object,
        parse_constant=reject_nonfinite,
    )
    if canonical_json(request) != raw:
        fail()
    if type(request) is not dict or set(request) != {"schema_version", "items"}:
        fail()
    if request["schema_version"] != REQUEST_SCHEMA:
        fail()
    items = request["items"]
    if type(items) is not list or not 0 < len(items) <= MAX_ITEMS:
        fail()
    tokens = []
    for item in items:
        if type(item) is not dict or set(item) != {"token", "comment"}:
            fail()
        token = item["token"]
        comment = item["comment"]
        if type(token) is not str or TOKEN.fullmatch(token) is None:
            fail()
        if type(comment) is not str or not comment:
            fail()
        if len(comment.encode("utf-8")) > MAX_COMMENT_BYTES:
            fail()
        tokens.append(token)
    if len(set(tokens)) != len(tokens):
        fail()
    return items


def project(result, ordinal):
    if type(result) is not dict:
        fail()
    answers = result.get("answers")
    usage = result.get("usage")
    if type(answers) is not dict or "feedback_category" not in answers:
        fail()
    answer = answers["feedback_category"]
    if type(answer) is not dict:
        fail()
    category = answer.get("choice")
    probabilities = answer.get("probabilities")
    if type(category) is not str or category not in CATEGORIES:
        fail()
    if type(probabilities) is not dict or set(probabilities) != set(CATEGORIES):
        fail()
    amounts = tuple(probabilities[name] for name in CATEGORIES)
    if not all(valid_probability(amount) for amount in amounts):
        fail()
    if not math.isclose(
        sum(amounts), 1.0, rel_tol=0.0, abs_tol=MASS_TOLERANCE
    ):
        fail()
    if probabilities[category] != max(amounts):
        fail()
    if type(usage) is not dict:
        fail()
    if not {"state_tokens", "state_tokens_dropped", "truncated"} <= set(usage):
        fail()
    state_tokens = usage["state_tokens"]
    state_tokens_dropped = usage["state_tokens_dropped"]
    truncated = usage["truncated"]
    if type(state_tokens) is not int or not 0 < state_tokens <= MAX_STATE_TOKENS:
        fail()
    if type(state_tokens_dropped) is not int or state_tokens_dropped != 0:
        fail()
    if type(truncated) is not bool or truncated is not False:
        fail()
    return {
        "ordinal": ordinal,
        "category": category,
        "probabilities": {name: probabilities[name] for name in CATEGORIES},
        "usage": {
            "state_tokens": state_tokens,
            "state_tokens_dropped": state_tokens_dropped,
            "truncated": truncated,
        },
    }


def run():
    raw = sys.stdin.buffer.read(65537)
    items = parse_request(raw)
    router = build_router()
    predictions = [
        project(
            router.predict(item["comment"], QUESTIONS, model="multilingual"),
            ordinal,
        )
        for ordinal, item in enumerate(items)
    ]
    rendered = canonical_json(
        {"schema_version": RESPONSE_SCHEMA, "predictions": predictions}
    )
    if not rendered or len(rendered) > MAX_OUTPUT_BYTES:
        fail()
    sys.stdout.write(rendered.decode("utf-8") + "\n")


failed = False
try:
    run()
except Exception:
    failed = True
if failed:
    fail()
""".strip()

OFFLINE_PROBE_ARGUMENTS = ("-I", "-B", "-c", _OFFLINE_PROGRAM)
