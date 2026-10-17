"""RED contract for the fixed, stdin-only Laya LOSO child program.

The tests execute the fixed program with an in-memory ``laya.serve`` stub.  No
model, Docker daemon, network, corpus, holdout, or scientific authority is used.
"""

from __future__ import annotations

import io
import json
import sys
from types import ModuleType

import pytest

from human_feedback.loso_offline_adapter import (
    GoldBlindOfflineInput,
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


def _request(*comments: str) -> bytes:
    return canonical_laya_loso_offline_request_bytes(
        tuple(
            GoldBlindOfflineInput(opaque_token=f"{index + 1:064x}", comment=comment)
            for index, comment in enumerate(comments)
        )
    )


def _result(*, category: str = "data_quality", usage=None):
    return {
        "model": "laya-rl-agent",
        "answers": {
            "feedback_category": {
                "type": "choice",
                "choice": category,
                "probabilities": {
                    "data_quality": 0.4,
                    "model_behavior": 0.2,
                    "agronomic_context": 0.15,
                    "usability": 0.15,
                    "other": 0.1,
                },
                "confidence": 0.2,
                "answer_confidence": 0.4,
                "action": {"act_probability": 0.3},
            }
        },
        "usage": usage
        or {
            "input_tokens": 21,
            "output_tokens": 0,
            "state_tokens": 7,
            "state_tokens_dropped": 0,
            "truncated": False,
            "truncated_questions": [],
        },
        "routing": {"model": "multilingual", "reason": "private"},
    }


class _Router:
    def __init__(self, results=None):
        self.calls = []
        self._results = iter(results) if results is not None else None

    def predict(self, state, questions, *, model):
        self.calls.append((state, questions, model))
        if self._results is not None:
            return next(self._results)
        return _result()


class _ObservedBytesIO(io.BytesIO):
    def __init__(self, payload: bytes):
        super().__init__(payload)
        self.read_sizes = []

    def read(self, size=-1):
        self.read_sizes.append(size)
        return super().read(size)


class _BoundedInput:
    def __init__(self, payload: bytes):
        self.buffer = _ObservedBytesIO(payload)

    @property
    def read_sizes(self):
        return self.buffer.read_sizes


def _program():
    from human_feedback.adapters import _laya_offline_probe as probe

    return probe, probe.OFFLINE_PROBE_ARGUMENTS[-1]


@pytest.fixture(autouse=True)
def _require_offline_program_module():
    """Keep every RED causal until the fixed child module exists."""

    _program()


def _execute(monkeypatch, payload: bytes, *, router=None):
    probe, program = _program()
    router = router or _Router()
    laya = ModuleType("laya")
    serve = ModuleType("laya.serve")
    serve.build_router = lambda: router
    laya.serve = serve
    source = _BoundedInput(payload)
    output = io.StringIO()
    monkeypatch.setitem(sys.modules, "laya", laya)
    monkeypatch.setitem(sys.modules, "laya.serve", serve)
    monkeypatch.setattr(sys, "stdin", source)
    monkeypatch.setattr(sys, "stdout", output)
    exec(compile(program, "<fixed Laya LOSO offline program>", "exec"), {})
    return probe, router, source, output.getvalue().encode("utf-8")


def test_program_and_environment_are_fixed_immutable_offline_contracts():
    from human_feedback.adapters import _laya_runtime_probe as runtime_probe

    probe, program = _program()

    assert type(probe.OFFLINE_PROBE_ARGUMENTS) is tuple
    assert probe.OFFLINE_PROBE_ARGUMENTS[:3] == ("-I", "-B", "-c")
    assert len(probe.OFFLINE_PROBE_ARGUMENTS) == 4
    assert type(program) is str and program.isascii()
    compile(program, "<fixed Laya LOSO offline program>", "exec")
    assert type(probe.OFFLINE_PROBE_ENVIRONMENT) is tuple
    assert probe.OFFLINE_PROBE_ENVIRONMENT == runtime_probe.PROBE_ENVIRONMENT
    assert "LAYA_DEVICE=cpu" in probe.OFFLINE_PROBE_ENVIRONMENT
    assert "HF_HUB_OFFLINE=1" in probe.OFFLINE_PROBE_ENVIRONMENT
    assert "NUM_THREADS=2" in probe.OFFLINE_PROBE_ENVIRONMENT
    assert "sys.argv" not in program
    assert "os.environ" not in program
    assert "subprocess" not in program
    assert "65537" in program


def test_program_preserves_unicode_order_and_duplicate_comments_as_literal_data(monkeypatch):
    comments = (
        "Observación 🌱; __import__('os').system('PRIVATE-CANARY')",
        "observación repetida",
        "observación repetida",
    )
    probe, router, source, stdout = _execute(monkeypatch, _request(*comments))

    assert source.read_sizes == [64 * 1024 + 1]
    assert [call[0] for call in router.calls] == list(comments)
    assert all(call[2] == "multilingual" for call in router.calls)
    assert validate_laya_loso_offline_response(stdout, expected_count=3) == stdout.rstrip(b"\n")
    response = json.loads(stdout)
    assert [item["ordinal"] for item in response["predictions"]] == [0, 1, 2]
    assert comments[0].encode("utf-8") not in stdout
    assert "PRIVATE-CANARY" not in stdout.decode("utf-8")
    assert probe.OFFLINE_PROBE_ARGUMENTS[-1] == _program()[1]


def test_program_uses_one_closed_feedback_question_and_projects_only_approved_fields(
    monkeypatch,
):
    upstream = _result()
    router = _Router([upstream])
    _probe, router, _source, stdout = _execute(
        monkeypatch, _request("bounded consultative feedback"), router=router
    )

    _state, questions, model = router.calls[0]
    assert model == "multilingual"
    assert set(questions) == {"feedback_category"}
    question = questions["feedback_category"]
    assert question["type"] == "choice"
    assert tuple(question["criteria"]) == CATEGORIES
    response = json.loads(stdout)
    assert set(response) == {"schema_version", "predictions"}
    assert response["schema_version"] == "laya-gold-blind-offline-response-v2"
    prediction = response["predictions"][0]
    assert set(prediction) == {"ordinal", "category", "probabilities", "usage"}
    assert prediction["usage"] == {
        "state_tokens": 7,
        "state_tokens_dropped": 0,
        "truncated": False,
    }
    assert set(prediction["probabilities"]) == set(CATEGORIES)
    projected_keys = (
        set(response)
        | set(prediction)
        | set(prediction["probabilities"])
        | set(prediction["usage"])
    )
    assert {
        "model",
        "routing",
        "confidence",
        "answer_confidence",
        "action",
        "input_tokens",
        "output_tokens",
        "truncated_questions",
    }.isdisjoint(projected_keys)


@pytest.mark.parametrize(
    "payload",
    (
        b"",
        b"[]",
        b"{}",
        b"{}\n",
        b"{" + b'"schema_version":"laya-gold-blind-offline-request-v2",' * 2 + b'"items":[]}',
        b'[{"comment":"PRIVATE","token":"' + b"a" * 64 + b'"}]',
        b"\xffPRIVATE-INPUT-CANARY",
    ),
    ids=(
        "empty",
        "array",
        "object",
        "noncanonical-newline",
        "duplicate-key",
        "missing-envelope",
        "invalid-utf8",
    ),
)
def test_program_rejects_malformed_noncanonical_or_open_requests_without_inference(
    monkeypatch, payload
):
    router = _Router()
    with pytest.raises(Exception) as caught:
        _execute(monkeypatch, payload, router=router)
    assert router.calls == []
    assert "PRIVATE-INPUT-CANARY" not in str(caught.value)
    assert "PRIVATE" not in str(caught.value)


def test_program_reads_at_most_cap_plus_one_and_rejects_oversized_stdin(monkeypatch):
    router = _Router()
    with pytest.raises(Exception):
        _execute(monkeypatch, b"x" * (64 * 1024 + 1), router=router)
    assert router.calls == []


@pytest.mark.parametrize(
    "usage",
    (
        {"state_tokens": True, "state_tokens_dropped": 0, "truncated": False},
        {"state_tokens": 7, "state_tokens_dropped": 1, "truncated": False},
        {"state_tokens": 7, "state_tokens_dropped": 0, "truncated": True},
        {"state_tokens": 1025, "state_tokens_dropped": 0, "truncated": False},
        {"state_tokens": 7, "truncated": False},
    ),
    ids=("bool-count", "dropped", "truncated", "over-model-limit", "missing-field"),
)
def test_program_rejects_invalid_pinned_usage_instead_of_emitting_partial_output(
    monkeypatch, usage
):
    router = _Router([_result(usage=usage)])
    with pytest.raises(Exception):
        _execute(monkeypatch, _request("private comment"), router=router)


@pytest.mark.parametrize(
    "mutation",
    ("missing-answer", "extra-probability", "inferior-category", "boolean-probability"),
)
def test_program_rejects_malformed_laya_projection(monkeypatch, mutation):
    result = _result()
    answer = result["answers"]["feedback_category"]
    if mutation == "missing-answer":
        result["answers"].pop("feedback_category")
    elif mutation == "extra-probability":
        answer["probabilities"]["caller_selected"] = 0.0
    elif mutation == "inferior-category":
        answer["choice"] = "other"
    else:
        answer["probabilities"]["data_quality"] = True
    with pytest.raises(Exception):
        _execute(
            monkeypatch,
            _request("private malformed upstream"),
            router=_Router([result]),
        )


def test_program_accepts_rounded_argmax_ties_without_inventing_selection_policy(monkeypatch):
    result = _result(category="model_behavior")
    result["answers"]["feedback_category"]["probabilities"] = {
        "data_quality": 0.3,
        "model_behavior": 0.3,
        "agronomic_context": 0.2,
        "usability": 0.1,
        "other": 0.1,
    }
    _probe, _router, _source, stdout = _execute(
        monkeypatch, _request("bounded tie"), router=_Router([result])
    )
    assert validate_laya_loso_offline_response(stdout, expected_count=1) == stdout.rstrip(b"\n")


def test_program_refuses_to_emit_stdout_larger_than_closed_response_budget(monkeypatch):
    comments = tuple("x" for _ in range(512))
    router = _Router()
    with pytest.raises(Exception):
        _execute(monkeypatch, _request(*comments), router=router)
    assert len(router.calls) == 512
