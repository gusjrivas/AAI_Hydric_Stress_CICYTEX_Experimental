from __future__ import annotations

import http.client
import inspect
import io
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


class _Headers:
    def __init__(self, pairs):
        self.pairs = tuple(pairs)

    def get_all(self, name, default=None):
        values = [value for key, value in self.pairs if key.lower() == name.lower()]
        return values or default

    def get(self, name, default=None):
        values = self.get_all(name)
        return default if values is None else ", ".join(values)


class _HijackResponse:
    def __init__(self, payload, *, status=101, headers=None, fragment=1):
        self.status = status
        self.headers = _Headers(
            headers
            or (
                ("Connection", "Upgrade"),
                ("Upgrade", "tcp"),
                ("Content-Type", "application/vnd.docker.multiplexed-stream"),
            )
        )
        self.payload = bytearray(payload)
        self.fragment = fragment

    def getheader(self, name, default=None):
        return self.headers.get(name, default)

    def read(self, size):
        count = min(size, self.fragment, len(self.payload))
        result = bytes(self.payload[:count])
        del self.payload[:count]
        return result

    read1 = read


class _HijackSocket:
    def __init__(self):
        self.shutdowns = []
        self.timeouts = []

    def shutdown(self, how):
        self.shutdowns.append(how)

    def settimeout(self, value):
        self.timeouts.append(value)


class _HijackConnection:
    instances = []
    response = None

    def __init__(self, timeout):
        self.timeout = timeout
        self.sock = _HijackSocket()
        self.request_call = None
        self.putrequest_call = None
        self.headers = []
        self.sent = []
        self.closed = False
        self.instances.append(self)

    def request(self, *args, **kwargs):
        self.request_call = (args, kwargs)

    def putrequest(self, *args, **kwargs):
        self.putrequest_call = (args, kwargs)

    def putheader(self, name, value):
        self.headers.append((name, value))

    def endheaders(self):
        pass

    def send(self, value):
        self.sent.append(bytes(value))

    def getresponse(self):
        return self.response

    def close(self):
        self.closed = True


def _frame(stream: int, payload: bytes) -> bytes:
    return bytes((stream, 0, 0, 0)) + len(payload).to_bytes(4, "big") + payload


def _hijack_transport(monkeypatch, response, *, expired=False):
    from human_feedback.adapters import local_docker_engine as module

    class Watchdog:
        def __init__(self, _connection, _deadline):
            self.expired = expired
            self.cancelled = False

        def cancel(self):
            self.cancelled = True

    _HijackConnection.instances.clear()
    _HijackConnection.response = response
    monkeypatch.setattr(module, "_UnixSocketHTTPConnection", _HijackConnection)
    monkeypatch.setattr(module, "_DeadlineWatchdog", Watchdog)
    return module, module._LocalUnixTransport()


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
        OFFLINE_PROBE_ARGUMENTS,
        OFFLINE_PROBE_ENVIRONMENT,
    )

    _engine, transport, _container_id = _created_engine()
    payload = transport.created_payload

    assert payload["Entrypoint"] == ["/opt/laya-runtime/.venv/bin/python"]
    assert payload["Cmd"] == list(OFFLINE_PROBE_ARGUMENTS)
    assert payload["Env"] == list(OFFLINE_PROBE_ENVIRONMENT)
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

    program = probe.OFFLINE_PROBE_ARGUMENTS[-1]
    assert "router.predict" in program
    assert any(
        expression in program
        for expression in ('result["usage"]', "result['usage']", 'result.get("usage")')
    )
    assert all(field in program for field in ("state_tokens", "state_tokens_dropped", "truncated"))
    assert "stdin.buffer.read" in program
    assert "65537" in program
    assert REQUEST not in tuple(
        value.encode("utf-8") if type(value) is str else value
        for value in probe.OFFLINE_PROBE_ARGUMENTS
    )


def test_attach_transport_upgrades_writes_eof_and_decodes_fragmented_frames(monkeypatch):
    stdout = b"canonical response"
    stderr = b"bounded warning"
    response = _HijackResponse(_frame(1, stdout) + _frame(2, stderr), fragment=1)
    module, transport = _hijack_transport(monkeypatch, response)
    path = f"/v1.44/containers/{CONTAINER_ID}/attach?" "stream=1&stdin=1&stdout=1&stderr=1"

    with transport.open_attach(
        path,
        stdin_limit=64 * 1024,
        stdout_limit=64 * 1024,
        stderr_limit=8 * 1024,
        timeout=300.0,
    ) as session:
        observed = session.exchange(REQUEST)

    connection = _HijackConnection.instances[0]
    if connection.request_call is not None:
        args, kwargs = connection.request_call
        assert args[:2] == ("POST", path)
        sent_headers = kwargs["headers"]
    else:
        assert connection.putrequest_call[0][:2] == ("POST", path)
        sent_headers = dict(connection.headers)
    normalized_headers = {key.lower(): value.lower() for key, value in sent_headers.items()}
    assert normalized_headers["connection"] == "upgrade"
    assert normalized_headers["upgrade"] == "tcp"
    assert b"".join(connection.sent) == REQUEST
    assert connection.sock.shutdowns == [module.socket.SHUT_WR]
    assert observed == (stdout, stderr)
    assert connection.closed is True


