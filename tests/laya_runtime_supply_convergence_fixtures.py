"""Genuinely issued, compact predecessor graph for the PR37 contract tests."""

from __future__ import annotations

import gzip
import hashlib
import json
from dataclasses import dataclass


def _json(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("ascii")


def _digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _git_sha1(kind: str, payload: bytes) -> str:
    header = kind.encode("ascii") + b" " + str(len(payload)).encode("ascii") + b"\0"
    return hashlib.sha1(header + payload, usedforsecurity=False).hexdigest()


def _tree_entry(mode: str, path: str, object_id: str) -> bytes:
    return mode.encode("ascii") + b" " + path.encode("utf-8") + b"\0" + bytes.fromhex(object_id)


def _commit(tree: str) -> bytes:
    return (
        f"tree {tree}\nparent {'2' * 40}\n"
        "author Example <example@example.com> 1700000000 +0000\n"
        "committer Example <example@example.com> 1700000000 +0000\n"
        "\nrelease: 0.4.2\n"
    ).encode("ascii")


def _tag(commit: str) -> bytes:
    return (
        f"object {commit}\ntype commit\ntag v0.4.2\n"
        "tagger Example <example@example.com> 1700000000 +0000\n\n"
        "laya 0.4.2\n"
    ).encode("ascii")


def _padded_json(value: dict[str, object], padding: dict[str, object], size: int) -> bytes:
    padding.clear()
    for position in range(8):
        payload = _json(value)
        if len(payload) == size:
            return payload
        assert len(payload) < size
        key = f"padding-{position}"
        padding[key] = ""
        payload = _json(value)
        padding[key] = "x" * min(4096, size - len(payload))
    payload = _json(value)
    assert len(payload) == size
    return payload


@dataclass(frozen=True, slots=True)
class IssuedLayaSupplyChain:
    layer_evidence: object
    provenance_evidence: object
    base_ancestry_evidence: object
    snapshot: object
    provenance_snapshot: object
    checkpoint_payloads: tuple[bytes, ...]
    layer_payloads: tuple[bytes, ...]
    provenance_payloads: dict[str, bytes]


def _provenance_graph(checkpoint_payloads: dict[str, bytes]):
    from human_feedback import runtime_provenance as provenance

    payloads = {
        "source_license": b"Apache License\nVersion 2.0, January 2004\n",
        "source_pyproject": (
            b'[project]\nname = "laya"\nversion = "0.4.2"\n' b'license = { text = "Apache-2.0" }\n'
        ),
        "checkpoint_readme": (
            b"---\nlicense: apache-2.0\nlibrary_name: transformers\n"
            b"pipeline_tag: text-classification\n"
            b"tags: [laya, system-one, calibrated-decisions, rlcd, classification, "
            b"routing, scoring, guardrails, moderation, reinforcement-learning, "
            b"commercial-use]\n---\n"
        ),
        "encoder_config": checkpoint_payloads["encoder_config"],
        "laya_config": checkpoint_payloads["laya_config"],
        "tokenizer_config": checkpoint_payloads["tokenizer_config"],
    }
    payloads["weights_lfs"] = (
        b"version https://git-lfs.github.com/spec/v1\n"
        + f"oid sha256:{_digest(checkpoint_payloads['weights'])}\n".encode("ascii")
        + f"size {len(checkpoint_payloads['weights'])}\n".encode("ascii")
    )
    payloads["tokenizer_lfs"] = (
        b"version https://git-lfs.github.com/spec/v1\n"
        + f"oid sha256:{_digest(checkpoint_payloads['tokenizer'])}\n".encode("ascii")
        + f"size {len(checkpoint_payloads['tokenizer'])}\n".encode("ascii")
    )

    def tree(role: str, entries: tuple[tuple[str, str, str, str], ...]) -> None:
        payloads[role] = b"".join(
            _tree_entry(mode, path, _git_sha1(kind, payloads[target]))
            for mode, path, kind, target in entries
        )

    tree("encoder_tree", (("100644", "config.json", "blob", "encoder_config"),))
    tree(
        "tokenizer_tree",
        (
            ("100644", "tokenizer.json", "blob", "tokenizer_lfs"),
            ("100644", "tokenizer_config.json", "blob", "tokenizer_config"),
        ),
    )
    tree(
        "multilingual_tree",
        (
            ("040000", "encoder", "tree", "encoder_tree"),
            ("100644", "model.safetensors", "blob", "weights_lfs"),
            ("100644", "rl_agent_config.json", "blob", "laya_config"),
            ("040000", "tokenizer", "tree", "tokenizer_tree"),
        ),
    )
    tree(
        "checkpoint_tree",
        (
            ("100644", "README.md", "blob", "checkpoint_readme"),
            ("040000", "multilingual", "tree", "multilingual_tree"),
        ),
    )
    tree(
        "source_tree",
        (
            ("100644", "LICENSE", "blob", "source_license"),
            ("100644", "pyproject.toml", "blob", "source_pyproject"),
        ),
    )
    payloads["source_commit"] = _commit(_git_sha1("tree", payloads["source_tree"]))
    payloads["source_tag"] = _tag(_git_sha1("commit", payloads["source_commit"]))
    payloads["checkpoint_commit"] = _commit(_git_sha1("tree", payloads["checkpoint_tree"]))

    kinds = {role: "tree" if role.endswith("_tree") else "blob" for role in payloads}
    kinds.update(source_tag="tag", source_commit="commit", checkpoint_commit="commit")
    order = (
        "source_tag",
        "source_commit",
        "source_tree",
        "source_license",
        "source_pyproject",
        "checkpoint_commit",
        "checkpoint_tree",
        "checkpoint_readme",
        "multilingual_tree",
        "encoder_tree",
        "tokenizer_tree",
        "encoder_config",
        "weights_lfs",
        "laya_config",
        "tokenizer_lfs",
        "tokenizer_config",
    )
    specs = []
    for role in order:
        payload = payloads[role]
        spec = object.__new__(provenance.LayaGitObjectSpec)
        object.__setattr__(spec, "role", role)
        object.__setattr__(
            spec,
            "repository",
            (
                provenance.SOURCE_REPOSITORY
                if role.startswith("source_")
                else provenance.CHECKPOINT_REPOSITORY
            ),
        )
        object.__setattr__(spec, "kind", kinds[role])
        object.__setattr__(spec, "sha1", _git_sha1(kinds[role], payload))
        object.__setattr__(spec, "sha256", _digest(payload))
        object.__setattr__(spec, "size_bytes", len(payload))
        specs.append(spec)
    return payloads, tuple(specs)


def issue_laya_supply_chain(
    monkeypatch,
    *,
    artifact_overrides: dict[str, bytes] | None = None,
) -> IssuedLayaSupplyChain:
    """Emit PR22, PR35 and PR36 through their real public verifiers/sealers.

    Only closed-profile constants are rebound. Canonical validators and PR35's
    deep checkpoint validator remain untouched.
    """

    from human_feedback import (
        runtime_base_ancestry,
        runtime_bundle,
        runtime_checkpoint,
        runtime_deployment_metadata,
        runtime_oci_config,
        runtime_oci_layers,
        runtime_oci_layout,
        runtime_oci_metadata,
        runtime_provenance,
    )
    from tests.test_laya_runtime_artifact_integrity import _manifest, _payloads
    from tests.test_laya_runtime_oci_config import _config_object

    checkpoint_by_role = {
        "encoder_config": b'{"model_type":"synthetic-laya"}\n',
        "weights": b"synthetic weights",
        "laya_config": b'{"profile":"synthetic-laya"}\n',
        "tokenizer": b"synthetic tokenizer",
        "tokenizer_config": b'{"tokenizer":"synthetic-laya"}\n',
    }
    provenance_payloads, provenance_specs = _provenance_graph(checkpoint_by_role)
    source_commit = _git_sha1("commit", provenance_payloads["source_commit"])
    checkpoint_commit = _git_sha1("commit", provenance_payloads["checkpoint_commit"])

    checkpoint_files = (
        ("encoder_config", "encoder/config.json"),
        ("weights", "model.safetensors"),
        ("laya_config", "rl_agent_config.json"),
        ("tokenizer", "tokenizer/tokenizer.json"),
        ("tokenizer_config", "tokenizer/tokenizer_config.json"),
    )
    checkpoint_profile = tuple(
        (role, path, _digest(checkpoint_by_role[role]), len(checkpoint_by_role[role]))
        for role, path in checkpoint_files
    )
    environment = dict(runtime_deployment_metadata.ENVIRONMENT)
    environment["LAYA_REVISION"] = checkpoint_commit
    monkeypatch.setattr(runtime_deployment_metadata, "MODEL_REVISION", checkpoint_commit)
    monkeypatch.setattr(runtime_deployment_metadata, "ENVIRONMENT", environment)
    monkeypatch.setattr(runtime_deployment_metadata, "CHECKPOINT_FILES", checkpoint_profile)

    checkpoint_bytes = _json(
        {
            "schema_version": runtime_deployment_metadata.CHECKPOINT_SCHEMA_VERSION,
            "repository": runtime_deployment_metadata.MODEL_REPOSITORY,
            "revision": checkpoint_commit,
            "subfolder": runtime_deployment_metadata.MODEL_SUBFOLDER,
            "files": [
                {"role": role, "path": path, "sha256": digest, "size_bytes": size}
                for role, path, digest, size in checkpoint_profile
            ],
        }
    )
    runtime_config_bytes = _json(
        {
            "schema_version": runtime_deployment_metadata.RUNTIME_CONFIG_SCHEMA_VERSION,
            "entrypoint": runtime_deployment_metadata.ENTRYPOINT,
            "provider": "laya-http",
            "engine": "laya==0.4.2",
            "source": (
                "https://github.com/NandhaKishorM/laya@" "68804629e8ccd9d616d48a40e87de9fabbeae069"
            ),
            "python": "3.11.10",
            "platform": "linux/amd64",
            "model": {
                "repository": runtime_deployment_metadata.MODEL_REPOSITORY,
                "revision": checkpoint_commit,
                "subfolder": runtime_deployment_metadata.MODEL_SUBFOLDER,
                "name": runtime_deployment_metadata.MODEL_NAME,
            },
            "environment": environment,
            "checkpoint_manifest_sha256": _digest(checkpoint_bytes),
        }
    )

    raw_layers = tuple(f"supply-layer-{position:02d}".encode("ascii") for position in range(10))
    compressed_layers = tuple(gzip.compress(payload, mtime=0) for payload in raw_layers)
    layer_digests = tuple("sha256:" + _digest(payload) for payload in compressed_layers)
    diff_ids = tuple("sha256:" + _digest(payload) for payload in raw_layers)

    artifact_payloads = _payloads()
    artifact_payloads["config/runtime.json"] = runtime_config_bytes
    artifact_payloads["manifests/checkpoint.json"] = checkpoint_bytes
    annotations = {
        "org.aai-hydric.runtime.checkpoint-manifest.sha256": _digest(checkpoint_bytes),
        "org.aai-hydric.runtime.config.sha256": _digest(runtime_config_bytes),
        "org.aai-hydric.runtime.sbom.sha256": _digest(
            artifact_payloads["sbom/laya-runtime.cdx.json"]
        ),
        "org.aai-hydric.runtime.uv-lock.sha256": _digest(artifact_payloads["locks/uv.lock"]),
        "org.opencontainers.image.base.digest": ("sha256:" + "1" * 64),
        "org.opencontainers.image.base.name": "docker.io/library/python:3.11.10-slim-bookworm",
        "org.opencontainers.image.licenses": "Apache-2.0",
        "org.opencontainers.image.revision": "68804629e8ccd9d616d48a40e87de9fabbeae069",
        "org.opencontainers.image.source": "https://github.com/NandhaKishorM/laya",
        "org.opencontainers.image.version": "0.4.2",
    }
    config_value = _config_object()
    config_value["rootfs"]["diff_ids"] = list(diff_ids)
    config_value["config"]["Labels"] = dict(annotations)
    config_payload = _json(config_value)
    config_descriptor = (
        "application/vnd.oci.image.config.v1+json",
        "sha256:" + _digest(config_payload),
        len(config_payload),
    )
    layer_profile = tuple(
        (layer_digests[i], len(value)) for i, value in enumerate(compressed_layers)
    )
    oci_value = {
        "schemaVersion": 2,
        "mediaType": "application/vnd.oci.image.manifest.v1+json",
        "config": {
            "mediaType": config_descriptor[0],
            "digest": config_descriptor[1],
            "size": config_descriptor[2],
        },
        "layers": [
            {
                "mediaType": "application/vnd.oci.image.layer.v1.tar+gzip",
                "digest": digest,
                "size": size,
            }
            for digest, size in layer_profile
        ],
        "annotations": annotations,
    }
    oci_payload = _json(oci_value)
    artifact_payloads["manifests/oci.json"] = oci_payload
    manifest = _manifest(payloads=artifact_payloads)
    snapshot = runtime_bundle.verify_laya_runtime_artifact_bytes(manifest, artifact_payloads)
    provenance_artifact_payloads = dict(artifact_payloads)
    if artifact_overrides is not None:
        if type(artifact_overrides) is not dict or any(
            type(path) is not str or type(content) is not bytes or not content
            for path, content in artifact_overrides.items()
        ):
            raise TypeError("artifact overrides must be a nonempty exact-bytes mapping")
        unknown_paths = set(artifact_overrides).difference(provenance_artifact_payloads)
        if unknown_paths:
            raise ValueError("artifact override path is outside the bundle contract")
        provenance_artifact_payloads.update(artifact_overrides)
    provenance_manifest = _manifest(payloads=provenance_artifact_payloads)
    provenance_snapshot = runtime_bundle.verify_laya_runtime_artifact_bytes(
        provenance_manifest, provenance_artifact_payloads
    )
    assert snapshot is not provenance_snapshot
    if artifact_overrides is None:
        assert snapshot == provenance_snapshot

    monkeypatch.setattr(runtime_oci_metadata, "_CONFIG", config_descriptor)
    monkeypatch.setattr(runtime_oci_metadata, "_LAYERS", layer_profile)
    monkeypatch.setattr(runtime_oci_metadata, "_ANNOTATIONS", annotations)
    monkeypatch.setattr(runtime_oci_metadata, "_SEMANTICS_SHA256", _digest(_json(oci_value)))
    monkeypatch.setattr(runtime_oci_metadata, "_OCI_PAYLOAD_SIZE_BYTES", len(oci_payload))
    monkeypatch.setattr(runtime_oci_metadata, "_OCI_PAYLOAD_SHA256", _digest(oci_payload))
    oci_evidence = runtime_oci_metadata.validate_laya_runtime_oci_metadata(snapshot)

    layout_bytes = b'{"imageLayoutVersion":"1.0.0"}'
    manifest_digest = "sha256:" + _digest(oci_payload)
    index_value = {
        "schemaVersion": 2,
        "mediaType": "application/vnd.oci.image.index.v1+json",
        "manifests": [
            {
                "mediaType": "application/vnd.oci.image.manifest.v1+json",
                "digest": manifest_digest,
                "size": len(oci_payload),
                "platform": {"architecture": "amd64", "os": "linux"},
                "annotations": {
                    "org.opencontainers.image.created": "1970-01-01T00:00:00Z",
                    "org.opencontainers.image.ref.name": "laya-runtime-v0.4.2",
                },
            }
        ],
    }
    index_bytes = _json(index_value)
    assert len(index_bytes) <= 423
    index_bytes += b" " * (423 - len(index_bytes))
    monkeypatch.setattr(runtime_oci_layout, "_LAYOUT_SIZE_BYTES", len(layout_bytes))
    monkeypatch.setattr(runtime_oci_layout, "_LAYOUT_SHA256", _digest(layout_bytes))
    monkeypatch.setattr(runtime_oci_layout, "_INDEX_SIZE_BYTES", len(index_bytes))
    monkeypatch.setattr(runtime_oci_layout, "_INDEX_SHA256", _digest(index_bytes))
    expected_blobs = (
        ("manifest", oci_value["mediaType"], manifest_digest, len(oci_payload)),
        ("config", config_descriptor[0], config_descriptor[1], config_descriptor[2]),
        *tuple(
            (
                f"layer-{position:02d}",
                "application/vnd.oci.image.layer.v1.tar+gzip",
                digest,
                size,
            )
            for position, (digest, size) in enumerate(layer_profile)
        ),
    )
    layout_plan = runtime_oci_layout.prepare_laya_oci_layout_plan(
        oci_evidence, layout_bytes, index_bytes
    )
    blob_payloads = (oci_payload, config_payload, *compressed_layers)
    blob_receipts = tuple(
        runtime_oci_layout.verify_laya_oci_blob_chunks(
            plan=layout_plan, digest=blob.digest, chunks=(payload,)
        )
        for blob, payload in zip(layout_plan.blobs, blob_payloads)
    )
    layout_authority = runtime_oci_layout._seal_laya_oci_layout_capture_authority(
        layout_plan,
        blob_receipts,
        controls_captured_from_same_root=True,
        inventory_captured_from_same_root=True,
        final_fd_sweep_verified=True,
    )
    layout_evidence = runtime_oci_layout._seal_laya_oci_layout_evidence(layout_authority)

    monkeypatch.setattr(runtime_oci_config, "_CONFIG_SIZE_BYTES", len(config_payload))
    monkeypatch.setattr(runtime_oci_config, "_CONFIG_SHA256", _digest(config_payload))
    monkeypatch.setattr(
        runtime_oci_config, "_OCI_MANIFEST_SEMANTICS_SHA256", _digest(_json(oci_value))
    )
    monkeypatch.setattr(runtime_oci_config, "_EXPECTED_LABELS", annotations)
    monkeypatch.setattr(runtime_oci_config, "_EXPECTED_DIFF_IDS", diff_ids)
    monkeypatch.setattr(runtime_oci_config, "_EXPECTED_BLOBS", expected_blobs)
    config_evidence = runtime_oci_config.validate_laya_runtime_oci_config_semantics(
        layout_evidence, config_payload
    )
    layer_plan = runtime_oci_layers.prepare_laya_oci_layer_diff_id_plan(config_evidence)
    layer_receipts = tuple(
        runtime_oci_layers.verify_laya_oci_layer_diff_id_chunks(
            layer_plan, blob.digest, (compressed_layers[position],)
        )
        for position, blob in enumerate(layer_plan.layer_blobs)
    )
    layer_authority = runtime_oci_layers._seal_laya_oci_layer_diff_ids_capture_authority(
        layer_plan,
        layer_receipts,
        layers_captured_from_same_root=True,
        inventory_captured_from_same_root=True,
        final_fd_sweep_verified=True,
        descriptors_closed_before_seal=True,
    )
    layer_evidence = runtime_oci_layers._seal_laya_runtime_oci_layer_diff_ids_evidence(
        layer_authority
    )

    base_layers = tuple(
        (blob.digest, blob.size_bytes, blob.media_type) for blob in layer_plan.layer_blobs[:4]
    )
    base_diff_ids = diff_ids[:4]
    base_config_padding: dict[str, object] = {}
    base_config = {
        "architecture": "amd64",
        "config": base_config_padding,
        "created": "1970-01-01T00:00:00Z",
        "history": [{"comment": "synthetic issued profile"}],
        "os": "linux",
        "rootfs": {"type": "layers", "diff_ids": list(base_diff_ids)},
    }
    base_config_payload = _padded_json(base_config, base_config_padding, 5295)
    base_manifest_padding: dict[str, object] = {}
    base_manifest = {
        "schemaVersion": 2,
        "mediaType": "application/vnd.oci.image.manifest.v1+json",
        "config": {
            "digest": "sha256:" + _digest(base_config_payload),
            "size": len(base_config_payload),
            "mediaType": "application/vnd.oci.image.config.v1+json",
        },
        "layers": [
            {"digest": digest, "size": size, "mediaType": media_type}
            for digest, size, media_type in base_layers
        ],
        "annotations": base_manifest_padding,
    }
    base_manifest_payload = _padded_json(base_manifest, base_manifest_padding, 1752)
    selected = {
        "digest": "sha256:" + _digest(base_manifest_payload),
        "size": len(base_manifest_payload),
        "mediaType": "application/vnd.oci.image.manifest.v1+json",
        "platform": {"architecture": "amd64", "os": "linux"},
        "annotations": {},
    }
    decoys = [
        {
            "digest": f"sha256:{position + 1:064x}",
            "size": 1,
            "mediaType": "application/vnd.oci.image.manifest.v1+json",
            "platform": {"architecture": f"other-{position:02d}", "os": "linux"},
        }
        for position in range(13)
    ]
    root_payload = _json(
        {
            "schemaVersion": 2,
            "mediaType": "application/vnd.oci.image.index.v1+json",
            "manifests": [selected, *decoys],
        }
    )
    base_payloads = (root_payload, base_manifest_payload, base_config_payload)
    monkeypatch.setattr(runtime_base_ancestry, "_BASE_LAYERS", base_layers)
    monkeypatch.setattr(runtime_base_ancestry, "_BASE_DIFF_IDS", base_diff_ids)
    monkeypatch.setattr(runtime_base_ancestry, "_ROOT_DIGEST", _digest(root_payload))
    monkeypatch.setattr(runtime_base_ancestry, "_MANIFEST_DIGEST", _digest(base_manifest_payload))
    monkeypatch.setattr(runtime_base_ancestry, "_CONFIG_DIGEST", _digest(base_config_payload))
    monkeypatch.setattr(
        runtime_base_ancestry,
        "_OBJECT_SPECS",
        tuple((len(payload), _digest(payload)) for payload in base_payloads),
    )
    base_plan = runtime_base_ancestry.prepare_laya_runtime_base_ancestry_plan(layer_evidence)
    base_evidence = runtime_base_ancestry.verify_laya_runtime_base_ancestry_objects(
        base_plan, tuple(iter((payload,)) for payload in base_payloads)
    )

    deployment = runtime_deployment_metadata.validate_laya_runtime_deployment_metadata(
        provenance_snapshot
    )
    checkpoint_plan = runtime_checkpoint.prepare_laya_runtime_checkpoint_plan(deployment)
    checkpoint_receipts = tuple(
        runtime_checkpoint.verify_laya_checkpoint_file_chunks(
            checkpoint_plan, item.sha256, (checkpoint_by_role[item.role],)
        )
        for item in checkpoint_plan.files
    )
    checkpoint_authority = runtime_checkpoint._seal_laya_checkpoint_capture_authority(
        checkpoint_plan, checkpoint_receipts
    )
    checkpoint_evidence = runtime_checkpoint._seal_laya_runtime_checkpoint_evidence(
        checkpoint_authority
    )
    monkeypatch.setattr(runtime_provenance, "SOURCE_COMMIT", source_commit)
    monkeypatch.setattr(runtime_provenance, "CHECKPOINT_COMMIT", checkpoint_commit)
    monkeypatch.setattr(runtime_provenance, "PROVENANCE_OBJECTS", provenance_specs)
    provenance_plan = runtime_provenance.prepare_laya_runtime_provenance_plan(checkpoint_evidence)
    packets = tuple(
        (spec.repository, spec.kind, spec.sha1, (provenance_payloads[spec.role],))
        for spec in provenance_plan.objects
    )
    provenance_evidence = runtime_provenance.verify_laya_runtime_provenance_objects(
        provenance_plan, packets
    )

    return IssuedLayaSupplyChain(
        layer_evidence=layer_evidence,
        provenance_evidence=provenance_evidence,
        base_ancestry_evidence=base_evidence,
        snapshot=snapshot,
        provenance_snapshot=provenance_snapshot,
        checkpoint_payloads=tuple(checkpoint_by_role[role] for role, _path in checkpoint_files),
        layer_payloads=compressed_layers,
        provenance_payloads=provenance_payloads,
    )
