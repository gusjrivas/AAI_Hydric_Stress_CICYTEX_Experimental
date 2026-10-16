import ast
import hashlib
import inspect
from dataclasses import fields, is_dataclass
from pathlib import Path
from types import SimpleNamespace

import pytest

PLAN_SCHEMA = "laya-runtime-provenance-plan-v1"
EVIDENCE_SCHEMA = "laya-runtime-provenance-evidence-v1"
SOURCE_REPOSITORY = "https://github.com/NandhaKishorM/laya"
CHECKPOINT_REPOSITORY = "https://huggingface.co/convaiinnovations/laya"
SOURCE_COMMIT = "68804629e8ccd9d616d48a40e87de9fabbeae069"
CHECKPOINT_COMMIT = "55cf4c4ebb4ebe31b2550e8bdf3bd21b99753851"
EXPECTED_OBJECTS = (
    (
        "source_tag",
        "tag",
        "a0d473b307b7eaa7385ae04feea43c52581c4f5a",
        "7f7f43c230ac6e106c3cc3ee713b905964cd66cd8c4c91435f6441be0f8b91ed",
        912,
    ),
    (
        "source_commit",
        "commit",
        SOURCE_COMMIT,
        "f40967375c7dd748a8060268384ef4103830c19798b5954da485234ccc7cef7f",
        975,
    ),
    (
        "source_tree",
        "tree",
        "1f64e459fd2b9f55d7672b0457a2245faa49dce7",
        "da1be47947c251b312b4007946b4460dfca97ec3f5f88c9c2ba75203d976a218",
        1686,
    ),
    (
        "source_license",
        "blob",
        "d9a10c0d8e868ebf8da0b3dc95bb0be634c34bfe",
        "a6cba85bc92e0cff7a450b1d873c0eaa2e9fc96bf472df0247a26bec77bf3ff9",
        10173,
    ),
    (
        "source_pyproject",
        "blob",
        "4f05fe8dcd6c6e131c8200648e024d1bad7fc920",
        "375130a133e96f0c7481ed38f1cc59a86aea79a5dd984770215fecc8e1bedaa6",
        3956,
    ),
    (
        "checkpoint_commit",
        "commit",
        CHECKPOINT_COMMIT,
        "4e00a98879150b4c17b83ec48688c81e0b14a2b62ebf35b2c831ab67eb95fb75",
        1149,
    ),
    (
        "checkpoint_tree",
        "tree",
        "61ea5230f8c24a7b55f9b37e74518c6ef17e62b3",
        "0c4cc02bf64c39e2594beb5021c49193a857302c18d9f3aa121d67d179ee74d3",
        512,
    ),
    (
        "checkpoint_readme",
        "blob",
        "ac11a565c217959d0cb062748a2f83e05da446a5",
        "00355613796b3f5860b0d5b20392381d26580ec242e04a1fd150c7f116858602",
        23187,
    ),
    (
        "multilingual_tree",
        "tree",
        "de7883e4ef73e15f09af019dd10526bfd3099bcc",
        "23b429e24c9cc58fa0afe42aa15b91f45f02e463cec666dbe50e389d82189ea4",
        163,
    ),
    (
        "encoder_tree",
        "tree",
        "3dab0f21aa014e7aded1f8e8087665d2a501b457",
        "37615bcb694d28a74ad14f87e3969d1158c3c96e19365f59918331e3548517d0",
        39,
    ),
    (
        "tokenizer_tree",
        "tree",
        "fb46ae282300390f9b4441103b7186ec6694d59a",
        "b0956a8fbb7183c7270faf8491235ea8c33c9c104f54ac594c0ea72f500b341b",
        91,
    ),
    (
        "encoder_config",
        "blob",
        "0de0e2d30638873790cf962def52e2acf4db3eef",
        "83f6916d13ef0f556ac461f28308dc2bffa7ebeadee8ec9e2db5812020ea5bb4",
        1938,
    ),
    (
        "weights_lfs",
        "blob",
        "b99c8bea239c53f6f6bce734557dc6c403fa6b3e",
        "728656cf0aacad64dea942a0438242d8d5199db39e5602a77ebee6cd0319c759",
        134,
    ),
    (
        "laya_config",
        "blob",
        "00e35f88bb731bb9126a914666ab1cdac8a204c8",
        "25061739243b617ad88d1219ba6f8a9c86c5881ca28df024fa2d9b3b2fcc30c6",
        472,
    ),
    (
        "tokenizer_lfs",
        "blob",
        "56d765858ed38eaabd35cd90759cbb1f89b0baa4",
        "9ca6155812f67a58160ce2cded92df5912c97509d38937ddc200f7fc8e142566",
        133,
    ),
    (
        "tokenizer_config",
        "blob",
        "c255ac0c8cb34a37d066cd0dafe313fd769d27ae",
        "6c6b2d8e3c84ce0e671c129cd6b374b235d6f9863042a5836358d00a89bbb5a1",
        524,
    ),
)


