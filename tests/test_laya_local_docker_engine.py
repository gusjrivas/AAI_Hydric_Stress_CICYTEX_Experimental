from __future__ import annotations

import inspect
import json
import urllib.parse

import pytest

IMAGE_ID = "sha256:" + "a" * 64
CONTAINER_ID = "b" * 64
NONCE = "c" * 32


class FakeStream:
    def __init__(self, chunks):
        self.chunks = tuple(chunks)
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()

    def __iter__(self):
        yield from self.chunks

    def close(self):
        self.closed = True


class FakeTransport:
    def __init__(self, responses, *, upload_responses=(), streams=()):
        self.responses = list(responses)
        self.upload_responses = list(upload_responses)
        self.streams = list(streams)
        self.calls = []

    def request(self, method, path, *, body=None, headers=None, response_limit, timeout):
        self.calls.append(
            {
                "method": method,
                "path": path,
                "body": body,
                "headers": headers,
                "response_limit": response_limit,
                "timeout": timeout,
            }
        )
        if not self.responses:
            pytest.fail(f"unexpected Docker request: {method} {path}")
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    def upload_producer(self, path, producer, **kwargs):
        class Writer:
            def __init__(self):
                self.payload = bytearray()

            def write(self, buffer):
                count = min(len(buffer), 3)
                self.payload.extend(buffer[:count])
                return count

        writer = Writer()
        reported = producer(writer)
        self.calls.append(
            {
                "method": "UPLOAD",
                "path": path,
                "payload": bytes(writer.payload),
                "reported": reported,
                **kwargs,
            }
        )
        if not self.upload_responses:
            pytest.fail(f"unexpected Docker upload: {path}")
        response = self.upload_responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    def open_stream(self, path, **kwargs):
        self.calls.append({"method": "STREAM", "path": path, **kwargs})
        if not self.streams:
            pytest.fail(f"unexpected Docker stream: {path}")
        return self.streams.pop(0)


def _response(status: int, value: object | None = None):
    from human_feedback.adapters.local_docker_engine import DockerHttpResponse

    body = b"" if value is None else json.dumps(value, separators=(",", ":")).encode("utf-8")
    return DockerHttpResponse(status=status, body=body)


def _version():
    return {
        "ApiVersion": "1.47",
        "MinAPIVersion": "1.24",
        "Os": "linux",
        "Arch": "amd64",
    }


def _info():
    return {
        "OSType": "linux",
        "Architecture": "x86_64",
        "SecurityOptions": ["name=seccomp,profile=builtin", "name=cgroupns"],
    }


def _container_inspect(*, nonce: str = NONCE, readonly: bool = True):
    from human_feedback.adapters.local_docker_engine import PROBE_ARGUMENTS, PROBE_ENVIRONMENT

    return {
        "Id": CONTAINER_ID,
        "Config": {
            "Image": IMAGE_ID,
            "User": "65532:65532",
            "WorkingDir": "/opt/laya-runtime",
            "Entrypoint": ["/opt/laya-runtime/.venv/bin/python"],
            "Cmd": list(PROBE_ARGUMENTS),
            "Env": list(PROBE_ENVIRONMENT),
            "Labels": {"org.aai-hydric.runtime.owner-nonce": nonce},
        },
        "HostConfig": {
            "ReadonlyRootfs": readonly,
            "NetworkMode": "none",
            "CapDrop": ["ALL"],
            "SecurityOpt": ["no-new-privileges", "seccomp=builtin"],
            "Privileged": False,
            "Binds": [],
            "Mounts": [],
            "Devices": [],
            "PortBindings": {},
            "PublishAllPorts": False,
            "AutoRemove": False,
            "OomKillDisable": False,
            "PidMode": "",
            "UTSMode": "",
            "UsernsMode": "",
            "CgroupnsMode": "private",
            "VolumesFrom": [],
            "Links": [],
            "ExtraHosts": [],
            "Dns": [],
            "DnsSearch": [],
            "DnsOptions": [],
            "PidsLimit": 64,
            "Memory": 4 * 1024**3,
            "MemorySwap": 4 * 1024**3,
            "NanoCpus": 2_000_000_000,
            "Ulimits": [
                {"Name": "nofile", "Soft": 256, "Hard": 256},
                {"Name": "core", "Soft": 0, "Hard": 0},
            ],
            "Tmpfs": {"/tmp": "rw,nosuid,nodev,noexec,size=67108864,mode=1777"},
            "LogConfig": {
                "Type": "json-file",
                "Config": {"max-size": "64k", "max-file": "1"},
            },
            "IpcMode": "private",
        },
        "NetworkSettings": {"Ports": {}, "Networks": {}},
        "Mounts": [],
        "State": {"Running": False},
    }


