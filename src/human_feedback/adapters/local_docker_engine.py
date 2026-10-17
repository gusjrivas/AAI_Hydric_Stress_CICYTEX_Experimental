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
import threading
import time
import urllib.parse
from dataclasses import dataclass
from typing import Any

from human_feedback.adapters._laya_offline_probe import (
    OFFLINE_PROBE_ARGUMENTS,
    OFFLINE_PROBE_ENVIRONMENT,
)
from human_feedback.adapters._laya_runtime_probe import (
    IMAGE_ENVIRONMENT,
    PROBE_ARGUMENTS,
    PROBE_ENVIRONMENT,
)
from human_feedback.adapters._laya_synthetic_probe import (
    SYNTHETIC_PROBE_ARGUMENTS,
    SYNTHETIC_PROBE_ENVIRONMENT,
    validate_synthetic_probe_observation,
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
_OFFLINE_STDIN_LIMIT = 64 * 1024
_OFFLINE_STDOUT_LIMIT = 64 * 1024
_OFFLINE_STDERR_LIMIT = 8 * 1024
_OFFLINE_TIMEOUT_SECONDS = 5 * 60.0

_MEMORY_BYTES = 4 * 1024**3
_TMPFS = "rw,nosuid,nodev,noexec,size=67108864,mode=1777"
_ZERO_DOCKER_TIMESTAMP = "0001-01-01T00:00:00Z"
_EXPECTED_PROBE_OBSERVATION = {
    "device": "cpu",
    "laya": "0.4.2",
    "loaded": "multilingual",
    "model_eval": True,
    "python": "3.11.10",
    "schema_version": "laya-local-load-probe-v1",
}
_MATERIALIZATION_PROBE_PROFILE = "materialization-load-v1"
_SYNTHETIC_PROBE_PROFILE = "synthetic-execution-v1"
_LOSO_OFFLINE_PROFILE = "gold-blind-offline-v2"


class LocalDockerEngineError(RuntimeError):
    """The local engine could not satisfy the closed orchestration contract."""


@dataclass(frozen=True, slots=True)
class DockerHttpResponse:
    status: int
    body: bytes


class _DeadlineWatchdog:
    """Close one connection when its total monotonic budget expires."""

    def __init__(self, connection, deadline: float) -> None:
        self._connection = connection
        self._expired = threading.Event()
        delay = max(0.0, deadline - time.monotonic())
        self._timer = threading.Timer(delay, self._expire)
        self._timer.daemon = True
        self._timer.start()

    @property
    def expired(self) -> bool:
        return self._expired.is_set()

    def _expire(self) -> None:
        self._expired.set()
        descriptor = getattr(self._connection, "sock", None)
        if descriptor is not None:
            try:
                descriptor.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass
        try:
            self._connection.close()
        except Exception:
            pass

    def cancel(self) -> None:
        self._timer.cancel()
        if threading.current_thread() is not self._timer:
            self._timer.join(1.0)


def _remaining_timeout(connection, deadline: float) -> float:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise LocalDockerEngineError("local Docker total deadline exceeded")
    connection.timeout = remaining
    descriptor = getattr(connection, "sock", None)
    if descriptor is not None:
        descriptor.settimeout(remaining)
    return remaining


def _response_read(response, size: int) -> bytes:
    reader = response.read1 if isinstance(response, http.client.HTTPResponse) else response.read
    chunk = reader(size)
    if type(chunk) is not bytes:
        raise LocalDockerEngineError("local Docker response schema is invalid")
    return chunk


def _bounded_response_body(connection, response, *, limit: int, deadline: float) -> bytes:
    chunks = []
    remaining = limit + 1
    while remaining:
        _remaining_timeout(connection, deadline)
        chunk = _response_read(response, min(64 * 1024, remaining))
        if time.monotonic() > deadline:
            raise LocalDockerEngineError("local Docker total deadline exceeded")
        if not chunk:
            break
        chunks.append(chunk)
        remaining -= len(chunk)
    payload = b"".join(chunks)
    if len(payload) > limit:
        raise LocalDockerEngineError("local Docker response exceeded its bound")
    return payload


class DockerByteStream:
    """One bounded daemon response whose connection is closed on EOF or exit."""

    def __init__(self, connection, response, *, byte_limit: int, deadline: float, watchdog) -> None:
        self._connection = connection
        self._response = response
        self._remaining = byte_limit
        self._deadline = deadline
        self._watchdog = watchdog
        self._closed = False

    def __enter__(self):
        return self

    def __exit__(self, _error_type, _error, _traceback) -> None:
        self.close()

    def __iter__(self):
        try:
            while True:
                if self._watchdog.expired or time.monotonic() > self._deadline:
                    raise LocalDockerEngineError("local Docker stream deadline exceeded")
                _remaining_timeout(self._connection, self._deadline)
                chunk = _response_read(
                    self._response, min(_ARCHIVE_CHUNK_LIMIT, self._remaining + 1)
                )
                if self._watchdog.expired or time.monotonic() > self._deadline:
                    raise LocalDockerEngineError("local Docker stream deadline exceeded")
                if not chunk:
                    self.close()
                    return
                if type(chunk) is not bytes or len(chunk) > self._remaining:
                    raise LocalDockerEngineError("local Docker stream exceeded its bound")
                self._remaining -= len(chunk)
                yield chunk
        except LocalDockerEngineError:
            self.close()
            raise
        except Exception:
            self.close()
            raise LocalDockerEngineError("local Docker streaming download failed") from None
        except BaseException:
            self.close()
            raise

    def close(self) -> None:
        if not self._closed:
            self._closed = True
            self._watchdog.cancel()
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
            _remaining_timeout(self._connection, self._deadline)
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

    def begin_hijacked_response(self):
        """Parse a 101 response without HTTPConnection closing the upgraded socket."""

        response = http.client.HTTPResponse(self.sock)
        try:
            response.begin()
        except BaseException:
            try:
                response.close()
            except Exception:
                pass
            raise
        return response


def _attach_header_values(response, name: str) -> list[str]:
    headers = getattr(response, "headers", None)
    if headers is None or not callable(getattr(headers, "get_all", None)):
        raise LocalDockerEngineError("local Docker attach headers are invalid")
    values = headers.get_all(name, [])
    if type(values) is not list or any(type(value) is not str for value in values):
        raise LocalDockerEngineError("local Docker attach headers are invalid")
    return values


def _attach_read(reader, size: int) -> bytes:
    chunk = reader.read(size)
    if type(chunk) is not bytes:
        raise LocalDockerEngineError("local Docker attach stream is invalid")
    return chunk


class _DockerAttachSession:
    """One exact bounded stdin/stdout exchange over a hijacked Docker socket."""

    def __init__(
        self,
        connection,
        response,
        *,
        stdin_limit: int,
        stdout_limit: int,
        stderr_limit: int,
        deadline: float,
        watchdog,
    ) -> None:
        self._connection = connection
        self._response = response
        self._reader = response.fp if isinstance(response, http.client.HTTPResponse) else response
        self._stdin_limit = stdin_limit
        self._stdout_limit = stdout_limit
        self._stderr_limit = stderr_limit
        self._deadline = deadline
        self._watchdog = watchdog
        self._used = False
        self._closed = False

    def __enter__(self):
        if self._closed:
            raise LocalDockerEngineError("local Docker attach session is closed")
        return self

    def __exit__(self, _error_type, _error, _traceback) -> None:
        self.close()

    def _read_exact(self, size: int, *, allow_clean_eof: bool = False) -> bytes:
        chunks = []
        remaining = size
        while remaining:
            if self._watchdog.expired or time.monotonic() > self._deadline:
                raise LocalDockerEngineError("local Docker attach deadline exceeded")
            _remaining_timeout(self._connection, self._deadline)
            chunk = _attach_read(self._reader, remaining)
            if self._watchdog.expired or time.monotonic() > self._deadline:
                raise LocalDockerEngineError("local Docker attach deadline exceeded")
            if not chunk:
                if allow_clean_eof and remaining == size:
                    return b""
                raise LocalDockerEngineError("local Docker attach stream is truncated")
            if len(chunk) > remaining:
                raise LocalDockerEngineError("local Docker attach stream is invalid")
            chunks.append(chunk)
            remaining -= len(chunk)
        return b"".join(chunks)

    def exchange(self, canonical_request: bytes) -> tuple[bytes, bytes]:
        if (
            self._used
            or type(canonical_request) is not bytes
            or not 0 < len(canonical_request) <= self._stdin_limit
        ):
            raise LocalDockerEngineError("local Docker attach input is invalid")
        self._used = True
        stdout = bytearray()
        stderr = bytearray()
        try:
            if self._watchdog.expired or time.monotonic() > self._deadline:
                raise LocalDockerEngineError("local Docker attach deadline exceeded")
            _remaining_timeout(self._connection, self._deadline)
            self._connection.send(canonical_request)
            descriptor = getattr(self._connection, "sock", None)
            if descriptor is None:
                raise LocalDockerEngineError("local Docker attach socket is unavailable")
            descriptor.shutdown(socket.SHUT_WR)
            while True:
                header = self._read_exact(8, allow_clean_eof=True)
                if not header:
                    break
                stream = header[0]
                if stream not in {1, 2} or header[1:4] != b"\x00\x00\x00":
                    raise LocalDockerEngineError("local Docker attach frame is invalid")
                size = int.from_bytes(header[4:8], "big")
                target = stdout if stream == 1 else stderr
                limit = self._stdout_limit if stream == 1 else self._stderr_limit
                if size > limit - len(target):
                    raise LocalDockerEngineError("local Docker attach output exceeded its bound")
                target.extend(self._read_exact(size))
            return bytes(stdout), bytes(stderr)
        except LocalDockerEngineError:
            self.close()
            raise
        except Exception:
            self.close()
            raise LocalDockerEngineError("local Docker attach exchange failed") from None
        except BaseException:
            self.close()
            raise

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._watchdog.cancel()
        try:
            self._response.close()
        except Exception:
            pass
        self._connection.close()


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
        deadline = time.monotonic() + timeout
        watchdog = _DeadlineWatchdog(connection, deadline)
        try:
            _remaining_timeout(connection, deadline)
            connection.request(method, path, body=body, headers=safe_headers)
            _remaining_timeout(connection, deadline)
            response = connection.getresponse()
            _remaining_timeout(connection, deadline)
            payload = _bounded_response_body(
                connection, response, limit=response_limit, deadline=deadline
            )
            _remaining_timeout(connection, deadline)
            return DockerHttpResponse(status=response.status, body=payload)
        except LocalDockerEngineError:
            raise
        except Exception:
            raise LocalDockerEngineError("local Docker transport failed") from None
        finally:
            watchdog.cancel()
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
        deadline = time.monotonic() + timeout
        connection = _UnixSocketHTTPConnection(float(timeout))
        watchdog = _DeadlineWatchdog(connection, deadline)
        try:
            _remaining_timeout(connection, deadline)
            connection.putrequest("POST", path)
            connection.putheader("Content-Type", "application/x-tar")
            connection.putheader("Transfer-Encoding", "chunked")
            connection.endheaders()
            writer = _ChunkedRequestWriter(
                connection,
                byte_limit=total_limit,
                deadline=deadline,
            )
            reported = producer(writer)
            if type(reported) is not int or reported != writer.total:
                raise LocalDockerEngineError("local Docker upload count changed")
            if time.monotonic() > writer._deadline:
                raise LocalDockerEngineError("local Docker upload deadline exceeded")
            _remaining_timeout(connection, deadline)
            connection.send(b"0\r\n\r\n")
            _remaining_timeout(connection, deadline)
            response = connection.getresponse()
            _remaining_timeout(connection, deadline)
            payload = _bounded_response_body(
                connection, response, limit=response_limit, deadline=deadline
            )
            _remaining_timeout(connection, deadline)
            return DockerHttpResponse(status=response.status, body=payload)
        except LocalDockerEngineError:
            raise
        except Exception:
            raise LocalDockerEngineError("local Docker streaming upload failed") from None
        finally:
            watchdog.cancel()
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
        deadline = time.monotonic() + timeout
        connection = _UnixSocketHTTPConnection(float(timeout))
        watchdog = _DeadlineWatchdog(connection, deadline)
        try:
            _remaining_timeout(connection, deadline)
            connection.request("GET", path, headers={})
            _remaining_timeout(connection, deadline)
            response = connection.getresponse()
            _remaining_timeout(connection, deadline)
            if response.status != 200:
                raise LocalDockerEngineError("local Docker export failed")
            _remaining_timeout(connection, deadline)
            return DockerByteStream(
                connection,
                response,
                byte_limit=byte_limit,
                deadline=deadline,
                watchdog=watchdog,
            )
        except LocalDockerEngineError:
            watchdog.cancel()
            connection.close()
            raise
        except Exception:
            watchdog.cancel()
            connection.close()
            raise LocalDockerEngineError("local Docker streaming download failed") from None

    def open_attach(
        self,
        path: str,
        *,
        stdin_limit: int,
        stdout_limit: int,
        stderr_limit: int,
        timeout: float,
    ) -> _DockerAttachSession:
        expected_suffix = "/attach?stream=1&stdin=1&stdout=1&stderr=1"
        prefix = f"/{DOCKER_API_VERSION}/containers/"
        identity = (
            path[len(prefix) : -len(expected_suffix)]
            if type(path) is str and path.startswith(prefix) and path.endswith(expected_suffix)
            else None
        )
        if (
            identity is None
            or _CONTAINER_ID.fullmatch(identity) is None
            or stdin_limit != _OFFLINE_STDIN_LIMIT
            or stdout_limit != _OFFLINE_STDOUT_LIMIT
            or stderr_limit != _OFFLINE_STDERR_LIMIT
            or timeout != _OFFLINE_TIMEOUT_SECONDS
        ):
            raise LocalDockerEngineError("local Docker attach request is invalid")
        deadline = time.monotonic() + timeout
        connection = _UnixSocketHTTPConnection(float(timeout))
        watchdog = _DeadlineWatchdog(connection, deadline)
        response = None
        try:
            _remaining_timeout(connection, deadline)
            if callable(getattr(connection, "putrequest", None)):
                connection.putrequest("POST", path)
                connection.putheader("Connection", "Upgrade")
                connection.putheader("Upgrade", "tcp")
                connection.endheaders()
            else:
                connection.request(
                    "POST",
                    path,
                    headers={"Connection": "Upgrade", "Upgrade": "tcp"},
                )
            _remaining_timeout(connection, deadline)
            begin = getattr(connection, "begin_hijacked_response", None)
            response = begin() if callable(begin) else connection.getresponse()
            _remaining_timeout(connection, deadline)
            if (
                response.status != 101
                or _attach_header_values(response, "Connection") != ["Upgrade"]
                or _attach_header_values(response, "Upgrade") != ["tcp"]
                or _attach_header_values(response, "Content-Type")
                != ["application/vnd.docker.multiplexed-stream"]
            ):
                raise LocalDockerEngineError("local Docker attach upgrade is invalid")
            return _DockerAttachSession(
                connection,
                response,
                stdin_limit=stdin_limit,
                stdout_limit=stdout_limit,
                stderr_limit=stderr_limit,
                deadline=deadline,
                watchdog=watchdog,
            )
        except LocalDockerEngineError:
            if response is not None:
                try:
                    response.close()
                except Exception:
                    pass
            watchdog.cancel()
            connection.close()
            raise
        except Exception:
            if response is not None:
                try:
                    response.close()
                except Exception:
                    pass
            watchdog.cancel()
            connection.close()
            raise LocalDockerEngineError("local Docker attach failed") from None
        except BaseException:
            if response is not None:
                try:
                    response.close()
                except Exception:
                    pass
            watchdog.cancel()
            connection.close()
            raise


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
            "CapAdd": [],
            "CapDrop": ["ALL"],
            "SecurityOpt": ["no-new-privileges", "seccomp=builtin"],
            "Privileged": False,
            "Binds": [],
            "Mounts": [],
            "Devices": [],
            "DeviceRequests": [],
            "DeviceCgroupRules": [],
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
            "LogConfig": {
                "Type": "json-file",
                "Config": {"max-size": "64k", "max-file": "1"},
            },
            "IpcMode": "private",
        },
        "NetworkingConfig": {"EndpointsConfig": {}},
    }


