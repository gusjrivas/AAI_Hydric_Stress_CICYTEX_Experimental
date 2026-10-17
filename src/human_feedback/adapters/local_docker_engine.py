"""Narrow local Docker Engine adapter for the disposable Laya runtime.

The Docker daemon is trusted orchestration infrastructure.  This module never
selects an endpoint from ambient Docker configuration and never exposes the
daemon socket to the child container.
"""

from __future__ import annotations

import http.client
import json
import re
import secrets
import socket
import time
import urllib.parse
from dataclasses import dataclass
from typing import Any

from human_feedback.adapters._laya_runtime_probe import (
    IMAGE_ENVIRONMENT,
    PROBE_ARGUMENTS,
    PROBE_ENVIRONMENT,
)

DOCKER_SOCKET_PATH = "/var/run/docker.sock"
DOCKER_API_VERSION = "v1.44"
OWNERSHIP_LABEL = "org.aai-hydric.runtime.owner-nonce"

_PINNED_API = (1, 44)
_IMAGE_ID = re.compile(r"sha256:[0-9a-f]{64}\Z")
_CONTAINER_ID = re.compile(r"[0-9a-f]{64}\Z")
_NONCE = re.compile(r"[0-9a-f]{32,64}\Z")
_REQUEST_TIMEOUT_SECONDS = 10.0
_CONTROL_RESPONSE_LIMIT = 256 * 1024
_ARCHIVE_BYTES_LIMIT = 5 * 1024 * 1024 * 1024
_ARCHIVE_CHUNK_LIMIT = 1024 * 1024
_ARCHIVE_TIMEOUT_SECONDS = 15 * 60.0
_PROBE_TIMEOUT_SECONDS = 5 * 60.0
_PROBE_LOG_LIMIT = 64 * 1024

_MEMORY_BYTES = 4 * 1024**3
_TMPFS = "rw,nosuid,nodev,noexec,size=67108864,mode=1777"
_EXPECTED_PROBE_OBSERVATION = {
    "device": "cpu",
    "laya": "0.4.2",
    "loaded": "multilingual",
    "model_eval": True,
    "python": "3.11.10",
    "schema_version": "laya-local-load-probe-v1",
}


class LocalDockerEngineError(RuntimeError):
    """The local engine could not satisfy the closed orchestration contract."""


@dataclass(frozen=True, slots=True)
class DockerHttpResponse:
    status: int
    body: bytes


class DockerByteStream:
    """One bounded daemon response whose connection is closed on EOF or exit."""

    def __init__(self, connection, response, *, byte_limit: int, deadline: float) -> None:
        self._connection = connection
        self._response = response
        self._remaining = byte_limit
        self._deadline = deadline
        self._closed = False

    def __enter__(self):
        return self

    def __exit__(self, _error_type, _error, _traceback) -> None:
        self.close()

    def __iter__(self):
        try:
            while True:
                if time.monotonic() > self._deadline:
                    raise LocalDockerEngineError("local Docker stream deadline exceeded")
                chunk = self._response.read(min(_ARCHIVE_CHUNK_LIMIT, self._remaining + 1))
                if not chunk:
                    self.close()
                    return
                if type(chunk) is not bytes or len(chunk) > self._remaining:
                    raise LocalDockerEngineError("local Docker stream exceeded its bound")
                self._remaining -= len(chunk)
                yield chunk
        except BaseException:
            self.close()
            raise

    def close(self) -> None:
        if not self._closed:
            self._closed = True
            self._connection.close()


class _ChunkedRequestWriter:
    """Bounded short-writing sink for one HTTP chunked request body."""

    def __init__(self, connection, *, byte_limit: int, deadline: float) -> None:
        self._connection = connection
        self._byte_limit = byte_limit
        self._deadline = deadline
        self.total = 0

    def write(self, buffer: object) -> int:
        if type(buffer) not in {bytes, bytearray, memoryview}:
            raise LocalDockerEngineError("local Docker upload buffer is invalid")
        view = memoryview(buffer).cast("B")
        if not view:
            return 0
        if time.monotonic() > self._deadline:
            raise LocalDockerEngineError("local Docker upload deadline exceeded")
        count = min(len(view), _ARCHIVE_CHUNK_LIMIT)
        if self.total + count > self._byte_limit:
            raise LocalDockerEngineError("local Docker upload exceeded its bound")
        payload = view[:count]
        try:
            self._connection.send(f"{count:x}\r\n".encode("ascii"))
            self._connection.send(payload)
            self._connection.send(b"\r\n")
        except Exception:
            raise LocalDockerEngineError("local Docker streaming upload failed") from None
        self.total += count
        return count