def _image_inspect(*, nonce: str = NONCE):
    from human_feedback.adapters._laya_runtime_probe import IMAGE_ENVIRONMENT

    return {
        "Id": IMAGE_ID,
        "Config": {
            "User": "65532:65532",
            "WorkingDir": "/opt/laya-runtime",
            "Entrypoint": ["laya-serve"],
            "Env": list(IMAGE_ENVIRONMENT),
            "Labels": {"org.aai-hydric.runtime.owner-nonce": nonce},
        },
    }


def test_closed_probe_bounds_daemon_disk_logs_and_rejects_unbounded_logging():
    from human_feedback.adapters import local_docker_engine as module

    expected = {"Type": "json-file", "Config": {"max-size": "64k", "max-file": "1"}}
    assert module._closed_probe_payload(IMAGE_ID, NONCE)["HostConfig"].get("LogConfig") == expected
    inspected = _container_inspect()
    inspected["HostConfig"]["LogConfig"] = {"Type": "json-file", "Config": {}}
    assert not module._matches_closed_probe(
        inspected, image_id=IMAGE_ID, container_id=CONTAINER_ID, nonce=NONCE
    )


def _log_frame(stream: int, payload: bytes) -> bytes:
    return bytes((stream, 0, 0, 0)) + len(payload).to_bytes(4, "big") + payload


def _probe_observation(**changes) -> bytes:
    value = {
        "device": "cpu",
        "laya": "0.4.2",
        "loaded": "multilingual",
        "model_eval": True,
        "python": "3.11.10",
        "schema_version": "laya-local-load-probe-v1",
    }
    value.update(changes)
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode() + b"\n"


def _write_all(payload: bytes):
    def produce(writer):
        offset = 0
        while offset < len(payload):
            offset += writer.write(payload[offset:])
        return offset

    return produce


def _engine(transport):
    from human_feedback.adapters.local_docker_engine import LocalDockerEngine

    return LocalDockerEngine(ownership_nonce=NONCE, _transport=transport)


def test_public_surface_does_not_accept_endpoint_command_or_host_paths():
    from human_feedback.adapters import local_docker_engine as module

    assert module.DOCKER_SOCKET_PATH == "/var/run/docker.sock"
    assert tuple(inspect.signature(module.LocalDockerEngine).parameters) == (
        "ownership_nonce",
        "_transport",
    )
    assert tuple(
        inspect.signature(module.LocalDockerEngine.create_closed_probe_container).parameters
    ) == (
        "self",
        "image_id",
    )
    assert "subprocess" not in module.__dict__