def _closed_synthetic_probe_payload(image_id: str, nonce: str) -> dict[str, Any]:
    payload = _closed_probe_payload(image_id, nonce)
    payload["Cmd"] = list(SYNTHETIC_PROBE_ARGUMENTS)
    payload["Env"] = list(SYNTHETIC_PROBE_ENVIRONMENT)
    return payload


def _closed_loso_offline_payload(image_id: str, nonce: str) -> dict[str, Any]:
    payload = _closed_probe_payload(image_id, nonce)
    payload.update(
        {
            "Cmd": list(OFFLINE_PROBE_ARGUMENTS),
            "Env": list(OFFLINE_PROBE_ENVIRONMENT),
            "OpenStdin": True,
            "StdinOnce": True,
            "AttachStdin": True,
            "AttachStdout": True,
            "AttachStderr": True,
            "Tty": False,
        }
    )
    payload["HostConfig"]["LogConfig"] = {"Type": "none", "Config": {}}
    return payload


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


def _matches_closed_security_options(value: object) -> bool:
    if type(value) is not list or len(value) != 2 or any(type(item) is not str for item in value):
        return False
    normalized = {
        "no-new-privileges" if item == "no-new-privileges=true" else item for item in value
    }
    return normalized == {"no-new-privileges", "seccomp=builtin"}


