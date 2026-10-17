"""Opt-in real Docker stdin transport gate, not a Laya/model evaluation.

The trusted orchestration helper may access the daemon. Its disposable child
has no socket, mounts, network, scientific data, or Laya model. Only fixed
synthetic bytes cross stdin; the child returns their size and SHA-256.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import sys

import pytest

_IMAGE = "sha256:90d42f3d776d8d3434982bd00bd815166d496dd3195cea2fa6b6bbcb0d934475"
_PROGRAM = (
    "import hashlib,json,sys; data=sys.stdin.buffer.read(65537); "
    "assert len(data)<=65536; "
    "print(json.dumps({'size':len(data),'sha256':hashlib.sha256(data).hexdigest()},"
    "sort_keys=True,separators=(',',':')))"
)


@pytest.mark.skipif(
    os.environ.get("LAYA_LOSO_ATTACH_LIVE") != "1" or sys.platform != "linux",
    reason="requires explicitly enabled Linux Docker transport gate",
)
@pytest.mark.parametrize(
    "payload",
    ("Synthetic stdin fixture: ñ".encode(), b"X" * 65536),
    ids=("unicode", "maximum-stdin"),
)
def test_real_attach_round_trip_is_bounded_and_disposes_only_its_child(payload):
    from human_feedback.adapters.local_docker_engine import (
        DOCKER_API_VERSION,
        _LocalUnixTransport,
    )

    transport = _LocalUnixTransport()
    prefix = f"/{DOCKER_API_VERSION}"
    nonce = secrets.token_hex(16)
    name = "aai-laya-loso-attach-test-" + nonce
    label = "aai.laya.loso.attach-fixture"
    container_id = None

    def request(method, path, *, body=None):
        return transport.request(
            method,
            path,
            body=body,
            headers={"Content-Type": "application/json"} if body is not None else {},
            response_limit=1024 * 1024,
            timeout=30.0,
        )

    configuration = {
        "Image": _IMAGE,
        "Cmd": ["python", "-I", "-B", "-c", _PROGRAM],
        "User": "65534:65534",
        "WorkingDir": "/tmp",
        "OpenStdin": True,
        "StdinOnce": True,
        "AttachStdin": True,
        "AttachStdout": True,
        "AttachStderr": True,
        "Tty": False,
        "Labels": {label: nonce},
        "HostConfig": {
            "NetworkMode": "none",
            "ReadonlyRootfs": True,
            "CapDrop": ["ALL"],
            "SecurityOpt": ["no-new-privileges:true"],
            "PidsLimit": 32,
            "Memory": 128 * 1024 * 1024,
            "LogConfig": {"Type": "none", "Config": {}},
        },
    }
    try:
        created = request(
            "POST",
            f"{prefix}/containers/create?name={name}",
            body=json.dumps(configuration).encode(),
        )
        assert created.status == 201
        container_id = json.loads(created.body)["Id"]
        assert re.fullmatch(r"[0-9a-f]{64}", container_id)
        with transport.open_attach(
            f"{prefix}/containers/{container_id}/attach?" "stream=1&stdin=1&stdout=1&stderr=1",
            stdin_limit=65536,
            stdout_limit=65536,
            stderr_limit=8192,
            timeout=30.0,
        ) as attached:
            assert request("POST", f"{prefix}/containers/{container_id}/start").status == 204
            stdout, stderr = attached.exchange(payload)
        assert stderr == b""
        assert json.loads(stdout) == {
            "size": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
        }
        waited = request("POST", f"{prefix}/containers/{container_id}/wait?condition=not-running")
        assert waited.status == 200
        assert json.loads(waited.body)["StatusCode"] == 0
    finally:
        # Reconcile by our unique name even if create's response was lost.
        inspected = request("GET", f"{prefix}/containers/{name}/json")
        if inspected.status != 404:
            assert inspected.status == 200
            details = json.loads(inspected.body)
            assert details["Config"]["Labels"].get(label) == nonce
            assert details["Image"] == _IMAGE
            if container_id is not None:
                assert details["Id"] == container_id
            assert request("DELETE", f"{prefix}/containers/{details['Id']}?force=1").status == 204
        assert request("GET", f"{prefix}/containers/{name}/json").status == 404