def test_unix_transport_bounds_control_responses_and_rejects_nonlocal_request_shapes(
    monkeypatch,
):
    from human_feedback.adapters import local_docker_engine as module

    class Response:
        status = 200

        def __init__(self, payload):
            self.payload = payload

        def read(self, _size):
            payload, self.payload = self.payload, b""
            return payload

    class Connection:
        instances = []

        def __init__(self, timeout):
            self.timeout = timeout
            self.request_args = None
            self.response = Response(b"okay")
            self.closed = False
            self.instances.append(self)

        def request(self, *args, **kwargs):
            self.request_args = (args, kwargs)

        def getresponse(self):
            return self.response

        def close(self):
            self.closed = True

    monkeypatch.setattr(module, "_UnixSocketHTTPConnection", Connection)
    transport = module._LocalUnixTransport()

    response = transport.request("GET", "/version", response_limit=4, timeout=1.0, headers=None)

    assert response == module.DockerHttpResponse(status=200, body=b"okay")
    assert Connection.instances[0].request_args[0] == ("GET", "/version")
    assert Connection.instances[0].closed is True

    Connection.instances.clear()
    overflow = Connection(1.0)
    overflow.response = Response(b"12345")
    monkeypatch.setattr(module, "_UnixSocketHTTPConnection", lambda _timeout: overflow)
    with pytest.raises(module.LocalDockerEngineError):
        transport.request("GET", "/version", response_limit=4, timeout=1.0)
    assert overflow.closed is True

    with pytest.raises(module.LocalDockerEngineError):
        transport.request("GET", "http://remote/version", response_limit=4, timeout=1.0)


def test_chunked_upload_is_push_streamed_with_short_writes_and_exact_count(monkeypatch):
    from human_feedback.adapters import local_docker_engine as module

    class Response:
        status = 200

        def __init__(self):
            self.payload = b'{"status":"' + IMAGE_ID.encode() + b'"}\n'

        def read(self, size):
            payload, self.payload = self.payload[:size], self.payload[size:]
            return payload

    class Connection:
        instance = None

        def __init__(self, timeout):
            self.timeout = timeout
            self.events = []
            self.closed = False
            self.response = Response()
            Connection.instance = self

        def putrequest(self, method, path):
            self.events.append(("request", method, path))

        def putheader(self, name, value):
            self.events.append(("header", name, value))

        def endheaders(self):
            self.events.append(("headers-end",))

        def send(self, payload):
            self.events.append(("send", bytes(payload)))

        def getresponse(self):
            return self.response

        def close(self):
            self.closed = True

    monkeypatch.setattr(module, "_UnixSocketHTTPConnection", Connection)
    monkeypatch.setattr(module, "_ARCHIVE_CHUNK_LIMIT", 3)
    transport = module._LocalUnixTransport()

    response = transport.upload_producer(
        "/v1.44/images/create?fromSrc=-",
        _write_all(b"abcdefg"),
        total_limit=module._ARCHIVE_BYTES_LIMIT,
        response_limit=module._CONTROL_RESPONSE_LIMIT,
        timeout=1.0,
        headers={"Content-Type": "application/x-tar"},
    )

    assert response.status == 200
    sends = [event[1] for event in Connection.instance.events if event[0] == "send"]
    assert sends == [
        b"3\r\n",
        b"abc",
        b"\r\n",
        b"3\r\n",
        b"def",
        b"\r\n",
        b"1\r\n",
        b"g",
        b"\r\n",
        b"0\r\n\r\n",
    ]
    assert Connection.instance.closed is True


def test_chunked_upload_rejects_producer_count_mismatch_without_finalizing(monkeypatch):
    from human_feedback.adapters import local_docker_engine as module

    class Connection:
        instance = None

        def __init__(self, _timeout):
            self.sent = []
            self.closed = False
            Connection.instance = self

        def putrequest(self, *_args):
            pass

        def putheader(self, *_args):
            pass

        def endheaders(self):
            pass

        def send(self, payload):
            self.sent.append(bytes(payload))

        def close(self):
            self.closed = True

    monkeypatch.setattr(module, "_UnixSocketHTTPConnection", Connection)
    transport = module._LocalUnixTransport()

    def wrong_count(writer):
        assert writer.write(b"tar") == 3
        return 2

    with pytest.raises(module.LocalDockerEngineError, match="count changed"):
        transport.upload_producer(
            "/v1.44/images/create?fromSrc=-",
            wrong_count,
            total_limit=module._ARCHIVE_BYTES_LIMIT,
            response_limit=module._CONTROL_RESPONSE_LIMIT,
            timeout=1.0,
            headers={"Content-Type": "application/x-tar"},
        )
    assert b"0\r\n\r\n" not in Connection.instance.sent
    assert Connection.instance.closed is True


