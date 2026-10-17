"""Regular-file reads can be shorter than requested, including on virtiofs."""

import io

from human_feedback.adapters import filesystem_checkpoint as filesystem


def test_checkpoint_capture_coalesces_short_reads_without_raising_chunk_budget(monkeypatch):
    source = io.BytesIO(bytes(range(100)))
    requests = []

    def short_read(descriptor, size):
        assert descriptor == 23
        requests.append(size)
        return source.read(min(size, 3))

    monkeypatch.setattr(filesystem.os, "read", short_read)
    monkeypatch.setattr(filesystem.runtime_checkpoint, "MAX_CHECKPOINT_CHUNK_BYTES", 16)
    chunks = tuple(filesystem._file_chunks(23, 64))
    assert tuple(map(len, chunks)) == (16, 16, 16, 16, 1)
    assert b"".join(chunks) == bytes(range(65))
    assert max(requests) <= 16
    assert source.tell() == 65  # preserve exactly one overflow-detection byte


def test_checkpoint_capture_preserves_short_final_chunk_and_eof(monkeypatch):
    source = io.BytesIO(b"abcde")
    monkeypatch.setattr(filesystem.os, "read", lambda descriptor, size: source.read(min(size, 2)))
    monkeypatch.setattr(filesystem.runtime_checkpoint, "MAX_CHECKPOINT_CHUNK_BYTES", 16)
    assert tuple(filesystem._file_chunks(23, 64)) == (b"abcde",)
