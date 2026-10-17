from __future__ import annotations

import copy
import inspect
import json

import pytest

from tests.test_laya_local_docker_engine import (
    CONTAINER_ID,
    IMAGE_ID,
    NONCE,
    FakeTransport,
    _container_inspect,
    _engine,
    _info,
    _log_frame,
    _response,
    _version,
)


def _synthetic_surface():
    from human_feedback.adapters.local_docker_engine import LocalDockerEngine

    return (
        LocalDockerEngine.create_closed_synthetic_probe_container,
        LocalDockerEngine.inspect_closed_synthetic_probe_container,
        LocalDockerEngine.run_closed_synthetic_probe,
    )


def _synthetic_container_inspect(*, nonce: str = NONCE, completed: bool = False):
    from human_feedback.adapters._laya_synthetic_probe import (
        SYNTHETIC_PROBE_ARGUMENTS,
        SYNTHETIC_PROBE_ENVIRONMENT,
    )

    value = copy.deepcopy(_container_inspect(nonce=nonce))
    value["Config"]["Cmd"] = list(SYNTHETIC_PROBE_ARGUMENTS)
    value["Config"]["Env"] = list(SYNTHETIC_PROBE_ENVIRONMENT)
    if completed:
        value["State"] = {
            "Status": "exited",
            "Running": False,
            "Paused": False,
            "Restarting": False,
            "OOMKilled": False,
            "Dead": False,
            "ExitCode": 0,
        }
    return value


def _synthetic_observation() -> tuple[bytes, bytes]:
    prediction = {
        "choice": "data_quality",
        "probabilities": {
            "data_quality": 0.6,
            "model_behavior": 0.1,
            "agronomic_context": 0.1,
            "usability": 0.1,
            "other": 0.1,
        },
        "confidence": 0.0756,
        "answer_confidence": 0.43,
    }
    value = {
        "schema_version": "laya-synthetic-execution-probe-v1",
        "predictions": [prediction, copy.deepcopy(prediction)],
    }
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("ascii")
    return canonical + b"\n", canonical


def _assert_no_broad_or_image_operations(transport: FakeTransport) -> None:
    paths = [call["path"] for call in transport.calls]
    assert not any("/images/" in path for path in paths)
    assert not any(path.endswith("/containers/json") for path in paths)
    assert not any("prune" in path for path in paths)
    assert not any(call["method"] == "UPLOAD" for call in transport.calls)


def test_synthetic_surface_is_explicit_and_accepts_no_command_environment_or_profile():
    create, inspect_closed, run = _synthetic_surface()
    assert tuple(inspect.signature(create).parameters) == ("self", "image_id")
    assert tuple(inspect.signature(inspect_closed).parameters) == (
        "self",
        "container_id",
        "expected_image_id",
    )
    assert tuple(inspect.signature(run).parameters) == (
        "self",
        "container_id",
        "expected_image_id",
    )

    transport = FakeTransport([])
    engine = _engine(transport)
    for forbidden in ({"command": ["sh"]}, {"environment": ["X=1"]}, {"profile": {}}):
        with pytest.raises(TypeError):
            engine.create_closed_synthetic_probe_container(IMAGE_ID, **forbidden)
    assert transport.calls == []


def test_synthetic_create_freezes_pr40_isolation_and_only_changes_fixed_probe_program(
    monkeypatch,
):
    _synthetic_surface()
    from human_feedback.adapters import local_docker_engine as module
    from human_feedback.adapters._laya_synthetic_probe import (
        SYNTHETIC_PROBE_ARGUMENTS,
        SYNTHETIC_PROBE_ENVIRONMENT,
    )

    monkeypatch.setattr(module.secrets, "token_hex", lambda _size: "d" * 32)
    transport = FakeTransport(
        [_response(200, _version()), _response(200, _info()), _response(201, {"Id": CONTAINER_ID})]
    )
    engine = _engine(transport)

    assert engine.create_closed_synthetic_probe_container(IMAGE_ID) == CONTAINER_ID
    create_call = transport.calls[-1]
    payload = json.loads(create_call["body"])
    materialization = module._closed_probe_payload(IMAGE_ID, NONCE)
    assert payload["HostConfig"] == materialization["HostConfig"]
    assert payload["NetworkDisabled"] is True
    assert payload["User"] == materialization["User"] == "65532:65532"
    assert payload["WorkingDir"] == materialization["WorkingDir"]
    assert payload["Entrypoint"] == materialization["Entrypoint"]
    assert payload["Cmd"] == list(SYNTHETIC_PROBE_ARGUMENTS)
    assert payload["Env"] == list(SYNTHETIC_PROBE_ENVIRONMENT)
    assert create_call["path"].endswith("?name=aai-laya-synthetic-probe-" + "d" * 32)
    assert engine._owned_images == set()
    assert engine._image_intents == set()
    _assert_no_broad_or_image_operations(transport)


