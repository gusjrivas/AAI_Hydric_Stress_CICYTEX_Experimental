"""Independent bounded TAR observations for derived-image content recapture.

No extraction, execution or child-supplied digest is used.  Hardlinks are
canonicalized by their equivalence class because Docker can choose a different
first member when exporting the same inode.  Linux symlink modes are always 777.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from human_feedback import runtime_oci_tar as _tar

_EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()
_GENERATED_FILES = {
    ".dockerenv": 0o755,
    "etc/hosts": 0o644,
    "etc/hostname": 0o644,
    "etc/resolv.conf": 0o644,
}
_GENERATED_DIRECTORIES = {"dev", "proc", "sys"}


def _fail() -> None:
    error = ValueError("runtime installation recapture failed")
    error.__suppress_context__ = True
    raise error from None


@dataclass(frozen=True, slots=True, repr=False)
class _InstallationManifest:
    records: tuple[tuple[object, ...], ...]
    commitment_sha256: str

    def __repr__(self) -> str:
        return "<private verified runtime installation manifest>"


class _PayloadHashes:
    def __init__(self):
        self.hashes: dict[str, str] = {}
        self._path = None
        self._digest = None

    def start(self, entry):
        if self._path is not None:
            _fail()
        self._path = entry.path
        self._digest = hashlib.sha256()

    def chunk(self, payload):
        if self._digest is None:
            _fail()
        self._digest.update(payload)

    def end(self):
        if self._path is None or self._digest is None:
            _fail()
        self.hashes[self._path] = self._digest.hexdigest()
        self._path = self._digest = None


def _records(entries, hashes) -> tuple[tuple[object, ...], ...]:
    namespace = {item.path: item for item in entries}
    groups: dict[str, list[str]] = {}
    terminal_paths = {}
    for entry in entries:
        if entry.typeflag not in {"0", "1"}:
            continue
        terminal = entry
        visited = set()
        while terminal.typeflag == "1":
            if terminal.path in visited or terminal.link_target not in namespace:
                _fail()
            visited.add(terminal.path)
            terminal = namespace[terminal.link_target]
        if terminal.typeflag != "0":
            _fail()
        terminal_paths[entry.path] = terminal.path
        groups.setdefault(terminal.path, []).append(entry.path)
    records = []
    for entry in entries:
        parent = entry.path.rpartition("/")[0]
        if parent and (parent not in namespace or namespace[parent].typeflag != "5"):
            _fail()
        kind = entry.typeflag
        if kind in {"0", "1"}:
            terminal_path = terminal_paths[entry.path]
            terminal = namespace[terminal_path]
            if (entry.uid, entry.gid, entry.mode) != (terminal.uid, terminal.gid, terminal.mode):
                _fail()
            payload = (
                terminal.size_bytes,
                hashes[terminal_path],
                tuple(sorted(groups[terminal_path])),
            )
            kind = "0"
        elif kind == "2":
            payload = (entry.link_target,)
        elif kind == "5":
            payload = ()
        else:
            _fail()
        records.append(
            (
                entry.path,
                kind,
                0o777 if kind == "2" else entry.mode,
                entry.uid,
                entry.gid,
                entry.mtime,
                payload,
            )
        )
    return tuple(sorted(records))


def _manifest(records) -> _InstallationManifest:
    encoded = json.dumps(records, ensure_ascii=True, separators=(",", ":")).encode("ascii")
    return _InstallationManifest(
        records, hashlib.sha256(b"laya-installation-v1\0" + encoded).hexdigest()
    )


class _InstallationTarObservation:
    """Tee exactly the accepted bytes into a caller-owned bounded writer."""

    def __init__(self, writer=None):
        self._writer = writer
        self._hashes = _PayloadHashes()
        self._parser = _tar._TarParser(_tar.MAX_OCI_TAR_ENTRIES, self._hashes)
        self._pending = bytearray()
        self._closed = False

    def write(self, payload):
        if self._closed:
            _fail()
        try:
            data = bytes(payload)
            if not data or len(data) > _tar.MAX_OCI_TAR_CHUNK_BYTES:
                _fail()
            count = len(data) if self._writer is None else self._writer.write(data)
            if type(count) is not int or not 0 < count <= len(data):
                _fail()
            self._pending.extend(data[:count])
            if len(self._pending) >= _tar.MAX_OCI_TAR_CHUNK_BYTES:
                self._parser.feed(bytes(self._pending[: _tar.MAX_OCI_TAR_CHUNK_BYTES]))
                del self._pending[: _tar.MAX_OCI_TAR_CHUNK_BYTES]
            return count
        except Exception:
            self._closed = True
            _fail()

    def _finish_records(self):
        if self._closed:
            _fail()
        self._closed = True
        try:
            if self._pending:
                self._parser.feed(bytes(self._pending))
                self._pending.clear()
            entries, _, _, root = self._parser.finish()
            if (
                not entries
                or root is not None
                and (root.typeflag != "5" or root.uid != 0 or root.gid != 0)
            ):
                _fail()
            return _records(entries, self._hashes.hashes)
        except Exception:
            _fail()

    def finish(self):
        records = self._finish_records()
        if any(item[0] == ".dockerenv" or item[3:6] != (65532, 65532, 0) for item in records):
            _fail()
        return _manifest(records)


def _capture_installation_tar(chunks) -> _InstallationManifest:
    observer = _InstallationTarObservation()
    try:
        for chunk in chunks:
            observer.write(chunk)
        return observer.finish()
    except Exception:
        _fail()


def _verify_exported_installation(chunks, expected: _InstallationManifest) -> str:
    try:
        if type(expected) is not _InstallationManifest or _manifest(expected.records) != expected:
            _fail()
        observer = _InstallationTarObservation()
        for chunk in chunks:
            observer.write(chunk)
        actual = observer._finish_records()
        original_paths = {item[0] for item in expected.records}
        retained = []
        for item in actual:
            if item[0] in original_paths:
                retained.append(item)
                continue
            path, kind, mode, uid, gid, _mtime, payload = item
            if (uid, gid) != (0, 0):
                _fail()
            if path in _GENERATED_FILES:
                if (kind, mode, payload) != (
                    "0",
                    _GENERATED_FILES[path],
                    (0, _EMPTY_SHA256, (path,)),
                ):
                    _fail()
            elif path in _GENERATED_DIRECTORIES:
                if (kind, mode, payload) != ("5", 0o755, ()):
                    _fail()
            else:
                _fail()
        if tuple(retained) != expected.records:
            _fail()
        return expected.commitment_sha256
    except Exception:
        _fail()