class _UnixSocketHTTPConnection(http.client.HTTPConnection):
    def __init__(self, timeout: float) -> None:
        super().__init__("localhost", timeout=timeout)

    def connect(self) -> None:
        descriptor = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            descriptor.settimeout(self.timeout)
            descriptor.connect(DOCKER_SOCKET_PATH)
        except BaseException:
            descriptor.close()
            raise
        self.sock = descriptor


class _LocalUnixTransport:
    """Bounded HTTP/1.1 transport pinned to the one authorized Unix socket."""

    def request(
        self,
        method: str,
        path: str,
        *,
        body: bytes | None = None,
        headers: dict[str, str] | None = None,
        response_limit: int,
        timeout: float,
    ) -> DockerHttpResponse:
        if (
            method not in {"GET", "POST", "DELETE"}
            or type(path) is not str
            or not path.startswith("/")
            or path.startswith("//")
            or any(character in path for character in "\r\n")
            or type(response_limit) is not int
            or not 0 < response_limit <= _CONTROL_RESPONSE_LIMIT
            or type(timeout) not in {int, float}
            or not 0 < timeout <= _PROBE_TIMEOUT_SECONDS
            or body is not None
            and type(body) is not bytes
        ):
            raise LocalDockerEngineError("local Docker request is invalid")
        safe_headers = {} if headers is None else dict(headers)
        if any(
            type(name) is not str
            or type(value) is not str
            or not name
            or any(character in name + value for character in "\r\n")
            for name, value in safe_headers.items()
        ):
            raise LocalDockerEngineError("local Docker headers are invalid")
        connection = _UnixSocketHTTPConnection(float(timeout))
        try:
            connection.request(method, path, body=body, headers=safe_headers)
            response = connection.getresponse()
            chunks = []
            remaining = response_limit + 1
            while remaining:
                chunk = response.read(min(64 * 1024, remaining))
                if not chunk:
                    break
                chunks.append(chunk)
                remaining -= len(chunk)
            payload = b"".join(chunks)
            if len(payload) > response_limit:
                raise LocalDockerEngineError("local Docker response exceeded its bound")
            return DockerHttpResponse(status=response.status, body=payload)
        except LocalDockerEngineError:
            raise
        except Exception:
            raise LocalDockerEngineError("local Docker transport failed") from None
        finally:
            connection.close()

    def upload_producer(
        self,
        path: str,
        producer: object,
        *,
        total_limit: int,
        response_limit: int,
        timeout: float,
        headers: dict[str, str],
    ) -> DockerHttpResponse:
        if total_limit != _ARCHIVE_BYTES_LIMIT or not 0 < timeout <= _ARCHIVE_TIMEOUT_SECONDS:
            raise LocalDockerEngineError("local Docker upload bound is invalid")
        if (
            type(path) is not str
            or not path.startswith(f"/{DOCKER_API_VERSION}/images/create?")
            or not callable(producer)
            or headers != {"Content-Type": "application/x-tar"}
            or not 0 < response_limit <= _CONTROL_RESPONSE_LIMIT
        ):
            raise LocalDockerEngineError("local Docker upload path is invalid")
        connection = _UnixSocketHTTPConnection(float(timeout))
        try:
            connection.putrequest("POST", path)
            connection.putheader("Content-Type", "application/x-tar")
            connection.putheader("Transfer-Encoding", "chunked")
            connection.endheaders()
            writer = _ChunkedRequestWriter(
                connection,
                byte_limit=total_limit,
                deadline=time.monotonic() + timeout,
            )
            reported = producer(writer)
            if type(reported) is not int or reported != writer.total:
                raise LocalDockerEngineError("local Docker upload count changed")
            if time.monotonic() > writer._deadline:
                raise LocalDockerEngineError("local Docker upload deadline exceeded")
            connection.send(b"0\r\n\r\n")
            response = connection.getresponse()
            chunks = []
            remaining = response_limit + 1
            while remaining:
                chunk = response.read(min(64 * 1024, remaining))
                if not chunk:
                    break
                chunks.append(chunk)
                remaining -= len(chunk)
            payload = b"".join(chunks)
            if len(payload) > response_limit:
                raise LocalDockerEngineError("local Docker response exceeded its bound")
            return DockerHttpResponse(status=response.status, body=payload)
        except LocalDockerEngineError:
            raise
        except Exception:
            raise LocalDockerEngineError("local Docker streaming upload failed") from None
        finally:
            connection.close()

    def open_stream(self, path: str, *, byte_limit: int, timeout: float) -> DockerByteStream:
        if (
            type(path) is not str
            or not path.startswith(f"/{DOCKER_API_VERSION}/containers/")
            or not path.endswith("/export")
            or byte_limit != _ARCHIVE_BYTES_LIMIT
            or not 0 < timeout <= _ARCHIVE_TIMEOUT_SECONDS
        ):
            raise LocalDockerEngineError("local Docker download bound is invalid")
        connection = _UnixSocketHTTPConnection(float(timeout))
        try:
            connection.request("GET", path, headers={})
            response = connection.getresponse()
            if response.status != 200:
                raise LocalDockerEngineError("local Docker export failed")
            return DockerByteStream(
                connection,
                response,
                byte_limit=byte_limit,
                deadline=time.monotonic() + timeout,
            )
        except LocalDockerEngineError:
            connection.close()
            raise
        except Exception:
            connection.close()
            raise LocalDockerEngineError("local Docker streaming download failed") from None