@pytest.mark.parametrize(
    ("status", "headers"),
    [
        (200, None),
        (101, (("Connection", "Upgrade"), ("Upgrade", "tcp"))),
        (
            101,
            (
                ("Connection", "Upgrade"),
                ("Upgrade", "tcp"),
                ("Upgrade", "websocket"),
                ("Content-Type", "application/vnd.docker.multiplexed-stream"),
            ),
        ),
        (
            101,
            (
                ("Connection", "Upgrade"),
                ("Connection", "keep-alive"),
                ("Upgrade", "tcp"),
                ("Content-Type", "application/vnd.docker.multiplexed-stream"),
            ),
        ),
    ],
)
def test_attach_transport_rejects_nonexact_upgrade_before_private_input(
    monkeypatch, status, headers
):
    response = _HijackResponse(b"", status=status, headers=headers)
    module, transport = _hijack_transport(monkeypatch, response)

    with pytest.raises(module.LocalDockerEngineError):
        transport.open_attach(
            f"/v1.44/containers/{CONTAINER_ID}/attach?" "stream=1&stdin=1&stdout=1&stderr=1",
            stdin_limit=64 * 1024,
            stdout_limit=64 * 1024,
            stderr_limit=8 * 1024,
            timeout=300.0,
        )

    connection = _HijackConnection.instances[0]
    assert connection.sent == []
    assert connection.closed is True


@pytest.mark.parametrize(
    "payload",
    [
        b"\x01\x00",
        _frame(3, b"invalid stream"),
        bytes((1, 0, 0, 0)) + (64 * 1024 + 1).to_bytes(4, "big"),
        bytes((1, 0, 0, 0)) + (4).to_bytes(4, "big") + b"cut",
    ],
    ids=("truncated-header", "invalid-stream", "oversized-frame", "truncated-payload"),
)
def test_attach_transport_closes_on_malformed_or_oversized_frames(monkeypatch, payload):
    response = _HijackResponse(payload, fragment=2)
    module, transport = _hijack_transport(monkeypatch, response)

    with pytest.raises(module.LocalDockerEngineError):
        with transport.open_attach(
            f"/v1.44/containers/{CONTAINER_ID}/attach?" "stream=1&stdin=1&stdout=1&stderr=1",
            stdin_limit=64 * 1024,
            stdout_limit=64 * 1024,
            stderr_limit=8 * 1024,
            timeout=300.0,
        ) as session:
            session.exchange(REQUEST)

    connection = _HijackConnection.instances[0]
    assert connection.closed is True


def test_attach_transport_deadline_closes_without_writing_private_input(monkeypatch):
    response = _HijackResponse(_frame(1, RESPONSE))
    module, transport = _hijack_transport(monkeypatch, response, expired=True)

    with pytest.raises(module.LocalDockerEngineError):
        with transport.open_attach(
            f"/v1.44/containers/{CONTAINER_ID}/attach?" "stream=1&stdin=1&stdout=1&stderr=1",
            stdin_limit=64 * 1024,
            stdout_limit=64 * 1024,
            stderr_limit=8 * 1024,
            timeout=300.0,
        ) as session:
            session.exchange(REQUEST)

    connection = _HijackConnection.instances[0]
    assert connection.sent == []
    assert connection.closed is True


def test_attach_transport_reads_http_101_buffered_readahead_instead_of_empty_body(
    monkeypatch,
):
    from human_feedback.adapters import local_docker_engine as module

    frame = _frame(1, RESPONSE)
    raw_response = (
        b"HTTP/1.1 101 UPGRADED\r\n"
        b"Connection: Upgrade\r\n"
        b"Upgrade: tcp\r\n"
        b"Content-Type: application/vnd.docker.multiplexed-stream\r\n"
        b"\r\n" + frame
    )

    class Socket:
        def __init__(self):
            self.stream = io.BytesIO(raw_response)
            self.shutdowns = []

        def makefile(self, *_args, **_kwargs):
            return self.stream

        def settimeout(self, _value):
            pass

        def shutdown(self, how):
            self.shutdowns.append(how)

    class Connection:
        instance = None

        def __init__(self, timeout):
            self.timeout = timeout
            self.sock = Socket()
            self.sent = []
            self.closed = False
            Connection.instance = self

        def request(self, *_args, **_kwargs):
            pass

        def getresponse(self):
            response = http.client.HTTPResponse(self.sock)
            response.begin()
            assert response.status == 101
            assert response.length == 0  # read() would close before response.fp frames.
            return response

        def send(self, value):
            self.sent.append(bytes(value))

        def close(self):
            self.closed = True

    class Watchdog:
        expired = False

        def __init__(self, _connection, _deadline):
            pass

        def cancel(self):
            pass

    monkeypatch.setattr(module, "_UnixSocketHTTPConnection", Connection)
    monkeypatch.setattr(module, "_DeadlineWatchdog", Watchdog)
    path = f"/v1.44/containers/{CONTAINER_ID}/attach?" "stream=1&stdin=1&stdout=1&stderr=1"

    with module._LocalUnixTransport().open_attach(
        path,
        stdin_limit=64 * 1024,
        stdout_limit=64 * 1024,
        stderr_limit=8 * 1024,
        timeout=300.0,
    ) as session:
        stdout, stderr = session.exchange(REQUEST)

    assert stdout == RESPONSE
    assert stderr == b""
    assert b"".join(Connection.instance.sent) == REQUEST
    assert Connection.instance.sock.shutdowns == [module.socket.SHUT_WR]
    assert Connection.instance.closed is True