def test_create_probe_negotiates_pinned_local_linux_daemon_and_uses_closed_payload(
    monkeypatch,
):
    from human_feedback.adapters import local_docker_engine as module

    monkeypatch.setattr(module.secrets, "token_hex", lambda _size: "d" * 32)
    transport = FakeTransport(
        [
            _response(200, _version()),
            _response(200, _info()),
            _response(201, {"Id": CONTAINER_ID, "Warnings": []}),
        ]
    )
    engine = _engine(transport)

    assert engine.create_closed_probe_container(IMAGE_ID) == CONTAINER_ID

    assert [(call["method"], call["path"]) for call in transport.calls] == [
        ("GET", "/version"),
        ("GET", "/v1.44/info"),
        ("POST", "/v1.44/containers/create?name=aai-laya-probe-" + "d" * 32),
    ]
    payload = json.loads(transport.calls[-1]["body"])
    assert payload == module._closed_probe_payload(IMAGE_ID, NONCE)
    assert payload["Entrypoint"] == ["/opt/laya-runtime/.venv/bin/python"]
    assert tuple(payload["Cmd"]) == module.PROBE_ARGUMENTS
    assert payload["HostConfig"]["NetworkMode"] == "none"
    assert payload["HostConfig"]["ReadonlyRootfs"] is True
    assert payload["HostConfig"]["CapDrop"] == ["ALL"]
    assert payload["HostConfig"]["Binds"] == []
    assert payload["HostConfig"]["Mounts"] == []
    assert payload["HostConfig"]["Devices"] == []
    assert payload["HostConfig"]["PortBindings"] == {}
    assert payload["NetworkingConfig"] == {"EndpointsConfig": {}}
    assert b"/var/run/docker.sock" not in transport.calls[-1]["body"]


def test_fixed_probe_loads_only_pinned_offline_model_without_inference():
    from human_feedback.adapters import _laya_runtime_probe as probe

    program = probe.PROBE_ARGUMENTS[-1]
    environment = set(probe.PROBE_ENVIRONMENT)
    assert probe.PROBE_ARGUMENTS[:2] == ("-I", "-B")
    assert "build_router()" in program
    assert 'router.load("multilingual")' in program
    assert 'version("laya") == "0.4.2"' in program
    assert "sys.version_info[:3] == (3, 11, 10)" in program
    assert "agent.model.training is False" in program
    assert not any(token in program for token in (".forward(", ".encode(", ".predict("))
    assert "HF_HUB_OFFLINE=1" in environment
    assert "LAYA_DEVICE=cpu" in environment
    assert "NUM_THREADS=2" in environment
    assert len(probe.CHECKPOINT_DIGESTS) == 5
    assert all(len(digest) == 64 for digest in probe.CHECKPOINT_DIGESTS.values())


def test_import_streams_archive_and_registers_only_exact_inspected_owned_image():
    from human_feedback.adapters import local_docker_engine as module

    transport = FakeTransport(
        [_response(200, _version()), _response(200, _info()), _response(200, _image_inspect())],
        upload_responses=[_response(200, {"status": IMAGE_ID})],
    )
    engine = _engine(transport)

    assert engine.import_normalized_image(_write_all(b"normalized-tar")) == IMAGE_ID

    upload = next(call for call in transport.calls if call["method"] == "UPLOAD")
    assert upload["payload"] == b"normalized-tar"
    assert upload["reported"] == len(b"normalized-tar")
    assert upload["headers"] == {"Content-Type": "application/x-tar"}
    query = urllib.parse.parse_qs(urllib.parse.urlsplit(upload["path"]).query)
    assert query["fromSrc"] == ["-"]
    assert query["repo"] == ["aai-laya-runtime-" + NONCE]
    assert query["tag"] == ["materialized"]
    assert query["changes"] == list(module._image_changes(NONCE))