def _reject_constant(_value: str) -> None:
    raise ValueError("non-finite JSON is forbidden")


def _object_without_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _json_object(payload: bytes) -> dict[str, Any]:
    try:
        value = json.loads(
            payload.decode("utf-8"),
            parse_constant=_reject_constant,
            object_pairs_hook=_object_without_duplicates,
        )
    except Exception:
        raise LocalDockerEngineError("local Docker response schema is invalid") from None
    if type(value) is not dict:
        raise LocalDockerEngineError("local Docker response schema is invalid")
    return value


def _imported_image_id(payload: bytes) -> str:
    identities = set()
    try:
        lines = payload.splitlines()
        if not lines:
            raise ValueError("empty import response")
        for line in lines:
            value = _json_object(line)
            if "error" in value or "errorDetail" in value:
                raise ValueError("daemon import error")
            status = value.get("status")
            if type(status) is str and _IMAGE_ID.fullmatch(status) is not None:
                identities.add(status)
    except Exception:
        raise LocalDockerEngineError("local Docker import response is invalid") from None
    if len(identities) != 1:
        raise LocalDockerEngineError("local Docker import identity is invalid")
    return identities.pop()


def _probe_log_frames(payload: bytes) -> tuple[bytes, bytes]:
    stdout = bytearray()
    stderr = bytearray()
    offset = 0
    while offset < len(payload):
        if len(payload) - offset < 8:
            raise LocalDockerEngineError("local Docker log frame is truncated")
        stream = payload[offset]
        if stream not in {1, 2} or payload[offset + 1 : offset + 4] != b"\x00\x00\x00":
            raise LocalDockerEngineError("local Docker log frame is invalid")
        size = int.from_bytes(payload[offset + 4 : offset + 8], "big")
        offset += 8
        if size > len(payload) - offset:
            raise LocalDockerEngineError("local Docker log frame is truncated")
        target = stdout if stream == 1 else stderr
        target.extend(payload[offset : offset + size])
        offset += size
        if len(stdout) + len(stderr) > _PROBE_LOG_LIMIT:
            raise LocalDockerEngineError("local Docker probe output exceeded its bound")
    return bytes(stdout), bytes(stderr)


