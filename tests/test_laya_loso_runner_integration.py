"""Mechanical wiring of the LOSO runner to the concrete Docker port.

Only synthetic unit authorities and a fake Docker backend are used.  The real
runner, port, byte codec, runtime lease, and fixed probe contract stay in the
path; no daemon, model, corpus evaluation, fitting, scoring, or scientific
authority is involved.
"""

from __future__ import annotations

import inspect
import json
from contextlib import contextmanager

from human_feedback.loso_offline_adapter import validate_laya_loso_offline_response
from tests.test_laya_loso_runner import (
    _assert_non_scientific,
    _FixtureGrant,
    _module,
    _protocol,
    _wire,
)
from tests.test_laya_runtime_execution_image_lease import _registered_runtime

_CATEGORIES = (
    "data_quality",
    "model_behavior",
    "agronomic_context",
    "usability",
    "other",
)


def _canonical_response(count: int) -> bytes:
    return json.dumps(
        {
            "schema_version": "laya-gold-blind-offline-response-v2",
            "predictions": [
                {
                    "ordinal": ordinal,
                    "category": "data_quality",
                    "probabilities": {
                        "data_quality": 0.6,
                        "model_behavior": 0.1,
                        "agronomic_context": 0.1,
                        "usability": 0.1,
                        "other": 0.1,
                    },
                    "usage": {
                        "state_tokens": 17,
                        "state_tokens_dropped": 0,
                        "truncated": False,
                    },
                }
                for ordinal in range(count)
            ],
        },
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")


class _FakeOfflineEngine:
    def __init__(self, nonce, *, events, batches):
        self.nonce = nonce
        self.events = events
        self.batches = batches
        self.container_id = "c" * 64
        self.child_owned = False

    def create_closed_loso_offline_container(self, image_id):
        self.events.append("create")
        self.events.append(("create-image", image_id))
        self.child_owned = True
        return self.container_id

    def inspect_closed_loso_offline_container(self, container_id, *, expected_image_id):
        assert container_id == self.container_id
        self.events.append("inspect")
        self.events.append(("inspect-image", expected_image_id))
        return {"Id": container_id}

    def run_closed_loso_offline(
        self,
        container_id,
        *,
        expected_image_id,
        canonical_request,
    ):
        assert container_id == self.container_id
        assert type(canonical_request) is bytes
        request = json.loads(canonical_request)
        assert set(request) == {"schema_version", "items"}
        assert request["schema_version"] == "laya-gold-blind-offline-request-v2"
        items = request["items"]
        assert items and all(set(item) == {"token", "comment"} for item in items)
        assert all(type(item["token"]) is str and len(item["token"]) == 64 for item in items)
        assert all(type(item["comment"]) is str and item["comment"] for item in items)
        assert all(
            not {"gold", "site_id", "group_id", "example_id", "record"}.intersection(item)
            for item in items
        )
        self.events.append("run")
        self.events.append(("run-image", expected_image_id))
        self.batches.append(
            tuple({"token": item["token"], "comment": item["comment"]} for item in items)
        )
        return _canonical_response(len(items))

    def cleanup_owned_resources(self):
        self.events.append("cleanup")
        self.child_owned = False


def test_runner_wires_all_six_batches_through_concrete_port_without_scientific_claims(
    monkeypatch, tmp_path
):
    from human_feedback.adapters import (
        docker_runtime_materialization,
        laya_loso_docker_adapter,
        local_docker_engine,
    )

    runner = _module()
    protocol = _protocol(tmp_path)
    assert len(protocol._plan.folds) == 3
    (
        _materialization,
        runtime,
        resource,
        parent_engine,
        image_id,
        _installation,
        *_rest,
    ) = _registered_runtime(monkeypatch, marker="8")
    events = []
    batches = []
    engines = []
    real_lease = docker_runtime_materialization._lease_laya_runtime_image

    @contextmanager
    def observed_lease(value):
        events.append("lease-enter")
        try:
            with real_lease(value) as lease:
                yield lease
        finally:
            events.append("lease-exit")

    def engine_factory(nonce):
        engine = _FakeOfflineEngine(nonce, events=events, batches=batches)
        engines.append(engine)
        return engine

    monkeypatch.setattr(laya_loso_docker_adapter, "_lease_laya_runtime_image", observed_lease)
    monkeypatch.setattr(laya_loso_docker_adapter, "LocalDockerEngine", engine_factory)
    grant = _FixtureGrant(
        events,
        runtime_identity=runtime,
        model_identity=object(),
    )
    _wire(runner, monkeypatch, grant)
    port = laya_loso_docker_adapter.DockerLayaLosoOfflinePort(runtime)

    real_signature = inspect.signature(
        local_docker_engine.LocalDockerEngine.run_closed_loso_offline
    ).parameters
    fake_signature = inspect.signature(_FakeOfflineEngine.run_closed_loso_offline).parameters
    assert tuple(fake_signature) == tuple(real_signature)
    assert tuple(value.kind for value in fake_signature.values()) == tuple(
        value.kind for value in real_signature.values()
    )

    result = runner._run_human_loso_mechanical_fixture(protocol, port)
    _assert_non_scientific(result)
    receipts = runner._sealed_human_loso_mechanical_batches(protocol)

    assert len(engines) == len(batches) == len(receipts) == 6
    assert len({engine.nonce for engine in engines}) == 6
    assert all(engine.child_owned is False for engine in engines)
    assert [receipt.phase for receipt in receipts] == [
        "calibration",
        "test",
        "calibration",
        "test",
        "calibration",
        "test",
    ]
    assert [receipt.fold_index for receipt in receipts] == [0, 0, 1, 1, 2, 2]
    for receipt, batch in zip(receipts, batches):
        assert receipt.runtime_identity is runtime
        assert receipt.model_identity is grant.model_identity
        assert receipt.inference_port is port
        assert receipt.item_count == len(batch)
        assert (
            validate_laya_loso_offline_response(
                receipt.canonical_response,
                expected_count=len(batch),
            )
            == receipt.canonical_response
        )
        assert set(
            json.loads(receipt.canonical_response)["predictions"][0]["probabilities"]
        ) == set(_CATEGORIES)

    lifecycle = [event for event in events if type(event) is str]
    assert lifecycle == [
        item
        for _batch in range(6)
        for item in ("lease-enter", "create", "inspect", "run", "cleanup", "lease-exit")
    ]
    assert [event for event in events if type(event) is tuple and event[0] == "release"] == [
        ("release", 0),
        ("release", 1),
        ("release", 2),
    ]
    with resource.condition:
        assert resource.leases == 0
        assert resource.lease_owners == {}
    assert parent_engine.removed == []

    events_after_run = tuple(events)
    batches_after_run = tuple(batches)
    assert runner._run_human_loso_mechanical_fixture(protocol, port) is result
    assert runner._sealed_human_loso_mechanical_batches(protocol) == receipts
    assert tuple(events) == events_after_run
    assert tuple(batches) == batches_after_run

    preflight = runner.preflight_human_loso_runner(protocol, port)
    assert preflight.status == "BLOCKED_CORPUS_NOT_PROVIDED"
    assert preflight.ready is False
    assert preflight.comment_consumed is False
    assert preflight.inference_invoked is False
    assert tuple(events) == events_after_run
    assert tuple(batches) == batches_after_run
