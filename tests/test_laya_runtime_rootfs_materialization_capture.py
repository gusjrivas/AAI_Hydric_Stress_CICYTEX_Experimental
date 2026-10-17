"""TDD seam for binding streamed layer payloads to exact PR33 TAR receipts."""

from __future__ import annotations

from types import SimpleNamespace

import pytest


def _receipt(position: int):
    return SimpleNamespace(
        layer_position=position,
        entries=(SimpleNamespace(path=f"file-{position}"),),
        root_directory=None,
        payload_size_bytes=position + 10,
        tar_size_bytes=position + 100,
        layer_receipt=SimpleNamespace(
            layer_position=position,
            uncompressed_size_bytes=position + 1,
        ),
    )


def _capture_harness(
    monkeypatch,
    *,
    sink_factory=None,
    expected=None,
    receipt_mutation=None,
):
    from human_feedback.adapters import filesystem_oci_layout as module

    layer_blobs = tuple(
        SimpleNamespace(
            role=f"layer-{position:02d}",
            digest=f"sha256:{position + 10:064x}",
            size_bytes=100 + position,
        )
        for position in range(10)
    )
    layout_plan = SimpleNamespace(
        oci_evidence=object(),
        blobs=layer_blobs,
    )
    tar_plan = SimpleNamespace(
        layout_plan=layout_plan,
        layer_plan=SimpleNamespace(layer_blobs=layer_blobs),
    )
    opened_positions = []
    verify_calls = []
    seal_calls = []
    descriptor_positions = {}
    fingerprints = {
        blob.role: (1, position + 20, blob.size_bytes) for position, blob in enumerate(layer_blobs)
    }

    monkeypatch.setattr(
        module, "_open_root_directory", lambda _components, owned: owned.append(1) or 1
    )
    monkeypatch.setattr(module, "_require_directory", lambda descriptor: (descriptor,))
    monkeypatch.setattr(
        module,
        "_capture_control",
        lambda _root, name, _maximum, _owned: (name.encode(), (2, len(name))),
    )
    monkeypatch.setattr(
        module.runtime_oci_layout,
        "prepare_laya_oci_layout_plan",
        lambda *_args: layout_plan,
    )
    monkeypatch.setattr(
        module,
        "_open_directory",
        lambda _parent, name, owned: owned.append(2 if name == "blobs" else 3) or owned[-1],
    )
    monkeypatch.setattr(module, "_verify_exact_laya_oci_layout_inventory", lambda *_args: None)
    monkeypatch.setattr(
        module,
        "_rehash_blob_for_layer_capture",
        lambda _sha, _plan, blob, _owned: fingerprints[blob.role],
    )

    def path_fingerprint(_parent, name, _owned, **_kwargs):
        blob = next(
            (item for item in layer_blobs if item.digest.removeprefix("sha256:") == name),
            None,
        )
        return fingerprints[blob.role] if blob is not None else (2, len(name))

    monkeypatch.setattr(module, "_path_fingerprint", path_fingerprint)

    def open_file(_parent, name, owned):
        position = next(
            index
            for index, blob in enumerate(layer_blobs)
            if blob.digest.removeprefix("sha256:") == name
        )
        descriptor = 100 + position
        descriptor_positions[descriptor] = position
        opened_positions.append(position)
        owned.append(descriptor)
        return descriptor

    monkeypatch.setattr(module, "_open_file", open_file)
    monkeypatch.setattr(
        module.os, "fstat", lambda descriptor: SimpleNamespace(descriptor=descriptor)
    )
    monkeypatch.setattr(module, "_require_file", lambda *_args: None)
    monkeypatch.setattr(
        module,
        "_fingerprint",
        lambda value: fingerprints[f"layer-{descriptor_positions[value.descriptor]:02d}"],
    )
    monkeypatch.setattr(module, "_blob_chunks", lambda *_args: (b"bounded",))

    def verify(_plan, digest, chunks, *, max_uncompressed_bytes, **kwargs):
        position = next(index for index, blob in enumerate(layer_blobs) if blob.digest == digest)
        assert tuple(chunks) == (b"bounded",)
        verify_calls.append((position, max_uncompressed_bytes, kwargs))
        receipt = _receipt(position)
        if receipt_mutation is not None and position == receipt_mutation[0]:
            setattr(receipt, receipt_mutation[1], receipt_mutation[2])
        return receipt

    monkeypatch.setattr(
        module.runtime_oci_tar,
        "_verify_laya_oci_tar_semantics_chunks_with_budget",
        verify,
    )

    def close_descriptor(owned, descriptor):
        owned.remove(descriptor)

    monkeypatch.setattr(module, "_close_descriptor", close_descriptor)
    monkeypatch.setattr(module, "_verify_laya_oci_layout_final_sweep", lambda *_args: None)
    monkeypatch.setattr(module, "_close_owned_once", lambda owned: owned.clear())

    def seal_authority(*_args, **_kwargs):
        seal_calls.append("authority")
        return object()

    def seal_evidence(*_args, **_kwargs):
        seal_calls.append("evidence")
        return "sealed"

    monkeypatch.setattr(
        module.runtime_oci_tar,
        "_seal_laya_oci_tar_semantics_capture_authority",
        seal_authority,
    )
    monkeypatch.setattr(
        module.runtime_oci_tar,
        "_seal_laya_runtime_oci_tar_semantics_evidence",
        seal_evidence,
    )

    error = result = None
    try:
        result = module._capture_and_verify_tar_semantics(
            tar_plan,
            ("private", "layout"),
            _payload_sink_factory=sink_factory,
            _expected_tar_receipts=expected,
        )
    except Exception as captured:
        error = captured
    return SimpleNamespace(
        result=result,
        error=error,
        opened_positions=opened_positions,
        verify_calls=verify_calls,
        seal_calls=seal_calls,
    )