def test_import_does_not_register_image_when_daemon_configuration_differs():
    from human_feedback.adapters.local_docker_engine import LocalDockerEngineError

    transport = FakeTransport(
        [
            _response(200, _version()),
            _response(200, _info()),
            _response(200, _image_inspect(nonce="d" * 32)),
            _response(200, _image_inspect(nonce="d" * 32)),
        ],
        upload_responses=[_response(200, {"status": IMAGE_ID})],
    )
    engine = _engine(transport)

    with pytest.raises(LocalDockerEngineError, match="configuration changed"):
        engine.import_normalized_image(_write_all(b"normalized-tar"))
    with pytest.raises(LocalDockerEngineError, match="cleanup is incomplete"):
        engine.cleanup_owned_resources()
    assert engine._owned_images == {IMAGE_ID}
    assert all(call["method"] != "DELETE" for call in transport.calls)


def test_import_inspect_failure_leaves_provisional_id_for_retry_cleanup():
    from human_feedback.adapters.local_docker_engine import LocalDockerEngineError

    transport = FakeTransport(
        [
            _response(200, _version()),
            _response(200, _info()),
            _response(500),
            _response(200, _image_inspect()),
            _response(200),
        ],
        upload_responses=[_response(200, {"status": IMAGE_ID})],
    )
    engine = _engine(transport)

    with pytest.raises(LocalDockerEngineError):
        engine.import_normalized_image(_write_all(b"normalized-tar"))
    engine.cleanup_owned_resources()
    assert transport.calls[-1]["path"] == f"/v1.44/images/{IMAGE_ID}?force=0&noprune=1"
    assert engine.cleanup_owned_resources() is None


def test_lost_import_response_reconciles_only_exact_reference_then_cleans_up():
    from human_feedback.adapters.local_docker_engine import LocalDockerEngineError

    lost = LocalDockerEngineError("response lost")
    transport = FakeTransport(
        [
            _response(200, _version()),
            _response(200, _info()),
            _response(200, _image_inspect()),
            _response(200, _image_inspect()),
            _response(200),
        ],
        upload_responses=[lost],
    )
    engine = _engine(transport)

    with pytest.raises(LocalDockerEngineError, match="response lost"):
        engine.import_normalized_image(_write_all(b"normalized-tar"))
    engine.cleanup_owned_resources()

    reconciled = transport.calls[-3]
    assert reconciled["method"] == "GET"
    assert reconciled["path"] == (
        "/v1.44/images/"
        + urllib.parse.quote("aai-laya-runtime-" + NONCE + ":materialized", safe="")
        + "/json"
    )
    assert all("/images/json" not in call["path"] for call in transport.calls)


@pytest.mark.parametrize(
    "version,info",
    [
        ({**_version(), "Os": "windows"}, _info()),
        ({**_version(), "Arch": "arm64"}, _info()),
        ({**_version(), "ApiVersion": "1.43"}, _info()),
        (_version(), {**_info(), "SecurityOptions": ["name=seccomp,profile=unconfined"]}),
    ],
)
def test_create_probe_rejects_incompatible_or_unconfined_daemon_before_mutation(version, info):
    from human_feedback.adapters.local_docker_engine import LocalDockerEngineError

    transport = FakeTransport([_response(200, version), _response(200, info)])
    engine = _engine(transport)

    with pytest.raises(LocalDockerEngineError):
        engine.create_closed_probe_container(IMAGE_ID)

    assert all(call["method"] == "GET" for call in transport.calls)


def test_inspect_requires_exact_closed_configuration_before_probe_can_start():
    from human_feedback.adapters.local_docker_engine import LocalDockerEngineError

    transport = FakeTransport(
        [_response(200, _version()), _response(200, _info()), _response(200, _container_inspect())]
    )
    engine = _engine(transport)

    inspected = engine.inspect_closed_probe_container(CONTAINER_ID, expected_image_id=IMAGE_ID)

    assert inspected["Id"] == CONTAINER_ID

    bad = _container_inspect(readonly=False)
    failing = _engine(
        FakeTransport([_response(200, _version()), _response(200, _info()), _response(200, bad)])
    )
    with pytest.raises(LocalDockerEngineError):
        failing.inspect_closed_probe_container(CONTAINER_ID, expected_image_id=IMAGE_ID)