def _validate_probe_observation(stdout: bytes) -> None:
    if _json_object(stdout) != _EXPECTED_PROBE_OBSERVATION:
        raise LocalDockerEngineError("local Docker probe observation is invalid")


def _api_version(value: object) -> tuple[int, int]:
    if type(value) is not str or re.fullmatch(r"[0-9]+\.[0-9]+", value) is None:
        raise LocalDockerEngineError("local Docker API version is invalid")
    major, minor = value.split(".")
    return int(major), int(minor)


def _require_image_id(value: object) -> str:
    if type(value) is not str or _IMAGE_ID.fullmatch(value) is None:
        raise LocalDockerEngineError("local Docker image identity is invalid")
    return value


def _require_container_id(value: object) -> str:
    if type(value) is not str or _CONTAINER_ID.fullmatch(value) is None:
        raise LocalDockerEngineError("local Docker container identity is invalid")
    return value


def _closed_probe_payload(image_id: str, nonce: str) -> dict[str, Any]:
    image_id = _require_image_id(image_id)
    if type(nonce) is not str or _NONCE.fullmatch(nonce) is None:
        raise LocalDockerEngineError("local Docker ownership nonce is invalid")
    return {
        "Image": image_id,
        "User": "65532:65532",
        "WorkingDir": "/opt/laya-runtime",
        "Entrypoint": ["/opt/laya-runtime/.venv/bin/python"],
        "Cmd": list(PROBE_ARGUMENTS),
        "Env": list(PROBE_ENVIRONMENT),
        "Labels": {OWNERSHIP_LABEL: nonce},
        "NetworkDisabled": True,
        "HostConfig": {
            "ReadonlyRootfs": True,
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
            "Memory": _MEMORY_BYTES,
            "MemorySwap": _MEMORY_BYTES,
            "NanoCpus": 2_000_000_000,
            "Ulimits": [
                {"Name": "nofile", "Soft": 256, "Hard": 256},
                {"Name": "core", "Soft": 0, "Hard": 0},
            ],
            "Tmpfs": {"/tmp": _TMPFS},
            "IpcMode": "private",
        },
        "NetworkingConfig": {"EndpointsConfig": {}},
    }


def _image_changes(nonce: str) -> tuple[str, ...]:
    if type(nonce) is not str or _NONCE.fullmatch(nonce) is None:
        raise LocalDockerEngineError("local Docker ownership nonce is invalid")
    return (
        "USER 65532:65532",
        "WORKDIR /opt/laya-runtime",
        'ENTRYPOINT ["laya-serve"]',
        *("ENV " + value for value in IMAGE_ENVIRONMENT),
        f"LABEL {OWNERSHIP_LABEL}={nonce}",
    )


def _matches_owned_image(value: dict[str, Any], *, image_id: str, nonce: str) -> bool:
    config = value.get("Config")
    if type(config) is not dict or value.get("Id") != image_id:
        return False
    labels = config.get("Labels")
    return (
        config.get("User") == "65532:65532"
        and config.get("WorkingDir") == "/opt/laya-runtime"
        and config.get("Entrypoint") == ["laya-serve"]
        and config.get("Env") == list(IMAGE_ENVIRONMENT)
        and type(labels) is dict
        and labels.get(OWNERSHIP_LABEL) == nonce
    )


