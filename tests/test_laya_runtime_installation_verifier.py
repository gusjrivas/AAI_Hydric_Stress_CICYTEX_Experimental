"""Trusted streaming recapture does not accept the child's own content assertions."""

import hashlib
import io
import tarfile

import pytest

_PROJECTED_PATHS = ("etc/hosts", "etc/hostname", "etc/resolv.conf")


def _tar(
    *,
    changed=False,
    extra=None,
    flatten=False,
    symlink=False,
    projected=True,
    projection_damage=None,
):
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w", format=tarfile.GNU_FORMAT) as archive:
        entries = [("app", "5", b""), ("app/model", "0", b"wrong" if changed else b"model")]
        entries += [("app/link", "0" if flatten else "1", b"model" if flatten else b"")]
        entries += [("app/sym", "2", b"")]
        entries += [("etc", "5", b"")]
        if projected:
            entries += [(path, "0", b"") for path in _PROJECTED_PATHS]
        if extra is not None:
            entries.append((extra, "0", b""))
        for path, kind, payload in entries:
            info = tarfile.TarInfo(path)
            info.type = kind.encode("ascii")
            info.uid = info.gid = 65532
            info.mode = 0o700 if kind == "5" else 0o600
            if path in _PROJECTED_PATHS:
                info.uid = info.gid = 0
                info.mode = 0o755
                if projection_damage == "payload" and path == "etc/hosts":
                    payload = b"tampered"
                elif projection_damage == "owner" and path == "etc/hosts":
                    info.uid = 65532
                elif projection_damage == "mode" and path == "etc/hosts":
                    info.mode = 0o644
                elif projection_damage == "type" and path == "etc/hosts":
                    info.type = tarfile.SYMTYPE
                    info.linkname = "elsewhere"
                elif projection_damage == "link" and path == "etc/hosts":
                    info.type = tarfile.LNKTYPE
                    info.linkname = "app/model"
                elif projection_damage == "mtime":
                    info.mtime = 123
            if path == "app/link":
                info.linkname = "app/model" if not flatten else ""
            if path == "app/sym":
                info.linkname = "elsewhere" if symlink else "model"
            if extra == path:
                info.uid = info.gid = 0
                info.mode = 0o755
            info.size = len(payload)
            archive.addfile(info, io.BytesIO(payload))
    return output.getvalue()


def _chunks(value):
    return (value[start : start + 173] for start in range(0, len(value), 173))


def test_export_recapture_matches_bytes_links_and_private_commitment():
    from human_feedback.adapters import runtime_installation_verifier as verifier

    expected = verifier._capture_installation_tar(_chunks(_tar()))
    digest = verifier._verify_exported_installation(_chunks(_tar()), expected)
    assert len(digest) == 64
    assert digest == expected.commitment_sha256
    assert b"model" not in repr(expected).encode()
    assert hashlib.sha256(b"model").hexdigest() not in repr(expected)


@pytest.mark.parametrize(
    "override",
    [
        {"changed": True},
        {"flatten": True},
        {"symlink": True},
        {"extra": "unexpected"},
    ],
)
def test_export_cannot_change_payload_topology_or_namespace(override):
    from human_feedback.adapters import runtime_installation_verifier as verifier

    expected = verifier._capture_installation_tar(_chunks(_tar()))
    with pytest.raises(ValueError, match="recapture"):
        verifier._verify_exported_installation(_chunks(_tar(**override)), expected)


def test_only_exact_empty_engine_marker_is_permitted():
    from human_feedback.adapters import runtime_installation_verifier as verifier

    expected = verifier._capture_installation_tar(_chunks(_tar()))
    assert (
        verifier._verify_exported_installation(_chunks(_tar(extra=".dockerenv")), expected)
        == expected.commitment_sha256
    )
    with pytest.raises(ValueError):
        verifier._capture_installation_tar(_chunks(_tar(extra=".dockerenv")))


def test_capture_requires_exact_three_projected_engine_files():
    from human_feedback.adapters import runtime_installation_verifier as verifier

    expected = verifier._capture_installation_tar(_chunks(_tar()))
    assert all(any(record[0] == path for record in expected.records) for path in _PROJECTED_PATHS)
    with pytest.raises(ValueError, match="recapture"):
        verifier._capture_installation_tar(_chunks(_tar(projected=False)))