def _matches_fresh_probe_state(value: object) -> bool:
    return type(value) is dict and all(
        (
            value.get("Status") == "created",
            value.get("Running") is False,
            value.get("Paused") is False,
            value.get("Restarting") is False,
            value.get("OOMKilled") is False,
            value.get("Dead") is False,
            value.get("StartedAt") == _ZERO_DOCKER_TIMESTAMP,
            value.get("FinishedAt") == _ZERO_DOCKER_TIMESTAMP,
        )
    )


def _matches_completed_probe_state(value: object) -> bool:
    return type(value) is dict and all(
        (
            value.get("Status") == "exited",
            value.get("Running") is False,
            value.get("Paused") is False,
            value.get("Restarting") is False,
            value.get("OOMKilled") is False,
            value.get("Dead") is False,
            value.get("ExitCode") == 0,
        )
    )


def _matches_closed_probe_payload(
    value: dict[str, Any],
    *,
    image_id: str,
    container_id: str,
    nonce: str,
    expected: dict[str, Any],
) -> bool:
    config = value.get("Config")
    host = value.get("HostConfig")
    networks = value.get("NetworkSettings")
    state = value.get("State")
    if not all(type(item) is dict for item in (config, host, networks, state)):
        return False
    expected_host = expected["HostConfig"]
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
        and host.get("CapAdd") in (None, [])
        and host.get("CapDrop") == ["ALL"]
        and _matches_closed_security_options(host.get("SecurityOpt"))
        and host.get("Privileged") is False
        and host.get("Binds") in (None, [])
        and host.get("Mounts") in (None, [])
        and host.get("Devices") in (None, [])
        and host.get("DeviceRequests") in (None, [])
        and host.get("DeviceCgroupRules") in (None, [])
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
        and host.get("LogConfig") == expected_host["LogConfig"]
        and host.get("IpcMode") == expected_host["IpcMode"]
        and value.get("Mounts") in (None, [])
        and networks.get("Ports") in (None, {})
        and no_network
        and _matches_fresh_probe_state(state)
    )


