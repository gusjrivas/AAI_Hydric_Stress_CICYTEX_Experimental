"""Opt-in real Engine mechanics; deliberately no model or scientific inference."""

import io
import os
import secrets
import sys
import tarfile

import pytest

pytestmark = pytest.mark.skipif(
    not sys.platform.startswith("linux") or os.environ.get("LAYA_LOCAL_DOCKER_LIVE") != "1",
    reason="explicit local trusted Docker daemon gate",
)


def test_real_engine_import_inspect_export_and_owned_cleanup():
    from human_feedback.adapters.local_docker_engine import LocalDockerEngine
    from human_feedback.adapters.runtime_installation_verifier import (
        _capture_installation_tar,
        _verify_exported_installation,
    )

    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w", format=tarfile.GNU_FORMAT) as archive:
        for path in ("dev", "etc", "opt", "opt/laya-runtime", "proc", "sys"):
            info = tarfile.TarInfo(path)
            info.type = tarfile.DIRTYPE
            info.mode = 0o700
            info.uid = info.gid = 65532
            archive.addfile(info)
        for path in ("etc/hostname", "etc/hosts", "etc/resolv.conf"):
            info = tarfile.TarInfo(path)
            info.mode = 0o755
            info.uid = info.gid = 0
            info.mtime = 0
            info.size = 0
            archive.addfile(info, io.BytesIO())
        info = tarfile.TarInfo("opt/laya-runtime/synthetic-marker")
        info.mode = 0o600
        info.uid = info.gid = 65532
        info.size = 6
        archive.addfile(info, io.BytesIO(b"marker"))
    payload = output.getvalue()
    expected = _capture_installation_tar([payload])
    engine = LocalDockerEngine(secrets.token_hex(32))
    image_id = container_id = None

    def produce(writer):
        count = 0
        while count < len(payload):
            count += writer.write(payload[count:])
        return count

    try:
        image_id = engine.import_normalized_image(produce)
        container_id = engine.create_closed_probe_container(image_id)
        engine.inspect_closed_probe_container(container_id, expected_image_id=image_id)
        with engine.export_stopped_container_stream(container_id) as chunks:
            # This fixture is <64 KiB; production recapture is always streaming.
            exported = b"".join(chunks)
            assert len(exported) < 65536
            with tarfile.open(fileobj=io.BytesIO(exported)) as archive:
                diagnostic = [
                    (x.name, x.type, x.mode, x.uid, x.gid, x.mtime, x.size, x.linkname)
                    for x in archive
                ]
            try:
                assert (
                    _verify_exported_installation([exported], expected)
                    == expected.commitment_sha256
                )
            except ValueError:
                pytest.fail(f"synthetic export metadata: {diagnostic!r}")
    finally:
        if container_id is not None:
            engine.remove_owned_container(container_id)
        if image_id is not None:
            engine.remove_owned_image(image_id)