def _matches_closed_probe(
    value: dict[str, Any], *, image_id: str, container_id: str, nonce: str
) -> bool:
    config = value.get("Config")
    host = value.get("HostConfig")
    networks = value.get("NetworkSettings")
    state = value.get("State")
    if not all(type(item) is dict for item in (config, host, networks, state)):
        return False
    expected = _closed_probe_payload(image_id, nonce)
    expected_host = expected["HostConfig"]
    security = host.get("SecurityOpt")
    network_entries = networks.get("Networks")
    no_network = type(network_entries) is dict and set(network_entries).issubset({"none"})
    return (
        value.get("Id") == container_id
        and config.get("Image") == image_id
        and config.get("User") == expected["User"]
        and config.get("WorkingDir") == expected["WorkingDir"]
        and config.get("Entrypoint") == expected["Entrypoint"]
        and config.get("Cmd") == expected["Cmd"]
        and config.get("Env") == expected["Env"]
        and type(config.get("Labels")) is dict
        and config["Labels"].get(OWNERSHIP_LABEL) == nonce
        and host.get("ReadonlyRootfs") is True
        and host.get("NetworkMode") == "none"
        and host.get("CapDrop") == ["ALL"]
        and type(security) is list
        and "seccomp=builtin" in security
        and any(item in security for item in ("no-new-privileges", "no-new-privileges=true"))
        and host.get("Privileged") is False
        and host.get("Binds") in (None, [])
        and host.get("Mounts") in (None, [])
        and host.get("Devices") in (None, [])
        and host.get("PortBindings") in (None, {})
        and host.get("PublishAllPorts") is False
        and host.get("AutoRemove") is False
        and host.get("OomKillDisable") is False
        and host.get("PidMode") in (None, "")
        and host.get("UTSMode") in (None, "")
        and host.get("UsernsMode") in (None, "")
        and host.get("CgroupnsMode") == "private"
        and host.get("VolumesFrom") in (None, [])
        and host.get("Links") in (None, [])
        and host.get("ExtraHosts") in (None, [])
        and host.get("Dns") in (None, [])
        and host.get("DnsSearch") in (None, [])
        and host.get("DnsOptions") in (None, [])
        and host.get("PidsLimit") == expected_host["PidsLimit"]
        and host.get("Memory") == expected_host["Memory"]
        and host.get("MemorySwap") == expected_host["MemorySwap"]
        and host.get("NanoCpus") == expected_host["NanoCpus"]
        and host.get("Ulimits") == expected_host["Ulimits"]
        and host.get("Tmpfs") == expected_host["Tmpfs"]
        and host.get("IpcMode") == expected_host["IpcMode"]
        and value.get("Mounts") in (None, [])
        and networks.get("Ports") in (None, {})
        and no_network
        and state.get("Running") is False
    )


