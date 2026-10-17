from __future__ import annotations

import inspect
import json

import pytest

IMAGE_ID = "sha256:" + "a" * 64
CONTAINER_ID = "b" * 64
NONCE = "c" * 32
REQUEST = (
    b'{"items":[{"comment":"private observation","token":"'
    + b"d" * 64
    + b'"}],"schema_version":"laya-gold-blind-offline-request-v2"}'
)
RESPONSE = b'{"predictions":[],"schema_version":"laya-gold-blind-offline-response-v2"}'


def _response(status: int, value: object | None = None):
    from human_feedback.adapters.local_docker_engine import DockerHttpResponse

    body = b"" if value is None else json.dumps(value, separators=(",", ":")).encode()
    return DockerHttpResponse(status=status, body=body)


def _fresh_state() -> dict[str, object]:
    return {
        "Status": "created",
        "Running": False,
        "Paused": False,
        "Restarting": False,
        "OOMKilled": False,
        "Dead": False,
        "StartedAt": "0001-01-01T00:00:00Z",
        "FinishedAt": "0001-01-01T00:00:00Z",
    }


class _AttachSession:
    def __init__(self, events, *, stdout=RESPONSE, stderr=b"", error=None):
        self.events = events
        self.stdout = stdout
        self.stderr = stderr
        self.error = error
        self.closed = False

    def __enter__(self):
        self.events.append("attach-enter")
        return self

    def __exit__(self, *_args):
        self.closed = True
        self.events.append("attach-close")

    def exchange(self, canonical_request: bytes):
        self.events.append(("exchange", canonical_request))
        if self.error is not None:
            raise self.error
        return self.stdout, self.stderr


class _OfflineTransport:
    def __init__(self, *, attach=None, attach_error=None):
        self.events = []
        self.created_payload = None
        self.started = False
        self.waited = False
        self.attach = attach or _AttachSession(self.events)
        self.attach_error = attach_error

    def request(self, method, path, *, body=None, headers=None, response_limit, timeout):
        del headers, response_limit, timeout
        self.events.append((method, path))
        if path == "/version":
            return _response(
                200,
                {
                    "ApiVersion": "1.47",
                    "MinAPIVersion": "1.24",
                    "Os": "linux",
                    "Arch": "amd64",
                },
            )
        if path == "/v1.44/info":
            return _response(
                200,
                {
                    "OSType": "linux",
                    "Architecture": "x86_64",
                    "SecurityOptions": ["name=seccomp,profile=builtin"],
                },
            )
        if path.startswith("/v1.44/containers/create?name="):
            self.created_payload = json.loads(body)
            return _response(201, {"Id": CONTAINER_ID, "Warnings": []})
        if path == f"/v1.44/containers/{CONTAINER_ID}/json":
            return _response(200, self.inspection())
        if path == f"/v1.44/containers/{CONTAINER_ID}/start":
            self.started = True
            self.events.append("start")
            return _response(204)
        if path == f"/v1.44/containers/{CONTAINER_ID}/wait?condition=not-running":
            self.waited = True
            self.events.append("wait")
            return _response(200, {"StatusCode": 0, "Error": None})
        pytest.fail(f"unexpected Docker request: {method} {path}")

    def open_attach(self, path, **bounds):
        self.events.append(("open-attach", path, bounds))
        if self.attach_error is not None:
            raise self.attach_error
        return self.attach

    def inspection(self):
        assert self.created_payload is not None
        config = {
            key: value
            for key, value in self.created_payload.items()
            if key not in {"HostConfig", "NetworkDisabled", "NetworkingConfig"}
        }
        state = _fresh_state()
        if self.waited:
            state.update(
                {
                    "Status": "exited",
                    "ExitCode": 0,
                    "StartedAt": "2026-10-17T00:00:00Z",
                    "FinishedAt": "2026-10-17T00:00:01Z",
                }
            )
        elif self.started:
            state.update({"Status": "running", "Running": True})
        return {
            "Id": CONTAINER_ID,
            "Config": config,
            "HostConfig": self.created_payload["HostConfig"],
            "Mounts": [],
            "NetworkSettings": {"Ports": {}, "Networks": {"none": {}}},
            "State": state,
        }


def _created_engine(*, transport=None):
    from human_feedback.adapters.local_docker_engine import LocalDockerEngine

    transport = transport or _OfflineTransport()
    engine = LocalDockerEngine(NONCE, _transport=transport)
    container_id = engine.create_closed_loso_offline_container(IMAGE_ID)
    engine.inspect_closed_loso_offline_container(container_id, expected_image_id=IMAGE_ID)
    return engine, transport, container_id


def test_offline_engine_surface_is_narrow_and_has_no_caller_selected_profile():
    from human_feedback.adapters.local_docker_engine import LocalDockerEngine

    assert tuple(
        inspect.signature(LocalDockerEngine.create_closed_loso_offline_container).parameters
    ) == ("self", "image_id")
    assert tuple(
        inspect.signature(LocalDockerEngine.inspect_closed_loso_offline_container).parameters
    ) == ("self", "container_id", "expected_image_id")
    assert tuple(inspect.signature(LocalDockerEngine.run_closed_loso_offline).parameters) == (
        "self",
        "container_id",
        "expected_image_id",
        "canonical_request",
    )


