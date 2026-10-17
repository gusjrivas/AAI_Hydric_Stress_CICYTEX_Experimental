"""TDD contract for streaming regular TAR payloads into PR39 materialization."""

from __future__ import annotations

import traceback

import pytest

from tests.test_laya_runtime_oci_tar import (
    _archive,
    _chunks,
    _gnu_extension,
    _install_bridge,
    _pax_entry,
    _synthetic_pr22_evidence,
    _tar_entry,
)


@pytest.fixture
def synthetic_pr22(monkeypatch):
    from human_feedback import runtime_oci_layers

    evidence = _synthetic_pr22_evidence()
    calls = []

    def deep_validate(candidate):
        calls.append(candidate)
        if candidate is not evidence:
            raise ValueError("invalid layer evidence") from None
        return b'{"schema_version":"laya-runtime-oci-layer-diff-ids-evidence-v1"}\n'

    monkeypatch.setattr(
        runtime_oci_layers,
        "canonical_laya_runtime_oci_layer_diff_ids_summary_bytes",
        deep_validate,
    )
    return evidence, calls


class _RecordingSink:
    def __init__(self) -> None:
        self.events = []

    def start(self, entry) -> None:
        self.events.append(("start", entry))

    def chunk(self, payload: bytes) -> None:
        self.events.append(("chunk", payload))

    def end(self) -> None:
        self.events.append(("end",))


def _verify_with_sink(monkeypatch, synthetic_pr22, archive, sink, *, width=37):
    from human_feedback import runtime_oci_tar as module

    evidence, _calls = synthetic_pr22
    plan = module.prepare_laya_oci_tar_semantics_plan(evidence)
    historical = evidence.receipts[0]
    object.__setattr__(historical, "uncompressed_size_bytes", len(archive))
    bridge_calls = _install_bridge(monkeypatch, module, historical)
    receipt = module._verify_laya_oci_tar_semantics_chunks_with_budget(
        plan,
        historical.layer_blob.digest,
        _chunks(archive, width),
        max_uncompressed_bytes=len(archive),
        _payload_sink=sink,
    )
    return receipt, bridge_calls


def test_regular_payloads_stream_in_order_and_include_empty_files(monkeypatch, synthetic_pr22):
    archive = _archive(
        _tar_entry("data/empty.bin"),
        _tar_entry("data/value.bin", b"abcdefghij"),
        _tar_entry("data", typeflag=b"5"),
        _tar_entry("data/symlink", typeflag=b"2", linkname="value.bin"),
        _tar_entry("data/hardlink", typeflag=b"1", linkname="data/value.bin"),
    )
    sink = _RecordingSink()

    receipt, bridge_calls = _verify_with_sink(monkeypatch, synthetic_pr22, archive, sink, width=7)

    starts = [event[1] for event in sink.events if event[0] == "start"]
    assert [(entry.path, entry.typeflag, entry.size_bytes) for entry in starts] == [
        ("data/empty.bin", "0", 0),
        ("data/value.bin", "0", 10),
    ]
    assert [event[0] for event in sink.events].count("end") == 2
    assert b"".join(event[1] for event in sink.events if event[0] == "chunk") == b"abcdefghij"
    assert all(type(event[1]) is bytes for event in sink.events if event[0] == "chunk")
    assert len(bridge_calls) == 1
    assert receipt.payload_size_bytes == 10
    assert tuple(entry.path for entry in receipt.entries) == (
        "data/empty.bin",
        "data/value.bin",
        "data",
        "data/symlink",
        "data/hardlink",
    )


@pytest.mark.parametrize("profile", ("pax", "gnu"))
def test_extension_payloads_are_never_forwarded_to_regular_payload_sink(
    monkeypatch, synthetic_pr22, profile
):
    effective_path = f"long/{'x' * 120}"
    extension = (
        _pax_entry((("path", effective_path),))
        if profile == "pax"
        else _gnu_extension(effective_path)
    )
    archive = _archive(extension, _tar_entry("raw", b"science", gnu=profile == "gnu"))
    sink = _RecordingSink()

    receipt, _bridge_calls = _verify_with_sink(monkeypatch, synthetic_pr22, archive, sink, width=11)

    starts = [event[1] for event in sink.events if event[0] == "start"]
    assert [(entry.path, entry.size_bytes) for entry in starts] == [(effective_path, 7)]
    assert b"".join(event[1] for event in sink.events if event[0] == "chunk") == b"science"
    assert sink.events[0][0] == "start"
    assert sink.events[-1][0] == "end"
    assert all(event[0] == "chunk" for event in sink.events[1:-1])
    assert receipt.entries[0] is starts[0]


def test_callback_failure_aborts_before_any_verified_receipt_is_returned(
    monkeypatch, synthetic_pr22
):
    from human_feedback import runtime_oci_tar as module

    class FailingSink(_RecordingSink):
        def chunk(self, payload: bytes) -> None:
            raise RuntimeError("private-streaming-sentinel")

    archive = _archive(_tar_entry("private/value.bin", b"secret"))
    evidence, _calls = synthetic_pr22
    plan = module.prepare_laya_oci_tar_semantics_plan(evidence)
    historical = evidence.receipts[0]
    object.__setattr__(historical, "uncompressed_size_bytes", len(archive))
    bridge_calls = _install_bridge(monkeypatch, module, historical)

    with pytest.raises(ValueError) as captured:
        module._verify_laya_oci_tar_semantics_chunks_with_budget(
            plan,
            historical.layer_blob.digest,
            _chunks(archive, 5),
            max_uncompressed_bytes=len(archive),
            _payload_sink=FailingSink(),
        )

    rendered = "".join(traceback.format_exception(captured.value))
    assert "private-streaming-sentinel" not in rendered
    assert "private/value.bin" not in rendered
    assert captured.value.__cause__ is None
    assert captured.value.__context__ is None
    assert captured.value.__suppress_context__ is True
    assert bridge_calls == []