def _provenance():
    import human_feedback.runtime_provenance as provenance

    return provenance


def _git_sha1(kind: str, payload: bytes) -> str:
    return hashlib.sha1(
        kind.encode("ascii") + b" " + str(len(payload)).encode("ascii") + b"\0" + payload,
        usedforsecurity=False,
    ).hexdigest()


def _tree_entry(mode: str, path: str, object_id: str) -> bytes:
    return mode.encode("ascii") + b" " + path.encode("utf-8") + b"\0" + bytes.fromhex(object_id)


def _commit(tree: str = "1" * 40) -> bytes:
    return (
        f"tree {tree}\n"
        f"parent {'2' * 40}\n"
        "author Example <example@example.com> 1700000000 +0000\n"
        "committer Example <example@example.com> 1700000000 +0000\n"
        "\nrelease: 0.4.2\n"
    ).encode("ascii")


def _tag(commit: str = SOURCE_COMMIT) -> bytes:
    return (
        f"object {commit}\n"
        "type commit\n"
        "tag v0.4.2\n"
        "tagger Example <example@example.com> 1700000000 +0000\n"
        "\nlaya 0.4.2\n"
    ).encode("ascii")


def _private_error(exc: BaseException, *markers: str) -> None:
    rendered = "\n".join((str(exc), repr(exc), repr(exc.__cause__), repr(exc.__context__)))
    assert exc.__cause__ is None
    assert exc.__suppress_context__ is True
    assert all(marker not in rendered for marker in markers)


def test_public_profile_constants_are_exact_closed_and_dual_digest_pinned():
    provenance = _provenance()
    assert provenance.PROVENANCE_PLAN_SCHEMA == PLAN_SCHEMA
    assert provenance.PROVENANCE_EVIDENCE_SCHEMA == EVIDENCE_SCHEMA
    assert provenance.SOURCE_REPOSITORY == SOURCE_REPOSITORY
    assert provenance.CHECKPOINT_REPOSITORY == CHECKPOINT_REPOSITORY
    assert provenance.SOURCE_COMMIT == SOURCE_COMMIT
    assert provenance.CHECKPOINT_COMMIT == CHECKPOINT_COMMIT
    assert provenance.MAX_PROVENANCE_OBJECTS == 16
    assert provenance.MAX_PROVENANCE_OBJECT_BYTES == 64 * 1024
    assert (
        tuple(
            (item.role, item.kind, item.sha1, item.sha256, item.size_bytes)
            for item in provenance.PROVENANCE_OBJECTS
        )
        == EXPECTED_OBJECTS
    )
    assert all(
        len(item.sha1) == 40
        and item.sha1 == item.sha1.lower()
        and int(item.sha1, 16) != 0
        and len(item.sha256) == 64
        and item.sha256 == item.sha256.lower()
        and int(item.sha256, 16) != 0
        for item in provenance.PROVENANCE_OBJECTS
    )


def test_plan_requires_exact_deeply_valid_pr34_evidence_before_object_consumption():
    provenance = _provenance()
    from human_feedback.runtime_checkpoint import LayaRuntimeCheckpointEvidence

    class Hostile:
        def __getattribute__(self, name):
            if name.startswith("__"):
                return object.__getattribute__(self, name)
            raise AssertionError("private-ancestor-marker")

    exact_but_unsealed = object.__new__(LayaRuntimeCheckpointEvidence)
    for invalid in (None, SimpleNamespace(), Hostile(), exact_but_unsealed):
        with pytest.raises((TypeError, ValueError)) as caught:
            provenance.prepare_laya_runtime_provenance_plan(invalid)
        _private_error(caught.value, "private-ancestor-marker")