def test_export_requires_owned_closed_inspected_stopped_probe_and_closes_stream(monkeypatch):
    from human_feedback.adapters import local_docker_engine as module

    monkeypatch.setattr(module.secrets, "token_hex", lambda _size: "d" * 32)
    stream = FakeStream([b"one", b"two"])
    transport = FakeTransport(
        [
            _response(200, _version()),
            _response(200, _info()),
            _response(201, {"Id": CONTAINER_ID, "Warnings": []}),
            _response(200, _container_inspect()),
            _response(200, _container_inspect()),
        ],
        streams=[stream],
    )
    engine = _engine(transport)
    engine.create_closed_probe_container(IMAGE_ID)
    engine.inspect_closed_probe_container(CONTAINER_ID, expected_image_id=IMAGE_ID)

    with engine.export_stopped_container_stream(CONTAINER_ID) as chunks:
        assert tuple(chunks) == (b"one", b"two")

    assert stream.closed is True
    export = transport.calls[-1]
    assert export == {
        "method": "STREAM",
        "path": f"/v1.44/containers/{CONTAINER_ID}/export",
        "byte_limit": module._ARCHIVE_BYTES_LIMIT,
        "timeout": module._ARCHIVE_TIMEOUT_SECONDS,
    }


def test_export_and_start_reject_before_owned_closed_inspection(monkeypatch):
    from human_feedback.adapters import local_docker_engine as module
    from human_feedback.adapters.local_docker_engine import LocalDockerEngineError

    monkeypatch.setattr(module.secrets, "token_hex", lambda _size: "d" * 32)
    transport = FakeTransport(
        [
            _response(200, _version()),
            _response(200, _info()),
            _response(201, {"Id": CONTAINER_ID, "Warnings": []}),
        ]
    )
    engine = _engine(transport)
    engine.create_closed_probe_container(IMAGE_ID)

    with pytest.raises(LocalDockerEngineError, match="not closed-inspected"):
        engine.export_stopped_container_stream(CONTAINER_ID)
    with pytest.raises(LocalDockerEngineError, match="not closed-inspected"):
        engine.start_probe(CONTAINER_ID)
    assert len(transport.calls) == 3


def test_run_closed_probe_reinspects_starts_waits_and_returns_bounded_logs(monkeypatch):
    from human_feedback.adapters import local_docker_engine as module

    monkeypatch.setattr(module.secrets, "token_hex", lambda _size: "d" * 32)
    observation = _probe_observation()
    framed = _log_frame(1, observation) + _log_frame(2, b"bounded warning\n")
    transport = FakeTransport(
        [
            _response(200, _version()),
            _response(200, _info()),
            _response(201, {"Id": CONTAINER_ID, "Warnings": []}),
            _response(200, _container_inspect()),
            _response(200, _container_inspect()),
            _response(204),
            _response(200, {"StatusCode": 0, "Error": None}),
            module.DockerHttpResponse(status=200, body=framed),
        ]
    )
    engine = _engine(transport)
    engine.create_closed_probe_container(IMAGE_ID)

    assert engine.run_closed_probe(CONTAINER_ID, expected_image_id=IMAGE_ID) == (
        observation,
        b"bounded warning\n",
    )
    assert [(call["method"], call["path"]) for call in transport.calls[-5:]] == [
        ("GET", f"/v1.44/containers/{CONTAINER_ID}/json"),
        ("GET", f"/v1.44/containers/{CONTAINER_ID}/json"),
        ("POST", f"/v1.44/containers/{CONTAINER_ID}/start"),
        ("POST", f"/v1.44/containers/{CONTAINER_ID}/wait?condition=not-running"),
        (
            "GET",
            f"/v1.44/containers/{CONTAINER_ID}/logs?stdout=1&stderr=1&timestamps=0&follow=0",
        ),
    ]
    assert transport.calls[-2]["timeout"] == 300.0