def test_payload_sink_factory_is_position_bound_and_forwarded_per_layer(monkeypatch):
    sinks = tuple(object() for _position in range(10))
    factory_calls = []

    def factory(position):
        factory_calls.append(position)
        return sinks[position]

    observed = _capture_harness(monkeypatch, sink_factory=factory)

    assert observed.error is None
    assert observed.result == "sealed"
    assert factory_calls == list(range(10))
    assert [call[0] for call in observed.verify_calls] == list(range(10))
    assert [call[2] for call in observed.verify_calls] == [
        {"_payload_sink": sinks[position]} for position in range(10)
    ]


def test_historical_capture_omits_payload_sink_keyword_when_factory_is_absent(monkeypatch):
    observed = _capture_harness(monkeypatch)

    assert observed.error is None
    assert [call[2] for call in observed.verify_calls] == [{} for _position in range(10)]


@pytest.mark.parametrize(
    "invalid",
    ([], (), tuple(_receipt(position) for position in range(9))),
)
def test_expected_receipts_must_be_an_exact_ten_item_tuple_before_open(monkeypatch, invalid):
    observed = _capture_harness(monkeypatch, expected=invalid)

    assert isinstance(observed.error, (TypeError, ValueError))
    assert observed.opened_positions == []
    assert observed.verify_calls == []
    assert observed.seal_calls == []


@pytest.mark.parametrize(
    ("field_name", "invalid"),
    (
        ("layer_position", 9),
        ("entries", (SimpleNamespace(path="forged"),)),
        ("root_directory", SimpleNamespace(path=".")),
        ("payload_size_bytes", 999),
        ("tar_size_bytes", 999),
        ("layer_receipt", SimpleNamespace(uncompressed_size_bytes=1)),
    ),
)
def test_receipt_mismatch_aborts_before_opening_the_next_layer_or_sealing(
    monkeypatch, field_name, invalid
):
    expected = tuple(_receipt(position) for position in range(10))
    observed = _capture_harness(
        monkeypatch,
        expected=expected,
        receipt_mutation=(3, field_name, invalid),
    )

    assert isinstance(observed.error, (TypeError, ValueError))
    assert observed.opened_positions == [0, 1, 2, 3]
    assert [call[0] for call in observed.verify_calls] == [0, 1, 2, 3]
    assert observed.seal_calls == []