def test_synthetic_run_reinspects_fresh_state_then_returns_only_canonical_bytes():
    _synthetic_surface()
    stdout, canonical = _synthetic_observation()
    transport = FakeTransport(
        [
            _response(200, _version()),
            _response(200, _info()),
            _response(201, {"Id": CONTAINER_ID}),
            _response(200, _synthetic_container_inspect()),
            _response(200, _synthetic_container_inspect()),
            _response(204),
            _response(200, {"StatusCode": 0}),
            _response(200, _synthetic_container_inspect(completed=True)),
            _response(200, _log_frame(1, stdout) + _log_frame(2, b"bounded warning\n")),
        ]
    )
    engine = _engine(transport)
    container_id = engine.create_closed_synthetic_probe_container(IMAGE_ID)

    result = engine.run_closed_synthetic_probe(container_id, expected_image_id=IMAGE_ID)

    assert result == canonical
    assert type(result) is bytes
    methods = [call["method"] for call in transport.calls[3:]]
    assert methods == ["GET", "GET", "POST", "POST", "GET", "GET"]
    assert "stdout=1&stderr=1" in transport.calls[-1]["path"]
    _assert_no_broad_or_image_operations(transport)


def test_materialization_and_synthetic_profiles_are_rejected_in_both_directions():
    _synthetic_surface()
    from human_feedback.adapters.local_docker_engine import LocalDockerEngineError

    synthetic_transport = FakeTransport(
        [
            _response(200, _version()),
            _response(200, _info()),
            _response(201, {"Id": CONTAINER_ID}),
            _response(200, _container_inspect()),
        ]
    )
    synthetic_engine = _engine(synthetic_transport)
    synthetic_engine.create_closed_synthetic_probe_container(IMAGE_ID)
    with pytest.raises(LocalDockerEngineError, match="isolation changed"):
        synthetic_engine.inspect_closed_synthetic_probe_container(
            CONTAINER_ID, expected_image_id=IMAGE_ID
        )

    materialization_transport = FakeTransport(
        [
            _response(200, _version()),
            _response(200, _info()),
            _response(201, {"Id": CONTAINER_ID}),
            _response(200, _synthetic_container_inspect()),
        ]
    )
    materialization_engine = _engine(materialization_transport)
    materialization_engine.create_closed_probe_container(IMAGE_ID)
    with pytest.raises(LocalDockerEngineError, match="isolation changed"):
        materialization_engine.inspect_closed_probe_container(
            CONTAINER_ID, expected_image_id=IMAGE_ID
        )


def test_fresh_engine_cleanup_removes_only_its_synthetic_child_and_is_idempotent():
    _synthetic_surface()
    transport = FakeTransport(
        [
            _response(200, _version()),
            _response(200, _info()),
            _response(201, {"Id": CONTAINER_ID}),
            _response(200, _synthetic_container_inspect()),
            _response(204),
        ]
    )
    engine = _engine(transport)
    engine.create_closed_synthetic_probe_container(IMAGE_ID)

    engine.cleanup_owned_resources()
    calls_after_first_cleanup = len(transport.calls)
    engine.cleanup_owned_resources()

    assert len(transport.calls) == calls_after_first_cleanup
    assert transport.calls[-1]["method"] == "DELETE"
    assert transport.calls[-1]["path"].endswith(f"/{CONTAINER_ID}?force=1&v=1")
    _assert_no_broad_or_image_operations(transport)


def test_lost_synthetic_create_reply_is_reconciled_by_exact_name_nonce_and_profile(
    monkeypatch,
):
    _synthetic_surface()
    from human_feedback.adapters import local_docker_engine as module

    token = "e" * 32
    monkeypatch.setattr(module.secrets, "token_hex", lambda _size: token)
    transport = FakeTransport(
        [
            _response(200, _version()),
            _response(200, _info()),
            TimeoutError("reply lost"),
            _response(200, _synthetic_container_inspect()),
            _response(200, _synthetic_container_inspect()),
            _response(204),
        ]
    )
    engine = _engine(transport)
    with pytest.raises(TimeoutError, match="reply lost"):
        engine.create_closed_synthetic_probe_container(IMAGE_ID)

    engine.cleanup_owned_resources()

    reconcile = transport.calls[3]
    assert reconcile["method"] == "GET"
    assert reconcile["path"].endswith("/containers/aai-laya-synthetic-probe-" + token + "/json")
    _assert_no_broad_or_image_operations(transport)


def test_cleanup_never_adopts_a_lost_synthetic_create_with_wrong_nonce(monkeypatch):
    _synthetic_surface()
    from human_feedback.adapters import local_docker_engine as module
    from human_feedback.adapters.local_docker_engine import LocalDockerEngineError

    monkeypatch.setattr(module.secrets, "token_hex", lambda _size: "f" * 32)
    transport = FakeTransport(
        [
            _response(200, _version()),
            _response(200, _info()),
            TimeoutError("reply lost"),
            _response(200, _synthetic_container_inspect(nonce="1" * 32)),
        ]
    )
    engine = _engine(transport)
    with pytest.raises(TimeoutError, match="reply lost"):
        engine.create_closed_synthetic_probe_container(IMAGE_ID)

    with pytest.raises(LocalDockerEngineError, match="cleanup is incomplete"):
        engine.cleanup_owned_resources()

    assert all(call["method"] != "DELETE" for call in transport.calls)
    _assert_no_broad_or_image_operations(transport)