@pytest.mark.parametrize(
    "wait_value",
    [
        {"StatusCode": 9, "Error": {"Message": "failed"}},
        {"StatusCode": 137, "Error": {"Message": "OOMKilled"}},
    ],
)
def test_probe_nonzero_or_oom_exit_and_malformed_logs_fail_closed(monkeypatch, wait_value):
    from human_feedback.adapters import local_docker_engine as module
    from human_feedback.adapters.local_docker_engine import LocalDockerEngineError

    monkeypatch.setattr(module.secrets, "token_hex", lambda _size: "d" * 32)
    responses = [
        _response(200, _version()),
        _response(200, _info()),
        _response(201, {"Id": CONTAINER_ID, "Warnings": []}),
        _response(200, _container_inspect()),
        _response(200, _container_inspect()),
        _response(204),
        _response(200, wait_value),
    ]
    engine = _engine(FakeTransport(responses))
    engine.create_closed_probe_container(IMAGE_ID)
    with pytest.raises(LocalDockerEngineError, match="probe failed"):
        engine.run_closed_probe(CONTAINER_ID, expected_image_id=IMAGE_ID)

    with pytest.raises(LocalDockerEngineError, match="frame is truncated"):
        module._probe_log_frames(b"short")


def test_transport_timeout_is_closed_and_not_exposed(monkeypatch):
    from human_feedback.adapters import local_docker_engine as module

    class Connection:
        instance = None

        def __init__(self, _timeout):
            self.closed = False
            Connection.instance = self

        def request(self, *_args, **_kwargs):
            pass

        def getresponse(self):
            raise TimeoutError("private daemon detail")

        def close(self):
            self.closed = True

    monkeypatch.setattr(module, "_UnixSocketHTTPConnection", Connection)
    with pytest.raises(module.LocalDockerEngineError, match="transport failed") as caught:
        module._LocalUnixTransport().request(
            "POST",
            "/v1.44/containers/" + CONTAINER_ID + "/wait?condition=not-running",
            response_limit=1024,
            timeout=300.0,
        )
    assert "private daemon detail" not in str(caught.value)
    assert Connection.instance.closed is True


@pytest.mark.parametrize(
    "stdout",
    [
        b"",
        b"{}\n",
        _probe_observation(extra="forbidden"),
        _probe_observation(laya="0.4.3"),
        _probe_observation(model_eval=False),
        b'{"device":NaN}\n',
        _probe_observation() + _probe_observation(),
    ],
)
def test_probe_observation_rejects_empty_extra_wrong_nonfinite_or_multiple_json(stdout):
    from human_feedback.adapters import local_docker_engine as module

    with pytest.raises(module.LocalDockerEngineError):
        module._validate_probe_observation(stdout)


def test_remove_container_requires_tracked_id_and_matching_nonce_then_is_idempotent(monkeypatch):
    from human_feedback.adapters import local_docker_engine as module

    monkeypatch.setattr(module.secrets, "token_hex", lambda _size: "d" * 32)
    transport = FakeTransport(
        [
            _response(200, _version()),
            _response(200, _info()),
            _response(201, {"Id": CONTAINER_ID, "Warnings": []}),
            _response(200, _container_inspect()),
            _response(204),
        ]
    )
    engine = _engine(transport)
    engine.create_closed_probe_container(IMAGE_ID)

    assert engine.remove_owned_container(CONTAINER_ID) is True
    assert engine.remove_owned_container(CONTAINER_ID) is False
    assert transport.calls[-1]["path"] == f"/v1.44/containers/{CONTAINER_ID}?force=1&v=1"


def test_remove_container_never_deletes_rebound_or_untracked_resource(monkeypatch):
    from human_feedback.adapters import local_docker_engine as module
    from human_feedback.adapters.local_docker_engine import LocalDockerEngineError

    monkeypatch.setattr(module.secrets, "token_hex", lambda _size: "d" * 32)
    transport = FakeTransport(
        [
            _response(200, _version()),
            _response(200, _info()),
            _response(201, {"Id": CONTAINER_ID, "Warnings": []}),
            _response(200, _container_inspect(nonce="e" * 32)),
        ]
    )
    engine = _engine(transport)
    engine.create_closed_probe_container(IMAGE_ID)

    with pytest.raises(LocalDockerEngineError):
        engine.remove_owned_container(CONTAINER_ID)
    assert all(call["method"] != "DELETE" for call in transport.calls)

    fresh = _engine(FakeTransport([]))
    with pytest.raises(LocalDockerEngineError):
        fresh.remove_owned_container(CONTAINER_ID)