class LocalDockerEngine:
    """Stateful owner of exact local Docker resources created by one operation."""

    def __init__(self, ownership_nonce: str, _transport=None) -> None:
        if type(ownership_nonce) is not str or _NONCE.fullmatch(ownership_nonce) is None:
            raise LocalDockerEngineError("local Docker ownership nonce is invalid")
        self._nonce = ownership_nonce
        self._transport = _LocalUnixTransport() if _transport is None else _transport
        self._ready = False
        self._owned_containers: set[str] = set()
        self._owned_images: set[str] = set()
        self._removed_containers: set[str] = set()
        self._removed_images: set[str] = set()
        self._container_images: dict[str, str] = {}
        self._container_intents: dict[str, str] = {}
        self._image_intents: set[str] = set()
        self._closed_inspected: set[str] = set()
        self._started: set[str] = set()
        self._waited: set[str] = set()

    def _request(
        self,
        method: str,
        path: str,
        *,
        body: bytes | None = None,
        response_limit: int = _CONTROL_RESPONSE_LIMIT,
        timeout: float = _REQUEST_TIMEOUT_SECONDS,
    ) -> DockerHttpResponse:
        headers = None if body is None else {"Content-Type": "application/json"}
        return self._transport.request(
            method,
            path,
            body=body,
            headers=headers,
            response_limit=response_limit,
            timeout=timeout,
        )

    def _request_json(
        self,
        method: str,
        path: str,
        *,
        expected_status: int,
        body: bytes | None = None,
        timeout: float = _REQUEST_TIMEOUT_SECONDS,
    ) -> dict[str, Any]:
        response = self._request(method, path, body=body, timeout=timeout)
        if response.status != expected_status:
            raise LocalDockerEngineError("local Docker operation failed")
        return _json_object(response.body)

    def _ensure_ready(self) -> None:
        if self._ready:
            return
        version = self._request_json("GET", "/version", expected_status=200)
        minimum = _api_version(version.get("MinAPIVersion"))
        maximum = _api_version(version.get("ApiVersion"))
        if (
            version.get("Os") != "linux"
            or version.get("Arch") != "amd64"
            or not minimum <= _PINNED_API <= maximum
        ):
            raise LocalDockerEngineError("local Docker daemon profile is incompatible")
        info = self._request_json("GET", f"/{DOCKER_API_VERSION}/info", expected_status=200)
        security = info.get("SecurityOptions")
        if (
            info.get("OSType") != "linux"
            or info.get("Architecture") not in {"x86_64", "amd64"}
            or type(security) is not list
            or not any(
                type(item) is str and item.startswith("name=seccomp") and "unconfined" not in item
                for item in security
            )
        ):
            raise LocalDockerEngineError("local Docker daemon isolation is unavailable")
        self._ready = True

    def create_closed_probe_container(self, image_id: str) -> str:
        image_id = _require_image_id(image_id)
        self._ensure_ready()
        name = "aai-laya-probe-" + secrets.token_hex(16)
        self._container_intents[name] = image_id
        payload = json.dumps(
            _closed_probe_payload(image_id, self._nonce),
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("ascii")
        response = self._request_json(
            "POST",
            f"/{DOCKER_API_VERSION}/containers/create?name={name}",
            expected_status=201,
            body=payload,
        )
        container_id = _require_container_id(response.get("Id"))
        self._owned_containers.add(container_id)
        self._container_images[container_id] = image_id
        self._container_intents.pop(name, None)
        if set(response).difference({"Id", "Warnings"}):
            raise LocalDockerEngineError("local Docker create response is invalid")
        return container_id

    def import_normalized_image(self, producer: object) -> str:
        """Import one bounded TAR stream and register only its inspected owned image."""
        self._ensure_ready()
        repository = "aai-laya-runtime-" + self._nonce
        reference = repository + ":materialized"
        self._image_intents.add(reference)
        query = urllib.parse.urlencode(
            [
                ("fromSrc", "-"),
                ("repo", repository),
                ("tag", "materialized"),
                *(("changes", change) for change in _image_changes(self._nonce)),
            ]
        )
        response = self._transport.upload_producer(
            f"/{DOCKER_API_VERSION}/images/create?{query}",
            producer,
            total_limit=_ARCHIVE_BYTES_LIMIT,
            response_limit=_CONTROL_RESPONSE_LIMIT,
            timeout=_ARCHIVE_TIMEOUT_SECONDS,
            headers={"Content-Type": "application/x-tar"},
        )
        if response.status != 200:
            raise LocalDockerEngineError("local Docker image import failed")
        image_id = _imported_image_id(response.body)
        self._owned_images.add(image_id)
        self._image_intents.discard(reference)
        value = self.inspect_image(image_id)
        if not _matches_owned_image(value, image_id=image_id, nonce=self._nonce):
            raise LocalDockerEngineError("local Docker imported image configuration changed")
        return image_id

    def _reconcile_container_intent(self, name: str, image_id: str) -> None:
        path_name = urllib.parse.quote(name, safe="")
        response = self._request("GET", f"/{DOCKER_API_VERSION}/containers/{path_name}/json")
        if response.status == 404:
            self._container_intents.pop(name, None)
            return
        if response.status != 200:
            raise LocalDockerEngineError("owned Docker container intent is unresolved")
        value = _json_object(response.body)
        container_id = _require_container_id(value.get("Id"))
        if not _matches_closed_probe(
            value,
            image_id=image_id,
            container_id=container_id,
            nonce=self._nonce,
        ):
            raise LocalDockerEngineError("local Docker container intent changed")
        self._owned_containers.add(container_id)
        self._container_images[container_id] = image_id
        self._container_intents.pop(name, None)

    def _reconcile_image_intent(self, reference: str) -> None:
        path_reference = urllib.parse.quote(reference, safe="")
        response = self._request("GET", f"/{DOCKER_API_VERSION}/images/{path_reference}/json")
        if response.status == 404:
            self._image_intents.discard(reference)
            return
        if response.status != 200:
            raise LocalDockerEngineError("owned Docker image intent is unresolved")
        value = _json_object(response.body)
        image_id = _require_image_id(value.get("Id"))
        if not _matches_owned_image(value, image_id=image_id, nonce=self._nonce):
            raise LocalDockerEngineError("local Docker image intent changed")
        self._owned_images.add(image_id)
        self._image_intents.discard(reference)

    def cleanup_owned_resources(self) -> None:
        """Reconcile exact intents, then retry owned containers before images."""
        self._ensure_ready()
        failed = False
        for name, image_id in tuple(self._container_intents.items()):
            try:
                self._reconcile_container_intent(name, image_id)
            except Exception:
                failed = True
        for reference in tuple(self._image_intents):
            try:
                self._reconcile_image_intent(reference)
            except Exception:
                failed = True
        for container_id in tuple(self._owned_containers):
            try:
                self.remove_owned_container(container_id)
            except Exception:
                failed = True
        for image_id in tuple(self._owned_images):
            try:
                self.remove_owned_image(image_id)
            except Exception:
                failed = True
        if failed:
            raise LocalDockerEngineError("owned Docker resource cleanup is incomplete")

    def inspect_container(self, container_id: str) -> dict[str, Any]:
        container_id = _require_container_id(container_id)
        self._ensure_ready()
        value = self._request_json(
            "GET",
            f"/{DOCKER_API_VERSION}/containers/{container_id}/json",
            expected_status=200,
        )
        if value.get("Id") != container_id:
            raise LocalDockerEngineError("local Docker container identity changed")
        return value

    def inspect_closed_probe_container(
        self, container_id: str, *, expected_image_id: str
    ) -> dict[str, Any]:
        container_id = _require_container_id(container_id)
        image_id = _require_image_id(expected_image_id)
        value = self.inspect_container(container_id)
        if not _matches_closed_probe(
            value,
            image_id=image_id,
            container_id=container_id,
            nonce=self._nonce,
        ):
            raise LocalDockerEngineError("local Docker probe isolation changed")
        if container_id in self._owned_containers:
            self._closed_inspected.add(container_id)
        return value

    def export_stopped_container_stream(self, container_id: str) -> DockerByteStream:
        container_id = _require_container_id(container_id)
        image_id = self._container_images.get(container_id)
        if image_id is None or container_id not in self._closed_inspected:
            raise LocalDockerEngineError("local Docker probe was not closed-inspected")
        if container_id in self._started:
            raise LocalDockerEngineError("local Docker probe already started")
        self.inspect_closed_probe_container(container_id, expected_image_id=image_id)
        return self._transport.open_stream(
            f"/{DOCKER_API_VERSION}/containers/{container_id}/export",
            byte_limit=_ARCHIVE_BYTES_LIMIT,
            timeout=_ARCHIVE_TIMEOUT_SECONDS,
        )

    def start_probe(self, container_id: str) -> None:
        container_id = _require_container_id(container_id)
        image_id = self._container_images.get(container_id)
        if image_id is None or container_id not in self._closed_inspected:
            raise LocalDockerEngineError("local Docker probe was not closed-inspected")
        if container_id in self._started:
            raise LocalDockerEngineError("local Docker probe already started")
        self.inspect_closed_probe_container(container_id, expected_image_id=image_id)
        response = self._request("POST", f"/{DOCKER_API_VERSION}/containers/{container_id}/start")
        if response.status != 204:
            raise LocalDockerEngineError("local Docker probe start failed")
        self._started.add(container_id)

    def wait_probe(self, container_id: str) -> None:
        container_id = _require_container_id(container_id)
        if container_id not in self._started or container_id in self._waited:
            raise LocalDockerEngineError("local Docker probe wait state is invalid")
        value = self._request_json(
            "POST",
            f"/{DOCKER_API_VERSION}/containers/{container_id}/wait?condition=not-running",
            expected_status=200,
            timeout=_PROBE_TIMEOUT_SECONDS,
        )
        error = value.get("Error")
        if value.get("StatusCode") != 0 or error not in (None, {"Message": ""}):
            raise LocalDockerEngineError("local Docker probe failed")
        self._waited.add(container_id)

    def probe_logs_bounded(self, container_id: str) -> tuple[bytes, bytes]:
        container_id = _require_container_id(container_id)
        if container_id not in self._waited:
            raise LocalDockerEngineError("local Docker probe logs are premature")
        response = self._request(
            "GET",
            f"/{DOCKER_API_VERSION}/containers/{container_id}/logs?"
            "stdout=1&stderr=1&timestamps=0&follow=0",
            response_limit=_PROBE_LOG_LIMIT + 8192,
        )
        if response.status != 200:
            raise LocalDockerEngineError("local Docker probe logs failed")
        return _probe_log_frames(response.body)

    def run_closed_probe(self, container_id: str, *, expected_image_id: str) -> tuple[bytes, bytes]:
        """Re-verify, run, wait for, and return bounded output from one probe."""
        self.inspect_closed_probe_container(container_id, expected_image_id=expected_image_id)
        self.start_probe(container_id)
        self.wait_probe(container_id)
        stdout, stderr = self.probe_logs_bounded(container_id)
        _validate_probe_observation(stdout)
        return stdout, stderr

    def inspect_image(self, image_id: str) -> dict[str, Any]:
        image_id = _require_image_id(image_id)
        self._ensure_ready()
        value = self._request_json(
            "GET", f"/{DOCKER_API_VERSION}/images/{image_id}/json", expected_status=200
        )
        if value.get("Id") != image_id:
            raise LocalDockerEngineError("local Docker image identity changed")
        return value

    def remove_owned_container(self, container_id: str) -> bool:
        container_id = _require_container_id(container_id)
        if container_id in self._removed_containers:
            return False
        if container_id not in self._owned_containers:
            raise LocalDockerEngineError("local Docker container is not owned")
        self._ensure_ready()
        inspected = self._request("GET", f"/{DOCKER_API_VERSION}/containers/{container_id}/json")
        if inspected.status == 404:
            self._owned_containers.remove(container_id)
            self._removed_containers.add(container_id)
            self._container_images.pop(container_id, None)
            self._closed_inspected.discard(container_id)
            self._started.discard(container_id)
            self._waited.discard(container_id)
            return False
        if inspected.status != 200:
            raise LocalDockerEngineError("owned Docker container inspection failed")
        value = _json_object(inspected.body)
        if value.get("Id") != container_id:
            raise LocalDockerEngineError("local Docker container identity changed")
        labels = value.get("Config", {}).get("Labels")
        if type(labels) is not dict or labels.get(OWNERSHIP_LABEL) != self._nonce:
            raise LocalDockerEngineError("local Docker container ownership changed")
        response = self._request(
            "DELETE", f"/{DOCKER_API_VERSION}/containers/{container_id}?force=1&v=1"
        )
        if response.status != 204:
            raise LocalDockerEngineError("owned Docker container cleanup failed")
        self._owned_containers.remove(container_id)
        self._removed_containers.add(container_id)
        self._container_images.pop(container_id, None)
        self._closed_inspected.discard(container_id)
        self._started.discard(container_id)
        self._waited.discard(container_id)
        return True

    def remove_owned_image(self, image_id: str) -> bool:
        image_id = _require_image_id(image_id)
        if image_id in self._removed_images:
            return False
        if image_id not in self._owned_images:
            raise LocalDockerEngineError("local Docker image is not owned")
        self._ensure_ready()
        inspected = self._request("GET", f"/{DOCKER_API_VERSION}/images/{image_id}/json")
        if inspected.status == 404:
            self._owned_images.remove(image_id)
            self._removed_images.add(image_id)
            return False
        if inspected.status != 200:
            raise LocalDockerEngineError("owned Docker image inspection failed")
        value = _json_object(inspected.body)
        if value.get("Id") != image_id:
            raise LocalDockerEngineError("local Docker image identity changed")
        labels = value.get("Config", {}).get("Labels")
        if type(labels) is not dict or labels.get(OWNERSHIP_LABEL) != self._nonce:
            raise LocalDockerEngineError("local Docker image ownership changed")
        response = self._request(
            "DELETE", f"/{DOCKER_API_VERSION}/images/{image_id}?force=0&noprune=1"
        )
        if response.status != 200:
            raise LocalDockerEngineError("owned Docker image cleanup failed")
        self._owned_images.remove(image_id)
        self._removed_images.add(image_id)
        return True