def test_git_commit_parser_is_strict_closed_and_private():
    provenance = _provenance()
    parsed = provenance._parse_git_commit_bytes(_commit())
    assert parsed.tree_sha1 == "1" * 40
    assert parsed.parent_sha1s == ("2" * 40,)
    assert not hasattr(parsed, "raw_bytes")
    invalid = (
        _commit().replace(b"tree ", b"Tree ", 1),
        _commit().replace(b"tree " + b"1" * 40 + b"\n", b"", 1),
        _commit().replace(b"author ", b"author \xff", 1),
        _commit() + b"\0private-trailing",
        _commit()[:-1],
        _commit().replace(b"\n\n", b"\ntree " + b"3" * 40 + b"\n\n", 1),
    )
    for payload in invalid:
        with pytest.raises(ValueError) as caught:
            provenance._parse_git_commit_bytes(payload)
        _private_error(caught.value, "private-trailing")


def test_annotated_tag_parser_requires_exact_commit_target_and_v042():
    provenance = _provenance()
    parsed = provenance._parse_git_tag_bytes(_tag())
    assert parsed.object_sha1 == SOURCE_COMMIT
    assert parsed.object_kind == "commit"
    assert parsed.tag == "v0.4.2"
    for payload in (
        _tag().replace(b"type commit", b"type tree"),
        _tag().replace(b"tag v0.4.2", b"tag 0.4.2"),
        _tag().replace(SOURCE_COMMIT.encode(), b"f" * 40),
        _tag() + b"private-trailing",
        _tag()[:-1],
    ):
        with pytest.raises(ValueError):
            provenance._parse_git_tag_bytes(payload)


def test_binary_tree_parser_preserves_order_and_rejects_unsafe_entries():
    provenance = _provenance()
    first = _tree_entry("100644", "LICENSE", "1" * 40)
    second = _tree_entry("040000", "multilingual", "2" * 40)
    parsed = provenance._parse_git_tree_bytes(first + second)
    assert tuple((item.mode, item.path, item.sha1) for item in parsed) == (
        ("100644", "LICENSE", "1" * 40),
        ("040000", "multilingual", "2" * 40),
    )
    invalid = (
        second + first,
        first + first,
        _tree_entry("120000", "link", "1" * 40),
        _tree_entry("160000", "submodule", "1" * 40),
        _tree_entry("100664", "weird", "1" * 40),
        _tree_entry("100644", "../escape", "1" * 40),
        _tree_entry("100644", "nested/path", "1" * 40),
        _tree_entry("100644", "C:private", "1" * 40),
        _tree_entry("100644", "back\\slash", "1" * 40),
        first[:-1],
        first + b"private-trailing",
    )
    for payload in invalid:
        with pytest.raises(ValueError) as caught:
            provenance._parse_git_tree_bytes(payload)
        _private_error(caught.value, "private-trailing", "C:private")


@pytest.mark.parametrize(
    ("payload", "expected_digest", "expected_size"),
    [
        (
            b"version https://git-lfs.github.com/spec/v1\n"
            b"oid sha256:9d628fd971b700382ac6f65920a86f149777b2e748e0c955fb3b19695aa8f204\n"
            b"size 643835514\n",
            "9d628fd971b700382ac6f65920a86f149777b2e748e0c955fb3b19695aa8f204",
            643835514,
        ),
        (
            b"version https://git-lfs.github.com/spec/v1\n"
            b"oid sha256:609d8f4c067cd3950f88594c5a802616cea245823836ef5848ee4fc40aab5b6f\n"
            b"size 34363188\n",
            "609d8f4c067cd3950f88594c5a802616cea245823836ef5848ee4fc40aab5b6f",
            34363188,
        ),
    ],
)
def test_large_checkpoint_blobs_are_exact_three_line_lfs_pointers(
    payload, expected_digest, expected_size
):
    parsed = _provenance()._parse_lfs_pointer_bytes(payload)
    assert parsed.sha256 == expected_digest
    assert parsed.size_bytes == expected_size
    for invalid in (
        payload.replace(b"\n", b"\r\n"),
        payload.rstrip(b"\n"),
        payload + b"extra\n",
        payload.replace(b"oid sha256:", b"oid sha1:"),
        payload.replace(str(expected_size).encode(), b"01"),
    ):
        with pytest.raises(ValueError):
            _provenance()._parse_lfs_pointer_bytes(invalid)