def _matches_closed_probe(
    value: dict[str, Any], *, image_id: str, container_id: str, nonce: str
) -> bool:
    return _matches_closed_probe_payload(
        value,
        image_id=image_id,
        container_id=container_id,
        nonce=nonce,
        expected=_closed_probe_payload(image_id, nonce),
    )


def _matches_closed_synthetic_probe(
    value: dict[str, Any], *, image_id: str, container_id: str, nonce: str
) -> bool:
    return _matches_closed_probe_payload(
        value,
        image_id=image_id,
        container_id=container_id,
        nonce=nonce,
        expected=_closed_synthetic_probe_payload(image_id, nonce),
    )


def _matches_closed_loso_offline(
    value: dict[str, Any], *, image_id: str, container_id: str, nonce: str
) -> bool:
    config = value.get("Config")
    expected = _closed_loso_offline_payload(image_id, nonce)
    return (
        _matches_closed_probe_payload(
            value,
            image_id=image_id,
            container_id=container_id,
            nonce=nonce,
            expected=expected,
        )
        and type(config) is dict
        and config.get("OpenStdin") is True
        and config.get("StdinOnce") is True
        and config.get("AttachStdin") is True
        and config.get("AttachStdout") is True
        and config.get("AttachStderr") is True
        and config.get("Tty") is False
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
        self._container_intent_profiles: dict[str, str] = {}
        self._container_profiles: dict[str, str] = {}
        self._image_intents: set[str] = set()
        self._closed_inspected: set[str] = set()
        self._inspected_profiles: dict[str, str] = {}
        self._started: set[str] = set()
        self._started_profiles: dict[str, str] = {}
        self._waited: set[str] = set()
        self._waited_profiles: dict[str, str] = {}

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
        return self._create_closed_probe_container(
            image_id,
            profile=_MATERIALIZATION_PROBE_PROFILE,
            name_prefix="aai-laya-probe-",
            payload_factory=_closed_probe_payload,
        )

    def create_closed_synthetic_probe_container(self, image_id: str) -> str:
        if any(
            (
                self._owned_containers,
                self._owned_images,
                self._removed_containers,
                self._removed_images,
                self._container_intents,
                self._container_intent_profiles,
                self._container_profiles,
                self._image_intents,
                self._closed_inspected,
                self._inspected_profiles,
                self._started,
                self._started_profiles,
                self._waited,
                self._waited_profiles,
            )
        ):
            raise LocalDockerEngineError("local Docker synthetic engine is not fresh")
        return self._create_closed_probe_container(
            image_id,
            profile=_SYNTHETIC_PROBE_PROFILE,
            name_prefix="aai-laya-synthetic-probe-",
            payload_factory=_closed_synthetic_probe_payload,
        )

    def create_closed_loso_offline_container(self, image_id: str) -> str:
        if any(
            (
                self._owned_containers,
                self._owned_images,
                self._removed_containers,
                self._removed_images,
                self._container_intents,
                self._container_intent_profiles,
                self._container_profiles,
                self._image_intents,
                self._closed_inspected,
                self._inspected_profiles,
                self._started,
                self._started_profiles,
                self._waited,
                self._waited_profiles,
            )
        ):
            raise LocalDockerEngineError("local Docker offline engine is not fresh")
        return self._create_closed_probe_container(
            image_id,
            profile=_LOSO_OFFLINE_PROFILE,
            name_prefix="aai-laya-loso-offline-",
            payload_factory=_closed_loso_offline_payload,
        )

    def _create_closed_probe_container(
        self,
        image_id: str,
        *,
        profile: str,
        name_prefix: str,
        payload_factory: object,
    ) -> str:
        image_id = _require_image_id(image_id)
        self._ensure_ready()
        name = name_prefix + secrets.token_hex(16)
        self._container_intents[name] = image_id
        self._container_intent_profiles[name] = profile
        payload = json.dumps(
            payload_factory(image_id, self._nonce),
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
        self._container_profiles[container_id] = profile
        self._container_intents.pop(name, None)
        self._container_intent_profiles.pop(name, None)
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
        profile = self._container_intent_profiles.get(name)
        if profile not in {
            _MATERIALIZATION_PROBE_PROFILE,
            _SYNTHETIC_PROBE_PROFILE,
            _LOSO_OFFLINE_PROFILE,
        }:
            raise LocalDockerEngineError("owned Docker container intent profile is invalid")
        path_name = urllib.parse.quote(name, safe="")
        response = self._request("GET", f"/{DOCKER_API_VERSION}/containers/{path_name}/json")
        if response.status == 404:
            self._container_intents.pop(name, None)
            self._container_intent_profiles.pop(name, None)
            return
        if response.status != 200:
            raise LocalDockerEngineError("owned Docker container intent is unresolved")
        value = _json_object(response.body)
        container_id = _require_container_id(value.get("Id"))
        matcher = {
            _MATERIALIZATION_PROBE_PROFILE: _matches_closed_probe,
            _SYNTHETIC_PROBE_PROFILE: _matches_closed_synthetic_probe,
            _LOSO_OFFLINE_PROFILE: _matches_closed_loso_offline,
        }[profile]
        if not matcher(
            value,
            image_id=image_id,
            container_id=container_id,
            nonce=self._nonce,
        ):
            raise LocalDockerEngineError("local Docker container intent changed")
        self._owned_containers.add(container_id)
        self._container_images[container_id] = image_id
        self._container_profiles[container_id] = profile
        self._container_intents.pop(name, None)
        self._container_intent_profiles.pop(name, None)

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
        return self._inspect_closed_probe_container(
            container_id,
            expected_image_id=expected_image_id,
            profile=_MATERIALIZATION_PROBE_PROFILE,
        )

    def inspect_closed_synthetic_probe_container(
        self, container_id: str, *, expected_image_id: str
    ) -> dict[str, Any]:
        return self._inspect_closed_probe_container(
            container_id,
            expected_image_id=expected_image_id,
            profile=_SYNTHETIC_PROBE_PROFILE,
        )

    def inspect_closed_loso_offline_container(
        self, container_id: str, *, expected_image_id: str
    ) -> dict[str, Any]:
        return self._inspect_closed_probe_container(
            container_id,
            expected_image_id=expected_image_id,
            profile=_LOSO_OFFLINE_PROFILE,
        )

    def _inspect_closed_probe_container(
        self, container_id: str, *, expected_image_id: str, profile: str
    ) -> dict[str, Any]:
        container_id = _require_container_id(container_id)
        image_id = _require_image_id(expected_image_id)
        registered_profile = self._container_profiles.get(container_id)
        if (
            container_id in self._owned_containers
            and registered_profile != profile
            or profile in {_SYNTHETIC_PROBE_PROFILE, _LOSO_OFFLINE_PROFILE}
            and (container_id not in self._owned_containers or registered_profile != profile)
        ):
            raise LocalDockerEngineError("local Docker probe isolation changed")
        value = self.inspect_container(container_id)
        matcher = {
            _MATERIALIZATION_PROBE_PROFILE: _matches_closed_probe,
            _SYNTHETIC_PROBE_PROFILE: _matches_closed_synthetic_probe,
            _LOSO_OFFLINE_PROFILE: _matches_closed_loso_offline,
        }.get(profile)
        if matcher is None:
            raise LocalDockerEngineError("local Docker probe profile is invalid")
        if not matcher(
            value,
            image_id=image_id,
            container_id=container_id,
            nonce=self._nonce,
        ):
            raise LocalDockerEngineError("local Docker probe isolation changed")
        if container_id in self._owned_containers:
            self._closed_inspected.add(container_id)
            self._inspected_profiles[container_id] = profile
        return value

    def export_stopped_container_stream(self, container_id: str) -> DockerByteStream:
        container_id = _require_container_id(container_id)
        image_id = self._container_images.get(container_id)
        if (
            image_id is None
            or container_id not in self._closed_inspected
            or self._inspected_profiles.get(container_id) != _MATERIALIZATION_PROBE_PROFILE
        ):
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
        self._start_probe(container_id, profile=_MATERIALIZATION_PROBE_PROFILE)

    def _start_probe(self, container_id: str, *, profile: str) -> None:
        container_id = _require_container_id(container_id)
        image_id = self._container_images.get(container_id)
        if (
            image_id is None
            or container_id not in self._closed_inspected
            or self._container_profiles.get(container_id) != profile
            or self._inspected_profiles.get(container_id) != profile
        ):
            raise LocalDockerEngineError("local Docker probe was not closed-inspected")
        if container_id in self._started:
            raise LocalDockerEngineError("local Docker probe already started")
        self._inspect_closed_probe_container(
            container_id, expected_image_id=image_id, profile=profile
        )
        response = self._request("POST", f"/{DOCKER_API_VERSION}/containers/{container_id}/start")
        if response.status != 204:
            raise LocalDockerEngineError("local Docker probe start failed")
        self._started.add(container_id)
        self._started_profiles[container_id] = profile

    def wait_probe(self, container_id: str) -> None:
        self._wait_probe(container_id, profile=_MATERIALIZATION_PROBE_PROFILE)

    def _wait_probe(self, container_id: str, *, profile: str) -> None:
        container_id = _require_container_id(container_id)
        if container_id not in self._started or container_id in self._waited:
            raise LocalDockerEngineError("local Docker probe wait state is invalid")
        started_profile = self._started_profiles.get(container_id)
        if started_profile is not None and started_profile != profile:
            raise LocalDockerEngineError("local Docker probe profile changed")
        if profile in {_SYNTHETIC_PROBE_PROFILE, _LOSO_OFFLINE_PROFILE} and (
            started_profile != profile
        ):
            raise LocalDockerEngineError("local Docker probe profile changed")
        value = self._request_json(
            "POST",
            f"/{DOCKER_API_VERSION}/containers/{container_id}/wait?condition=not-running",
            expected_status=200,
            timeout=_PROBE_TIMEOUT_SECONDS,
        )
        error = value.get("Error")
        if value.get("StatusCode") != 0 or error not in (None, {"Message": ""}):
            raise LocalDockerEngineError("local Docker probe failed")
        completed = self.inspect_container(container_id)
        if not _matches_completed_probe_state(completed.get("State")):
            raise LocalDockerEngineError("local Docker completed probe state changed")
        self._waited.add(container_id)
        self._waited_profiles[container_id] = profile

    def probe_logs_bounded(self, container_id: str) -> tuple[bytes, bytes]:
        return self._probe_logs_bounded(container_id, profile=_MATERIALIZATION_PROBE_PROFILE)

    def _probe_logs_bounded(self, container_id: str, *, profile: str) -> tuple[bytes, bytes]:
        container_id = _require_container_id(container_id)
        if container_id not in self._waited:
            raise LocalDockerEngineError("local Docker probe logs are premature")
        waited_profile = self._waited_profiles.get(container_id)
        if waited_profile is not None and waited_profile != profile:
            raise LocalDockerEngineError("local Docker probe profile changed")
        if profile == _SYNTHETIC_PROBE_PROFILE and waited_profile != profile:
            raise LocalDockerEngineError("local Docker probe profile changed")
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

    def run_closed_synthetic_probe(self, container_id: str, *, expected_image_id: str) -> bytes:
        """Run one fixed synthetic probe and return only its canonical observation."""

        self.inspect_closed_synthetic_probe_container(
            container_id, expected_image_id=expected_image_id
        )
        self._start_probe(container_id, profile=_SYNTHETIC_PROBE_PROFILE)
        self._wait_probe(container_id, profile=_SYNTHETIC_PROBE_PROFILE)
        stdout, _stderr = self._probe_logs_bounded(container_id, profile=_SYNTHETIC_PROBE_PROFILE)
        return validate_synthetic_probe_observation(stdout)

    def run_closed_loso_offline(
        self,
        container_id: str,
        *,
        expected_image_id: str,
        canonical_request: bytes,
    ) -> bytes:
        """Run one fixed gold-blind batch through bounded hijacked standard I/O."""

        if type(canonical_request) is not bytes or not 0 < len(canonical_request) <= 64 * 1024:
            raise ValueError("canonical offline request is invalid") from None
        container_id = _require_container_id(container_id)
        image_id = _require_image_id(expected_image_id)
        self.inspect_closed_loso_offline_container(container_id, expected_image_id=image_id)
        path = (
            f"/{DOCKER_API_VERSION}/containers/{container_id}/attach?"
            "stream=1&stdin=1&stdout=1&stderr=1"
        )
        with self._transport.open_attach(
            path,
            stdin_limit=_OFFLINE_STDIN_LIMIT,
            stdout_limit=_OFFLINE_STDOUT_LIMIT,
            stderr_limit=_OFFLINE_STDERR_LIMIT,
            timeout=_OFFLINE_TIMEOUT_SECONDS,
        ) as session:
            self._start_probe(container_id, profile=_LOSO_OFFLINE_PROFILE)
            stdout, stderr = session.exchange(canonical_request)
        self._wait_probe(container_id, profile=_LOSO_OFFLINE_PROFILE)
        if type(stdout) is not bytes or not stdout or len(stdout) > _OFFLINE_STDOUT_LIMIT or stderr:
            raise LocalDockerEngineError("local Docker offline output is invalid")
        return stdout

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
            self._container_profiles.pop(container_id, None)
            self._closed_inspected.discard(container_id)
            self._inspected_profiles.pop(container_id, None)
            self._started.discard(container_id)
            self._started_profiles.pop(container_id, None)
            self._waited.discard(container_id)
            self._waited_profiles.pop(container_id, None)
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
        self._container_profiles.pop(container_id, None)
        self._closed_inspected.discard(container_id)
        self._inspected_profiles.pop(container_id, None)
        self._started.discard(container_id)
        self._started_profiles.pop(container_id, None)
        self._waited.discard(container_id)
        self._waited_profiles.pop(container_id, None)
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