@pytest.mark.parametrize("damage", ["payload", "owner", "mode", "type", "link"])
def test_capture_rejects_noncanonical_projected_engine_files(damage):
    from human_feedback.adapters import runtime_installation_verifier as verifier

    with pytest.raises(ValueError, match="recapture"):
        verifier._capture_installation_tar(_chunks(_tar(projection_damage=damage)))


@pytest.mark.parametrize("damage", ["payload", "owner", "mode", "type", "link"])
def test_export_rejects_changes_to_projected_engine_files(damage):
    from human_feedback.adapters import runtime_installation_verifier as verifier

    expected = verifier._capture_installation_tar(_chunks(_tar()))
    with pytest.raises(ValueError, match="recapture"):
        verifier._verify_exported_installation(
            _chunks(_tar(projection_damage=damage)), expected
        )


def test_export_normalizes_only_projected_file_mtime():
    from human_feedback.adapters import runtime_installation_verifier as verifier

    expected = verifier._capture_installation_tar(_chunks(_tar()))
    assert (
        verifier._verify_exported_installation(
            _chunks(_tar(projection_damage="mtime")), expected
        )
        == expected.commitment_sha256
    )


def test_export_does_not_normalize_against_a_forged_incomplete_projection():
    from human_feedback.adapters import runtime_installation_verifier as verifier

    expected = verifier._capture_installation_tar(_chunks(_tar()))
    forged = verifier._manifest(
        tuple(record for record in expected.records if record[0] != "etc/hosts")
    )
    with pytest.raises(ValueError, match="recapture"):
        verifier._verify_exported_installation(_chunks(_tar()), forged)


def test_fourth_root_owned_projected_file_is_not_permitted():
    from human_feedback.adapters import runtime_installation_verifier as verifier

    with pytest.raises(ValueError, match="recapture"):
        verifier._capture_installation_tar(_chunks(_tar(extra="etc/fourth")))
    expected = verifier._capture_installation_tar(_chunks(_tar()))
    with pytest.raises(ValueError, match="recapture"):
        verifier._verify_exported_installation(
            _chunks(_tar(extra="etc/fourth")), expected
        )


@pytest.mark.parametrize("damage", ["truncated", "tail", "checksum", "duplicate"])
def test_recapture_rejects_malformed_or_ambiguous_tar(damage):
    from human_feedback.adapters import runtime_installation_verifier as verifier

    value = _tar()
    if damage == "truncated":
        value = value[:513]
    elif damage == "tail":
        value += b"X" * 512
    elif damage == "checksum":
        value = b"X" + value[1:]
    else:
        value = value[:512] + value[:512] + value[512:]
    with pytest.raises(ValueError):
        verifier._capture_installation_tar(_chunks(value))


def test_observer_tee_short_writes_and_closed_state():
    from human_feedback.adapters import runtime_installation_verifier as verifier

    class ShortWriter:
        def __init__(self):
            self.data = bytearray()

        def write(self, payload):
            self.data.extend(payload[:23])
            return min(len(payload), 23)

    target = ShortWriter()
    tee = verifier._InstallationTarObservation(target)
    value = _tar()
    for chunk in _chunks(value):
        offset = 0
        while offset < len(chunk):
            offset += tee.write(memoryview(chunk)[offset:])
    expected = tee.finish()
    assert bytes(target.data) == value
    assert (
        expected.commitment_sha256
        == verifier._capture_installation_tar(_chunks(value)).commitment_sha256
    )
    with pytest.raises(ValueError):
        tee.write(b"x")
    with pytest.raises(ValueError):
        tee.finish()


def test_valid_many_small_writes_do_not_exhaust_chunk_budget():
    from human_feedback.adapters import runtime_installation_verifier as verifier

    observer = verifier._InstallationTarObservation()
    value = _tar()
    for byte in value:
        observer.write(bytes([byte]))
    assert (
        observer.finish().commitment_sha256
        == verifier._capture_installation_tar([value]).commitment_sha256
    )