def test_license_and_package_declarations_are_exact_and_checkpoint_repo_is_not_alias():
    provenance = _provenance()
    provenance._validate_source_license_bytes(b"Apache License\nVersion 2.0, January 2004\n")
    provenance._validate_source_pyproject_bytes(
        b'[project]\nname = "laya"\nversion = "0.4.2"\n' b'license = { text = "Apache-2.0" }\n'
    )
    provenance._validate_checkpoint_readme_bytes(
        b"---\nlicense: apache-2.0\n---\nrepo: convaiinnovations/laya\nsubfolder: multilingual\n"
    )
    invalid = (
        (provenance._validate_source_license_bytes, b"MIT License"),
        (
            provenance._validate_source_pyproject_bytes,
            b'[project]\nname="laya"\nversion="0.4.2"\nlicense="MIT"\n',
        ),
        (
            provenance._validate_checkpoint_readme_bytes,
            b"---\nlicense: apache-2.0\n---\n" b"repo: convaiinnovations/laya-multilingual\n",
        ),
    )
    for validator, payload in invalid:
        with pytest.raises(ValueError):
            validator(payload)


def test_object_verifier_rejects_wrong_type_size_sha1_sha256_and_stream_shape():
    provenance = _provenance()
    bad_plan = SimpleNamespace()
    for value in (None, bad_plan, object()):
        with pytest.raises((TypeError, ValueError)):
            provenance.verify_laya_runtime_provenance_object_chunks(value, "1" * 40, iter((b"x",)))
    assert provenance.MAX_PROVENANCE_CHUNK_BYTES == 1024 * 1024
    assert provenance.MAX_PROVENANCE_CHUNKS == 64


def test_factory_sealed_types_are_frozen_slotted_private_and_retain_no_payload():
    provenance = _provenance()
    classes = (
        provenance.LayaGitObjectSpec,
        provenance.LayaRuntimeProvenancePlan,
        provenance.LayaGitObjectEnvelope,
        provenance.VerifiedLayaProvenanceObject,
        provenance.LayaRuntimeProvenanceEvidence,
    )
    for cls in classes:
        assert is_dataclass(cls) and cls.__dataclass_params__.frozen
        assert "__dict__" not in vars(cls)
        assert not {"payload", "content", "chunks", "raw_bytes"} & {
            field.name for field in fields(cls)
        }
        with pytest.raises((TypeError, ValueError)):
            cls()
    assert all(
        parameter.default is inspect.Parameter.empty
        for name, parameter in inspect.signature(
            provenance.LayaGitObjectEnvelope
        ).parameters.items()
        if name == "_factory_token"
    )


def test_evidence_claims_and_summary_remain_conservative_private_and_deep():
    provenance = _provenance()
    evidence_fields = {
        field.name: field for field in fields(provenance.LayaRuntimeProvenanceEvidence)
    }
    true_flags = {
        "artifact_integrity_verified",
        "runtime_config_semantics_verified",
        "checkpoint_manifest_semantics_verified",
        "checkpoint_bytes_verified",
        "provenance_objects_verified",
    }
    false_flags = {
        "lock_verified",
        "sbom_verified",
        "lock_sbom_consistent",
        "oci_bytes_verified",
        "oci_manifest_semantics_verified",
        "origin_verified",
        "license_verified",
        "runtime_materialized",
        "executor_available",
        "inference_executed",
    }
    assert all(not evidence_fields[name].init for name in true_flags | false_flags)
    for value in (None, SimpleNamespace(), object()):
        with pytest.raises((TypeError, ValueError)):
            provenance.canonical_laya_runtime_provenance_summary_bytes(value)
    source = Path(provenance.__file__).read_text(encoding="utf-8")
    summary_source = source[source.index("def canonical_laya_runtime_provenance_summary_bytes") :]
    assert all(term not in summary_source for term in ('"path"', '"sha1"', '"sha256"', '"payload"'))


def test_module_is_pure_and_has_no_productive_callers():
    provenance = _provenance()
    source = Path(provenance.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        (node.module or "").split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
    assert not imports & {
        "os",
        "pathlib",
        "subprocess",
        "socket",
        "requests",
        "urllib",
        "shutil",
    }
    forbidden_calls = {
        "__import__",
        "compile",
        "eval",
        "exec",
        "open",
        "system",
        "read_bytes",
        "read_text",
        "write_bytes",
        "write_text",
    }
    calls = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    } | {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert not calls & forbidden_calls
    offenders = []
    for root in (Path("src"), Path("backend"), Path("scripts")):
        for path in root.rglob("*.py"):
            if path.as_posix() == "src/human_feedback/runtime_provenance.py":
                continue
            candidate = path.read_text(encoding="utf-8")
            if "human_feedback.runtime_provenance" in candidate:
                offenders.append(path.as_posix())
    assert offenders == []