def test_offline_container_profile_is_fixed_closed_and_stdin_only():
    from human_feedback.adapters._laya_offline_probe import (
        LOSO_OFFLINE_ARGUMENTS,
        LOSO_OFFLINE_ENVIRONMENT,
    )

    _engine, transport, _container_id = _created_engine()
    payload = transport.created_payload

    assert payload["Entrypoint"] == ["/opt/laya-runtime/.venv/bin/python"]
    assert payload["Cmd"] == list(LOSO_OFFLINE_ARGUMENTS)
    assert payload["Env"] == list(LOSO_OFFLINE_ENVIRONMENT)
    assert payload["OpenStdin"] is True
    assert payload["StdinOnce"] is True
    assert payload["AttachStdin"] is True
    assert payload["AttachStdout"] is True
    assert payload["AttachStderr"] is True
    assert payload["Tty"] is False
    assert payload["NetworkDisabled"] is True
    host = payload["HostConfig"]
    assert host["ReadonlyRootfs"] is True
    assert host["NetworkMode"] == "none"
    assert host["CapDrop"] == ["ALL"]
    assert host["Privileged"] is False
    assert host["Binds"] == host["Mounts"] == host["Devices"] == []
    assert host["LogConfig"] == {"Type": "none", "Config": {}}


def test_offline_run_attaches_before_start_sends_one_bounded_request_and_waits():
    engine, transport, container_id = _created_engine()

    stdout = engine.run_closed_loso_offline(
        container_id,
        expected_image_id=IMAGE_ID,
        canonical_request=REQUEST,
    )

    assert stdout == RESPONSE and type(stdout) is bytes
    open_event = next(event for event in transport.events if event[0] == "open-attach")
    assert open_event[1] == (
        f"/v1.44/containers/{CONTAINER_ID}/attach?" "stream=1&stdin=1&stdout=1&stderr=1"
    )
    assert transport.events.index(open_event) < transport.events.index("start")
    assert transport.events.index("start") < transport.events.index(("exchange", REQUEST))
    assert transport.events.index(("exchange", REQUEST)) < transport.events.index("wait")
    assert transport.attach.closed is True


@pytest.mark.parametrize("invalid_kind", ["mutable", "empty", "oversized"])
def test_invalid_offline_stdin_fails_before_inspect_attach_or_start(invalid_kind):
    invalid = {
        "mutable": bytearray(REQUEST),
        "empty": b"",
        "oversized": b"x" * (64 * 1024 + 1),
    }[invalid_kind]
    engine, transport, container_id = _created_engine()
    before = tuple(transport.events)

    with pytest.raises(ValueError):
        engine.run_closed_loso_offline(
            container_id,
            expected_image_id=IMAGE_ID,
            canonical_request=invalid,
        )

    assert tuple(transport.events) == before


def test_attach_failure_never_starts_and_stderr_is_fail_closed():
    from human_feedback.adapters.local_docker_engine import LocalDockerEngineError

    transport = _OfflineTransport(attach_error=LocalDockerEngineError("attach refused"))
    engine, transport, container_id = _created_engine(transport=transport)
    with pytest.raises(LocalDockerEngineError):
        engine.run_closed_loso_offline(
            container_id,
            expected_image_id=IMAGE_ID,
            canonical_request=REQUEST,
        )
    assert "start" not in transport.events

    warning_attach = _AttachSession([], stderr=b"private warning")
    warning_transport = _OfflineTransport(attach=warning_attach)
    warning_attach.events = warning_transport.events
    engine, warning_transport, container_id = _created_engine(transport=warning_transport)
    with pytest.raises(LocalDockerEngineError):
        engine.run_closed_loso_offline(
            container_id,
            expected_image_id=IMAGE_ID,
            canonical_request=REQUEST,
        )
    assert warning_attach.closed is True


def test_offline_profile_cannot_use_legacy_probe_operations():
    from human_feedback.adapters.local_docker_engine import LocalDockerEngineError

    engine, transport, container_id = _created_engine()
    before = tuple(transport.events)

    for operation in (
        lambda: engine.start_probe(container_id),
        lambda: engine.export_stopped_container_stream(container_id),
        lambda: engine.run_closed_synthetic_probe(
            container_id,
            expected_image_id=IMAGE_ID,
        ),
    ):
        with pytest.raises(LocalDockerEngineError):
            operation()
    assert tuple(transport.events) == before


def test_fixed_program_projects_pinned_laya_usage_without_host_estimation():
    from human_feedback.adapters import _laya_offline_probe as probe

    program = probe.LOSO_OFFLINE_ARGUMENTS[-1]
    assert "router.predict" in program
    assert 'result["usage"]' in program or "result['usage']" in program
    assert all(field in program for field in ("state_tokens", "state_tokens_dropped", "truncated"))
    assert "stdin.buffer.read" in program
    assert "65537" in program
    assert REQUEST not in tuple(
        value.encode("utf-8") if type(value) is str else value
        for value in probe.LOSO_OFFLINE_ARGUMENTS
    )