def test_remove_container_retry_accepts_exact_owned_resource_already_absent(monkeypatch):
    from human_feedback.adapters import local_docker_engine as module

    monkeypatch.setattr(module.secrets, "token_hex", lambda _size: "d" * 32)
    transport = FakeTransport(
        [
            _response(200, _version()),
            _response(200, _info()),
            _response(201, {"Id": CONTAINER_ID, "Warnings": []}),
            _response(404),
        ]
    )
    engine = _engine(transport)
    engine.create_closed_probe_container(IMAGE_ID)

    assert engine.remove_owned_container(CONTAINER_ID) is False
    assert engine.remove_owned_container(CONTAINER_ID) is False
    assert all(call["method"] != "DELETE" for call in transport.calls)


def test_lost_create_response_reconciles_only_exact_random_name_then_cleans_up(
    monkeypatch,
):
    from human_feedback.adapters import local_docker_engine as module

    monkeypatch.setattr(module.secrets, "token_hex", lambda _size: "d" * 32)
    transport = FakeTransport(
        [
            _response(200, _version()),
            _response(200, _info()),
            module.LocalDockerEngineError("response lost"),
            _response(200, _container_inspect()),
            _response(200, _container_inspect()),
            _response(204),
        ]
    )
    engine = _engine(transport)

    with pytest.raises(module.LocalDockerEngineError, match="response lost"):
        engine.create_closed_probe_container(IMAGE_ID)
    engine.cleanup_owned_resources()

    name = "aai-laya-probe-" + "d" * 32
    assert transport.calls[-3]["path"] == f"/v1.44/containers/{name}/json"
    assert transport.calls[-1]["path"] == (f"/v1.44/containers/{CONTAINER_ID}?force=1&v=1")
    assert all("/containers/json" not in call["path"] for call in transport.calls)


def test_cleanup_retry_keeps_failed_records_and_finishes_later(monkeypatch):
    from human_feedback.adapters import local_docker_engine as module

    monkeypatch.setattr(module.secrets, "token_hex", lambda _size: "d" * 32)
    transport = FakeTransport(
        [
            _response(200, _version()),
            _response(200, _info()),
            _response(201, {"Id": CONTAINER_ID, "Warnings": []}),
            _response(503),
            _response(200, _container_inspect()),
            _response(204),
        ]
    )
    engine = _engine(transport)
    engine.create_closed_probe_container(IMAGE_ID)

    with pytest.raises(module.LocalDockerEngineError, match="cleanup is incomplete"):
        engine.cleanup_owned_resources()
    assert engine._owned_containers == {CONTAINER_ID}

    engine.cleanup_owned_resources()
    assert engine._owned_containers == set()


def test_remove_image_requires_tracked_id_and_matching_nonce():
    from human_feedback.adapters.local_docker_engine import LocalDockerEngineError

    transport = FakeTransport([])
    engine = _engine(transport)
    with pytest.raises(LocalDockerEngineError):
        engine.remove_owned_image(IMAGE_ID)
    assert transport.calls == []


def test_ids_and_nonce_are_closed_before_any_request():
    from human_feedback.adapters.local_docker_engine import (
        LocalDockerEngine,
        LocalDockerEngineError,
    )

    with pytest.raises(LocalDockerEngineError):
        LocalDockerEngine(ownership_nonce="not-a-nonce", _transport=FakeTransport([]))
    engine = _engine(FakeTransport([]))
    for value in ("latest", "sha256:../escape", "sha256:" + "A" * 64):
        with pytest.raises(LocalDockerEngineError):
            engine.create_closed_probe_container(value)
    assert engine._transport.calls == []
