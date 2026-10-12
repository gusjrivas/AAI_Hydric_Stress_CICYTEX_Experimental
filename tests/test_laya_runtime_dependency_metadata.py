import hashlib
import json
import traceback
from copy import deepcopy
from dataclasses import FrozenInstanceError, is_dataclass, replace
from pathlib import Path

import pytest

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - exercised by the Python 3.10 job
    import tomli as tomllib

FIXTURE_SHA256 = "e968771680b9c6e683163230ebd98b43541325ccb36d6959d1f9ed5565bd5526"
FIXTURE_SIZE_BYTES = 37_599
EXPECTED_LOCK_SEMANTICS_SHA256 = "c4e1d2876569217c106d9a32fdfacb5a88c1fbd4808fe90c828ba8073a9ab45e"
SBOM_FIXTURE_SHA256 = "f2fde1a342990e3b5b4d74d4930bf37f6d2229768b509a27f34edffc009a03b2"
SBOM_FIXTURE_SIZE_BYTES = 65_198
EXPECTED_SBOM_SEMANTICS_SHA256 = "c2feadbd7103a8b27a435a682ee7ba4a9fdc90e4ebbf358b2f0b892bb73721fe"
MAX_UV_LOCK_BYTES = 2 * 1024 * 1024
MAX_UV_LOCK_PACKAGES = 512
MAX_DISTRIBUTIONS_PER_PACKAGE = 256
MAX_UV_LOCK_STRING_LENGTH = 1_024
MAX_UV_LOCK_URL_LENGTH = 4_096
MAX_CYCLONEDX_SBOM_BYTES = 2 * 1024 * 1024
MAX_SBOM_COMPONENTS = 512
MAX_SBOM_DEPENDENCY_NODES = 512
MAX_SBOM_DEPENDENCY_EDGES = 4_096
MAX_SBOM_STRING_LENGTH = 1_024
MAX_SBOM_URL_LENGTH = 4_096
MARKER = (
    "implementation_name == 'cpython' and platform_machine == 'x86_64' "
    "and sys_platform == 'linux'"
)
EXCLUDE_NEWER = "2026-10-10T09:19:05Z"
LAYA_COMMIT = "68804629e8ccd9d616d48a40e87de9fabbeae069"
LAYA_GIT = "https://github.com/NandhaKishorM/laya?rev=" f"{LAYA_COMMIT}#{LAYA_COMMIT}"
PYTORCH_INDEX = "https://download.pytorch.org/whl/cpu"
CYCLONEDX_SCHEMA = "https://cyclonedx.org/schema/bom-1.6.schema.json"
ALLOWED_REGISTRIES = {"https://pypi.org/simple", PYTORCH_INDEX}
ALLOWED_ARTIFACT_HOSTS = {"files.pythonhosted.org", "download-r2.pytorch.org"}


def _fixture_path() -> Path:
    return Path(__file__).parent / "fixtures" / "laya" / "runtime_dependency" / "uv.lock"


def _fixture_bytes() -> bytes:
    return _fixture_path().read_bytes()


def _sbom_fixture_path() -> Path:
    return _fixture_path().with_name("laya-runtime.cdx.json")


def _sbom_fixture_bytes() -> bytes:
    return _sbom_fixture_path().read_bytes()


def _sbom_fixture_object() -> dict[str, object]:
    return json.loads(_sbom_fixture_bytes())


def _fixture_object() -> dict[str, object]:
    return tomllib.loads(_fixture_bytes().decode("utf-8"))


def _canonical_lock_semantics_sha256(value: dict[str, object]) -> str:
    normalized = deepcopy(value)
    packages = normalized["package"]
    assert isinstance(packages, list)
    for package in packages:
        for collection in ("dependencies", "wheels"):
            if collection in package:
                package[collection].sort(
                    key=lambda item: json.dumps(item, sort_keys=True, separators=(",", ":"))
                )
        if "optional-dependencies" in package:
            optional = package["optional-dependencies"]
            package["optional-dependencies"] = {
                name: sorted(
                    dependencies,
                    key=lambda item: json.dumps(item, sort_keys=True, separators=(",", ":")),
                )
                for name, dependencies in sorted(optional.items())
            }
        if "metadata" in package:
            package["metadata"]["requires-dist"].sort(
                key=lambda item: json.dumps(item, sort_keys=True, separators=(",", ":"))
            )
    packages.sort(key=lambda package: package["name"])
    encoded = json.dumps(
        normalized,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("ascii")
    return hashlib.sha256(encoded).hexdigest()


def _canonical_sbom_semantics_sha256(value: dict[str, object]) -> str:
    unordered_arrays = {
        "authors",
        "components",
        "dependencies",
        "dependsOn",
        "externalReferences",
        "identity",
        "lifecycles",
        "methods",
        "properties",
    }

    def normalize(current, *, parent_key: str | None = None):
        if isinstance(current, dict):
            return {key: normalize(item, parent_key=key) for key, item in sorted(current.items())}
        if isinstance(current, list):
            result = [normalize(item) for item in current]
            if parent_key in unordered_arrays:
                result.sort(
                    key=lambda item: json.dumps(item, sort_keys=True, separators=(",", ":"))
                )
            return result
        return current

    encoded = json.dumps(
        normalize(value),
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("ascii")
    return hashlib.sha256(encoded).hexdigest()


def _mutated(old: bytes, new: bytes) -> bytes:
    payload = _fixture_bytes()
    assert old in payload
    return payload.replace(old, new, 1)


def _validate(payload: bytes | None = None):
    from human_feedback.runtime_dependency_metadata import validate_laya_uv_lock_bytes

    return validate_laya_uv_lock_bytes(_fixture_bytes() if payload is None else payload)


def _validate_parsed(monkeypatch, value: dict[str, object]):
    from human_feedback import runtime_dependency_metadata as module

    monkeypatch.setattr(module.tomllib, "loads", lambda _text: value)
    return module.validate_laya_uv_lock_bytes(b"synthetic-valid-size")


def _validate_sbom(payload: bytes | None = None):
    from human_feedback.runtime_dependency_metadata import validate_laya_cyclonedx_sbom_bytes

    return validate_laya_cyclonedx_sbom_bytes(_sbom_fixture_bytes() if payload is None else payload)


def _validate_sbom_parsed(monkeypatch, value: dict[str, object]):
    from human_feedback import runtime_dependency_metadata as module

    monkeypatch.setattr(module.json, "loads", lambda _text: value)
    return module.validate_laya_cyclonedx_sbom_bytes(b'{"synthetic":"valid-size"}')


def _package(lock, name: str):
    return next(item for item in lock.packages if item.name == name)


def test_committed_uv_lock_fixture_is_exact_generated_evidence():
    payload = _fixture_bytes()

    assert len(payload) == FIXTURE_SIZE_BYTES
    assert hashlib.sha256(payload).hexdigest() == FIXTURE_SHA256
    assert len(_fixture_object()["package"]) == 45


def test_full_canonical_lock_semantics_have_an_exact_commitment():
    value = _fixture_object()
    lock = _validate()

    assert _canonical_lock_semantics_sha256(value) == EXPECTED_LOCK_SEMANTICS_SHA256
    assert lock.semantics_sha256 == EXPECTED_LOCK_SEMANTICS_SHA256


def test_exact_laya_supply_lock_profile_loads():
    from human_feedback.runtime_dependency_metadata import (
        LockedDistribution,
        LockedPackage,
        ValidatedLayaUvLock,
    )

    lock = _validate()

    assert isinstance(lock, ValidatedLayaUvLock)
    assert lock.version == 1
    assert lock.revision == 3
    assert lock.requires_python == "==3.11.10"
    assert lock.resolution_markers == (MARKER,)
    assert lock.supported_markers == (MARKER,)
    assert lock.required_markers == (MARKER,)
    assert lock.exclude_newer == EXCLUDE_NEWER
    assert lock.build_constraints == (("setuptools", "==84.0.0"),)
    assert len(lock.packages) == 45
    assert all(isinstance(package, LockedPackage) for package in lock.packages)
    assert tuple(package.name for package in lock.packages) == tuple(
        sorted(package.name for package in lock.packages)
    )
    assert all(
        isinstance(distribution, LockedDistribution)
        for package in lock.packages
        for distribution in package.distributions
    )


def test_root_laya_and_torch_packages_are_exactly_pinned():
    lock = _validate()
    root = _package(lock, "laya-runtime-supply")
    laya = _package(lock, "laya")
    torch = _package(lock, "torch")

    assert root.version == "0.0.0"
    assert root.source_kind == "virtual"
    assert root.source_url == "."
    assert root.dependencies == ("laya", "torch")
    assert laya.version == "0.4.2"
    assert laya.source_kind == "git"
    assert laya.source_url == LAYA_GIT
    assert laya.dependencies == (
        "huggingface-hub",
        "numpy",
        "safetensors",
        "torch",
        "transformers",
    )
    assert laya.optional_dependencies == (("serve", ("fastapi", "python-multipart", "uvicorn")),)
    assert torch.version == "2.14.0+cpu"
    assert torch.source_kind == "registry"
    assert torch.source_url == PYTORCH_INDEX


def test_registry_artifacts_have_pinned_https_integrity_metadata():
    from urllib.parse import urlsplit

    lock = _validate()
    torch_missing_size = []
    for package in lock.packages:
        if package.source_kind != "registry":
            assert package.distributions == ()
            continue
        assert package.source_url in ALLOWED_REGISTRIES
        assert package.distributions
        for distribution in package.distributions:
            parsed = urlsplit(distribution.url)
            assert parsed.scheme == "https"
            assert parsed.username is None
            assert parsed.password is None
            assert parsed.hostname in ALLOWED_ARTIFACT_HOSTS
            assert len(distribution.sha256) == 64
            assert distribution.sha256 != "0" * 64
            assert distribution.sha256 == distribution.sha256.lower()
            if distribution.size_bytes is None:
                torch_missing_size.append((package.name, distribution.url))
            else:
                assert type(distribution.size_bytes) is int
                assert distribution.size_bytes > 0

    assert torch_missing_size == [
        (
            "torch",
            "https://download-r2.pytorch.org/whl/cpu/"
            "torch-2.14.0%2Bcpu-cp311-cp311-manylinux_2_28_x86_64.whl",
        )
    ]


def test_validator_requires_bytes_strict_utf8_and_valid_toml():
    with pytest.raises((TypeError, ValueError), match="bytes|payload"):
        _validate("not-bytes")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="UTF-8|TOML|payload"):
        _validate(b"\xff")
    with pytest.raises(ValueError, match="TOML|payload"):
        _validate(b"not = [valid")


def test_public_two_mib_cap_rejects_before_toml_parser(monkeypatch):
    from human_feedback import runtime_dependency_metadata as module

    assert module.MAX_UV_LOCK_BYTES == MAX_UV_LOCK_BYTES
    parsed = False

    def forbidden_loads(*args, **kwargs):
        nonlocal parsed
        parsed = True
        raise AssertionError("oversized lock must fail before TOML parsing")

    monkeypatch.setattr(module.tomllib, "loads", forbidden_loads)
    with pytest.raises(ValueError, match="lock|payload|size|limit|large"):
        module.validate_laya_uv_lock_bytes(b"x" * (MAX_UV_LOCK_BYTES + 1))

    assert parsed is False


@pytest.mark.parametrize(
    ("limit_name", "expected"),
    [
        ("MAX_UV_LOCK_PACKAGES", MAX_UV_LOCK_PACKAGES),
        ("MAX_DISTRIBUTIONS_PER_PACKAGE", MAX_DISTRIBUTIONS_PER_PACKAGE),
        ("MAX_UV_LOCK_STRING_LENGTH", MAX_UV_LOCK_STRING_LENGTH),
        ("MAX_UV_LOCK_URL_LENGTH", MAX_UV_LOCK_URL_LENGTH),
    ],
)
def test_public_structural_limits_are_explicit(limit_name, expected):
    from human_feedback import runtime_dependency_metadata as module

    assert getattr(module, limit_name) == expected


def test_package_count_limit_precedes_package_element_parsing(monkeypatch):
    from human_feedback import runtime_dependency_metadata as module

    value = _fixture_object()
    packages = value["package"]
    assert isinstance(packages, list)
    value["package"] = [deepcopy(packages[0]) for _ in range(MAX_UV_LOCK_PACKAGES + 1)]
    called = False

    def forbidden_parser(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("package amplification must fail before element parsing")

    monkeypatch.setattr(module, "_parse_package", forbidden_parser)
    with pytest.raises(ValueError, match="package|count|limit"):
        _validate_parsed(monkeypatch, value)

    assert called is False


def test_distribution_count_limit_precedes_distribution_element_parsing(monkeypatch):
    from human_feedback import runtime_dependency_metadata as module

    value = _fixture_object()
    package = value["package"][0]  # type: ignore[index]
    wheel = package["wheels"][0]
    package["wheels"] = [deepcopy(wheel) for _ in range(MAX_DISTRIBUTIONS_PER_PACKAGE + 1)]
    called = False

    def forbidden_parser(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("distribution amplification must fail before element parsing")

    monkeypatch.setattr(module, "_parse_distribution", forbidden_parser)
    with pytest.raises(ValueError, match="distribution|wheel|count|limit"):
        _validate_parsed(monkeypatch, value)

    assert called is False


@pytest.mark.parametrize("kind", ["string", "url"])
def test_strings_and_urls_are_bounded(monkeypatch, kind):
    value = _fixture_object()
    package = value["package"][0]  # type: ignore[index]
    if kind == "string":
        package["name"] = "a" * (MAX_UV_LOCK_STRING_LENGTH + 1)
    else:
        package["wheels"][0]["url"] = "https://files.pythonhosted.org/" + (
            "a" * MAX_UV_LOCK_URL_LENGTH
        )

    with pytest.raises(ValueError, match="string|name|URL|length|limit"):
        _validate_parsed(monkeypatch, value)


@pytest.mark.parametrize(
    ("old", "new"),
    [
        (b"version = 1", b"version = 2"),
        (b"revision = 3", b"revision = 4"),
        (b'requires-python = "==3.11.10"', b'requires-python = ">=3.11"'),
        (MARKER.encode("ascii"), b"sys_platform == 'linux'"),
        (EXCLUDE_NEWER.encode("ascii"), b"2026-10-11T00:00:00Z"),
        (b'specifier = "==84.0.0"', b'specifier = ">=84"'),
    ],
)
def test_lock_header_resolution_and_build_profile_are_exact(old, new):
    with pytest.raises(ValueError, match="lock|version|revision|Python|marker|build|exclude"):
        _validate(_mutated(old, new))


def test_plain_integer_fields_reject_booleans(monkeypatch):
    for field in ("version", "revision"):
        value = _fixture_object()
        value[field] = True
        with pytest.raises((TypeError, ValueError), match="integer|version|revision|lock"):
            _validate_parsed(monkeypatch, value)

    value = _fixture_object()
    value["package"][0]["wheels"][0]["size"] = True  # type: ignore[index]
    with pytest.raises((TypeError, ValueError), match="size|integer|distribution"):
        _validate_parsed(monkeypatch, value)


def test_package_names_are_canonical_lowercase_hyphenated(monkeypatch):
    value = _fixture_object()
    value["package"][0]["name"] = "Bad_Name"  # type: ignore[index]

    with pytest.raises(ValueError, match="package|name|canonical"):
        _validate_parsed(monkeypatch, value)


@pytest.mark.parametrize("case", ["duplicate", "missing", "extra"])
def test_package_collection_is_exact_without_duplicate_or_unknown_fields(monkeypatch, case):
    value = _fixture_object()
    packages = value["package"]
    assert isinstance(packages, list)
    if case == "duplicate":
        packages[-1] = deepcopy(packages[0])
    elif case == "missing":
        packages.pop()
    else:
        packages[0]["private-extra"] = "forbidden"

    with pytest.raises(ValueError, match="package|duplicate|count|field|key|exact"):
        _validate_parsed(monkeypatch, value)


def test_representational_order_of_packages_dependencies_and_distributions_is_canonicalized(
    monkeypatch,
):
    original = _validate()
    value = _fixture_object()
    packages = value["package"]
    assert isinstance(packages, list)
    for package in packages:
        if "dependencies" in package:
            package["dependencies"].reverse()
        if "wheels" in package:
            package["wheels"].reverse()
        if "optional-dependencies" in package:
            for dependencies in package["optional-dependencies"].values():
                dependencies.reverse()
    value["package"] = list(reversed(packages))

    reordered = _validate_parsed(monkeypatch, value)

    assert reordered == original
    assert reordered.semantics_sha256 == EXPECTED_LOCK_SEMANTICS_SHA256
    assert tuple(package.name for package in reordered.packages) == tuple(
        sorted(package.name for package in reordered.packages)
    )


@pytest.mark.parametrize(
    ("old", "new"),
    [
        (b'registry = "https://pypi.org/simple"', b'registry = "https://evil.invalid/simple"'),
        (b'source = { virtual = "." }', b'source = { virtual = "../private" }'),
        (LAYA_GIT.encode("ascii"), b"https://github.com/NandhaKishorM/laya?rev=main"),
        (b'source = { registry = "https://pypi.org/simple" }', b'source = { editable = "." }'),
        (b'source = { registry = "https://pypi.org/simple" }', b'source = { path = "../x" }'),
    ],
)
def test_sources_are_restricted_to_exact_allowlist_without_mutable_or_local_refs(old, new):
    with pytest.raises(ValueError, match="source|registry|git|virtual|path|editable|allow"):
        _validate(_mutated(old, new))


@pytest.mark.parametrize(
    ("old", "new"),
    [
        (b"https://files.pythonhosted.org/", b"http://files.pythonhosted.org/"),
        (b"https://files.pythonhosted.org/", b"https://user:secret@files.pythonhosted.org/"),
        (
            b"sha256:c7e58ce09192557605d8bbd92836d7e1d520ac9580096042c0bfd197efacf1bb",
            b"sha256:" + b"0" * 64,
        ),
        (b"size = 10758", b"size = true"),
    ],
)
def test_registry_artifact_urls_hashes_and_sizes_fail_closed(old, new):
    with pytest.raises((TypeError, ValueError), match="artifact|distribution|URL|hash|digest|size"):
        _validate(_mutated(old, new))


@pytest.mark.parametrize(
    ("old", "new"),
    [
        (b'{ name = "idna" }', b'{ name = "h11" }'),
        (
            b"sha256:c7e58ce09192557605d8bbd92836d7e1d520ac9580096042c0bfd197efacf1bb",
            b"sha256:" + b"f" * 64,
        ),
        (
            b"https://files.pythonhosted.org/packages/5a/8e/"
            b"38aa427ed5402449e226975b649c5dc73ccadfefeb95e6aecb8f8ea4b6b6/"
            b"annotated_doc-0.0.5.tar.gz",
            b"https://files.pythonhosted.org/packages/5a/8e/"
            b"38aa427ed5402449e226975b649c5dc73ccadfefeb95e6aecb8f8ea4b6b6/"
            b"other-valid-file.tar.gz",
        ),
    ],
    ids=["closed-edge", "valid-digest", "allowlisted-https-url"],
)
def test_structurally_valid_semantic_mutations_are_rejected(old, new):
    with pytest.raises(ValueError, match="lock|semantic|profile|exact"):
        _validate(_mutated(old, new))


def test_dependency_references_are_closed_over_locked_packages(monkeypatch):
    value = _fixture_object()
    value["package"][0]["dependencies"] = [{"name": "private-missing-package"}]  # type: ignore[index]

    with pytest.raises(ValueError, match="dependency|package|missing|closure") as error:
        _validate_parsed(monkeypatch, value)

    assert "private-missing-package" not in str(error.value)


def test_closed_graph_that_differs_from_exact_profile_is_rejected_regardless_of_cycles(
    monkeypatch,
):
    value = _fixture_object()
    packages = value["package"]
    assert isinstance(packages, list)
    packages[0]["dependencies"] = [{"name": packages[1]["name"]}]
    packages[1]["dependencies"] = [{"name": packages[0]["name"]}]

    with pytest.raises(ValueError, match="lock|semantic|profile|exact"):
        _validate_parsed(monkeypatch, value)


@pytest.mark.parametrize("case", ["other-package", "sdist-kind", "other-torch-url"])
def test_missing_distribution_size_exception_is_exactly_scoped(monkeypatch, case):
    value = _fixture_object()
    packages = value["package"]
    assert isinstance(packages, list)
    torch = next(package for package in packages if package["name"] == "torch")
    torch_wheel = deepcopy(torch["wheels"][0])
    assert "size" not in torch_wheel
    if case == "other-package":
        target = next(package for package in packages if package["name"] == "annotated-doc")
        target["wheels"] = [torch_wheel]
    elif case == "sdist-kind":
        torch["sdist"] = torch_wheel
        torch["wheels"] = []
    else:
        torch_wheel["url"] = "https://download-r2.pytorch.org/whl/cpu/other-valid-wheel.whl"
        torch["wheels"] = [torch_wheel]

    with pytest.raises(ValueError, match="torch|distribution|size|profile|exact"):
        _validate_parsed(monkeypatch, value)


@pytest.mark.parametrize(
    ("old", "new"),
    [
        (b'name = "laya-runtime-supply"', b'name = "other-root"'),
        (b'version = "0.0.0"', b'version = "1.0.0"'),
        (b'extra = ["serve"]', b'extra = ["other"]'),
        (b'extras = ["serve"]', b'extras = ["other"]'),
        (b'name = "laya"\nversion = "0.4.2"', b'name = "laya"\nversion = "0.4.3"'),
        (b"torch-2.14.0%2Bcpu", b"torch-2.15.0%2Bcpu"),
    ],
)
def test_root_laya_serve_and_torch_supply_profile_is_exact(old, new):
    with pytest.raises(ValueError, match="root|laya|torch|package|profile|metadata|serve"):
        _validate(_mutated(old, new))


def test_validated_lock_types_are_frozen_slotted_factory_sealed_and_private():
    lock = _validate()
    package = lock.packages[0]
    distribution = package.distributions[0]

    assert is_dataclass(lock)
    assert is_dataclass(package)
    assert is_dataclass(distribution)
    assert not hasattr(lock, "__dict__")
    assert not hasattr(package, "__dict__")
    assert not hasattr(distribution, "__dict__")
    with pytest.raises(FrozenInstanceError):
        lock.version = 2  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        package.name = "changed"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        distribution.url = "changed"  # type: ignore[misc]
    for value in (lock, package, distribution):
        with pytest.raises((TypeError, ValueError)):
            replace(value)

    rendered = repr(lock) + repr(lock.packages) + repr(distribution)
    assert LAYA_GIT not in rendered
    assert FIXTURE_SHA256 not in rendered
    assert "files.pythonhosted.org" not in rendered
    assert distribution.sha256 not in rendered


def test_validation_errors_do_not_echo_credentials_urls_or_digests():
    private_url = b"https://private-user:private-secret@files.pythonhosted.org/"
    payload = _mutated(b"https://files.pythonhosted.org/", private_url)

    with pytest.raises(ValueError) as error:
        _validate(payload)

    rendered = str(error.value)
    assert "private-user" not in rendered
    assert "private-secret" not in rendered
    assert private_url.decode("ascii") not in rendered


@pytest.mark.parametrize("case", ["utf8", "toml", "url"])
def test_parser_error_traceback_chain_does_not_expose_private_payload(case):
    if case == "utf8":
        marker = "private-utf8-secret"
        payload = marker.encode("ascii") + b"\xff"
    elif case == "toml":
        marker = "private-toml-secret"
        payload = f'{marker} = ["unterminated"'.encode("ascii")
    else:
        marker = "private-port-secret"
        payload = _mutated(
            b"https://files.pythonhosted.org/",
            f"https://files.pythonhosted.org:{marker}/".encode("ascii"),
        )

    with pytest.raises(ValueError) as captured:
        _validate(payload)

    error = captured.value
    rendered_chain = "".join(traceback.TracebackException.from_exception(error).format(chain=True))
    assert marker not in str(error)
    assert marker not in rendered_chain
    assert error.__cause__ is None
    assert error.__suppress_context__ is True


def test_dependency_metadata_module_is_pure_and_operationally_isolated():
    from human_feedback import runtime_dependency_metadata

    source = Path(runtime_dependency_metadata.__file__).read_text(encoding="utf-8")
    forbidden = (
        "subprocess",
        "requests",
        "httpx",
        "docker",
        "socket",
        "pathlib",
        "Path(",
        "open(",
        "read_bytes",
        "write_bytes",
        "offline_readiness",
        "experiment_runner",
        "backend",
        "adapters",
    )

    assert [token for token in forbidden if token in source] == []
    assert "human_feedback.runtime_dependency_metadata" not in "".join(
        path.read_text(encoding="utf-8")
        for root in (
            Path(__file__).parents[1] / "backend",
            Path(__file__).parents[1] / "src" / "human_feedback" / "adapters",
            Path(__file__).parents[1] / "src" / "experiment_runner",
            Path(__file__).parents[1] / "scripts",
        )
        for path in root.rglob("*.py")
    )


def test_committed_sbom_fixture_is_exact_deterministic_cyclonedx_evidence():
    payload = _sbom_fixture_bytes()
    value = _sbom_fixture_object()

    assert len(payload) == SBOM_FIXTURE_SIZE_BYTES
    assert hashlib.sha256(payload).hexdigest() == SBOM_FIXTURE_SHA256
    assert value["$schema"] == CYCLONEDX_SCHEMA
    assert len(value["components"]) == 44
    assert len(value["dependencies"]) == 45
    assert sum(len(node["dependsOn"]) for node in value["dependencies"]) == 70
    assert _canonical_sbom_semantics_sha256(value) == EXPECTED_SBOM_SEMANTICS_SHA256


def test_exact_cyclonedx_sbom_profile_loads_and_normalizes_45_identities():
    from human_feedback.runtime_dependency_metadata import (
        SbomComponent,
        SbomDependency,
        ValidatedLayaCycloneDxSbom,
    )

    sbom = _validate_sbom()

    assert isinstance(sbom, ValidatedLayaCycloneDxSbom)
    assert sbom.bom_format == "CycloneDX"
    assert sbom.spec_version == "1.6"
    assert sbom.version == 1
    assert sbom.schema == CYCLONEDX_SCHEMA
    assert sbom.semantics_sha256 == EXPECTED_SBOM_SEMANTICS_SHA256
    assert len(sbom.components) == 44
    assert len(sbom.dependencies) == 45
    assert sbom.identity_count == 45
    assert isinstance(sbom.root_component, SbomComponent)
    assert all(isinstance(component, SbomComponent) for component in sbom.components)
    assert all(isinstance(node, SbomDependency) for node in sbom.dependencies)
    identities = (sbom.root_component, *sbom.components)
    assert len({component.bom_ref for component in identities}) == 45
    assert len({component.purl for component in identities}) == 45
    for component in identities:
        expected_bom_ref = f"pkg:pypi/{component.name}@{component.version}"
        expected_purl = expected_bom_ref.replace("+", "%2B")
        assert component.bom_ref == expected_bom_ref
        assert component.purl == expected_purl


def test_torch_preserves_distinct_purl_and_bom_ref_identities_in_dependency_graph():
    sbom = _validate_sbom()
    torch = next(component for component in sbom.components if component.name == "torch")

    assert torch.version == "2.14.0+cpu"
    assert torch.purl == "pkg:pypi/torch@2.14.0%2Bcpu"
    assert torch.bom_ref == "pkg:pypi/torch@2.14.0+cpu"
    assert torch.purl != torch.bom_ref

    dependency_refs = {node.ref for node in sbom.dependencies}
    dependency_edges = {reference for node in sbom.dependencies for reference in node.depends_on}
    assert torch.bom_ref in dependency_refs
    assert torch.bom_ref in dependency_edges
    assert torch.purl not in dependency_refs
    assert torch.purl not in dependency_edges


def test_sbom_metadata_generator_lifecycle_and_lock_binding_are_exact():
    sbom = _validate_sbom()

    assert sbom.tool_name == "cdxgen"
    assert sbom.tool_version == "13.3.0"
    assert sbom.lifecycle == "pre-build"
    assert sbom.lock_sha256 == FIXTURE_SHA256
    assert sbom.uv_version == "0.12.3"
    assert sbom.root_component.name == "laya-runtime-supply"
    assert sbom.root_component.version == "0.0.0"
    assert sbom.root_component.component_type == "application"
    assert sbom.root_component.purl == "pkg:pypi/laya-runtime-supply@0.0.0"


def test_sbom_laya_vcs_reference_is_the_exact_immutable_commit():
    sbom = _validate_sbom()
    laya = next(component for component in sbom.components if component.name == "laya")

    assert laya.version == "0.4.2"
    assert laya.bom_ref == "pkg:pypi/laya@0.4.2"
    assert laya.external_references == (
        (
            "vcs",
            "git+https://github.com/NandhaKishorM/laya?rev=" f"{LAYA_COMMIT}#{LAYA_COMMIT}",
            "vcs",
        ),
    )


def test_sbom_dependencies_are_unique_closed_and_have_exact_cardinality():
    sbom = _validate_sbom()
    identities = {component.bom_ref for component in (sbom.root_component, *sbom.components)}

    assert len(sbom.dependencies) == 45
    assert len({node.ref for node in sbom.dependencies}) == 45
    assert {node.ref for node in sbom.dependencies} == identities
    assert sum(len(node.depends_on) for node in sbom.dependencies) == 70
    assert all(len(node.depends_on) == len(set(node.depends_on)) for node in sbom.dependencies)
    assert all(
        reference in identities for node in sbom.dependencies for reference in node.depends_on
    )


def test_sbom_components_make_no_selected_installed_artifact_hash_claim():
    sbom = _validate_sbom()

    assert all(component.hashes == () for component in sbom.components)
    value = _sbom_fixture_object()
    value["components"][0]["hashes"] = [  # type: ignore[index]
        {"alg": "SHA-256", "content": "f" * 64}
    ]
    with pytest.raises(ValueError, match="component|hash|profile|exact"):
        _validate_sbom(json.dumps(value).encode("utf-8"))


def test_sbom_validator_requires_bytes_strict_utf8_and_strict_json():
    with pytest.raises((TypeError, ValueError), match="bytes|payload"):
        _validate_sbom("not-bytes")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="UTF-8|JSON|payload"):
        _validate_sbom(b"\xff")
    with pytest.raises(ValueError, match="JSON|payload"):
        _validate_sbom(b'{"unterminated":[')
    duplicate = _sbom_fixture_bytes().replace(
        b'"bomFormat": "CycloneDX",',
        b'"bomFormat":"private","bomFormat":"CycloneDX",',
        1,
    )
    nonfinite = _sbom_fixture_bytes().replace(b'"confidence": 1', b'"confidence": NaN', 1)
    with pytest.raises(ValueError, match="duplicate|key|JSON"):
        _validate_sbom(duplicate)
    with pytest.raises(ValueError, match="finite|number|JSON"):
        _validate_sbom(nonfinite)


def test_public_sbom_cap_rejects_before_json_parser(monkeypatch):
    from human_feedback import runtime_dependency_metadata as module

    assert module.MAX_CYCLONEDX_SBOM_BYTES == MAX_CYCLONEDX_SBOM_BYTES
    parsed = False

    def forbidden_loads(*args, **kwargs):
        nonlocal parsed
        parsed = True
        raise AssertionError("oversized SBOM must fail before JSON parsing")

    monkeypatch.setattr(module.json, "loads", forbidden_loads)
    with pytest.raises(ValueError, match="SBOM|payload|size|limit|large"):
        module.validate_laya_cyclonedx_sbom_bytes(b"x" * (MAX_CYCLONEDX_SBOM_BYTES + 1))

    assert parsed is False


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("MAX_SBOM_COMPONENTS", MAX_SBOM_COMPONENTS),
        ("MAX_SBOM_DEPENDENCY_NODES", MAX_SBOM_DEPENDENCY_NODES),
        ("MAX_SBOM_DEPENDENCY_EDGES", MAX_SBOM_DEPENDENCY_EDGES),
        ("MAX_SBOM_STRING_LENGTH", MAX_SBOM_STRING_LENGTH),
        ("MAX_SBOM_URL_LENGTH", MAX_SBOM_URL_LENGTH),
    ],
)
def test_public_sbom_structural_caps_are_explicit(name, expected):
    from human_feedback import runtime_dependency_metadata as module

    assert getattr(module, name) == expected


@pytest.mark.parametrize("collection", ["components", "dependencies", "edges"])
def test_sbom_cardinality_limits_precede_element_parsing(monkeypatch, collection):
    from human_feedback import runtime_dependency_metadata as module

    value = _sbom_fixture_object()
    parsed = False

    def forbidden_parser(*args, **kwargs):
        nonlocal parsed
        parsed = True
        raise AssertionError("SBOM amplification must fail before element parsing")

    if collection == "components":
        value["components"] = [
            deepcopy(value["components"][0]) for _ in range(MAX_SBOM_COMPONENTS + 1)
        ]
        monkeypatch.setattr(module, "_parse_sbom_component", forbidden_parser)
    elif collection == "dependencies":
        value["dependencies"] = [
            deepcopy(value["dependencies"][0]) for _ in range(MAX_SBOM_DEPENDENCY_NODES + 1)
        ]
        monkeypatch.setattr(module, "_parse_sbom_dependency", forbidden_parser)
    else:
        value["dependencies"][0]["dependsOn"] = [  # type: ignore[index]
            "pkg:pypi/idna@3.20" for _ in range(MAX_SBOM_DEPENDENCY_EDGES + 1)
        ]
        monkeypatch.setattr(module, "_parse_sbom_dependency", forbidden_parser)

    with pytest.raises(ValueError, match="SBOM|component|dependency|edge|count|limit"):
        _validate_sbom_parsed(monkeypatch, value)

    assert parsed is False


@pytest.mark.parametrize("kind", ["string", "url"])
def test_sbom_strings_and_urls_are_bounded(monkeypatch, kind):
    value = _sbom_fixture_object()
    component = value["components"][0]  # type: ignore[index]
    if kind == "string":
        component["name"] = "a" * (MAX_SBOM_STRING_LENGTH + 1)
    else:
        component["externalReferences"][0]["url"] = (  # type: ignore[index]
            "https://files.pythonhosted.org/" + "a" * MAX_SBOM_URL_LENGTH
        )

    with pytest.raises(ValueError, match="SBOM|string|name|URL|length|limit"):
        _validate_sbom_parsed(monkeypatch, value)


@pytest.mark.parametrize(
    ("field", "invalid"),
    [
        ("bomFormat", "Other"),
        ("specVersion", "1.5"),
        ("version", 2),
        ("$schema", "https://example.invalid/schema.json"),
    ],
)
def test_sbom_header_and_official_schema_are_exact(monkeypatch, field, invalid):
    value = _sbom_fixture_object()
    value[field] = invalid

    with pytest.raises(ValueError, match="SBOM|CycloneDX|version|schema|profile|exact"):
        _validate_sbom_parsed(monkeypatch, value)


def test_sbom_version_is_plain_integer_not_boolean(monkeypatch):
    value = _sbom_fixture_object()
    value["version"] = True

    with pytest.raises((TypeError, ValueError), match="version|integer|SBOM"):
        _validate_sbom_parsed(monkeypatch, value)


@pytest.mark.parametrize("prohibited", ["serialNumber", "timestamp", "annotations"])
def test_sbom_prohibits_nondeterministic_or_annotation_fields(monkeypatch, prohibited):
    value = _sbom_fixture_object()
    value[prohibited] = "private-forbidden"

    with pytest.raises(ValueError, match="SBOM|field|key|exact|deterministic"):
        _validate_sbom_parsed(monkeypatch, value)


@pytest.mark.parametrize("case", ["missing", "unknown", "duplicate"])
def test_sbom_components_are_exact_unique_and_complete(monkeypatch, case):
    value = _sbom_fixture_object()
    components = value["components"]
    assert isinstance(components, list)
    if case == "missing":
        components.pop()
    elif case == "unknown":
        components[0]["private-extra"] = "forbidden"
    else:
        components[-1] = deepcopy(components[0])

    with pytest.raises(ValueError, match="component|duplicate|count|field|key|exact"):
        _validate_sbom_parsed(monkeypatch, value)


@pytest.mark.parametrize("case", ["missing", "duplicate", "unknown-ref", "unknown-edge"])
def test_sbom_dependency_graph_is_exact_unique_and_closed(monkeypatch, case):
    value = _sbom_fixture_object()
    dependencies = value["dependencies"]
    assert isinstance(dependencies, list)
    if case == "missing":
        dependencies.pop()
    elif case == "duplicate":
        dependencies[-1] = deepcopy(dependencies[0])
    elif case == "unknown-ref":
        dependencies[0]["ref"] = "pkg:pypi/private-missing@1.0.0"
    else:
        dependencies[0]["dependsOn"] = ["pkg:pypi/private-missing@1.0.0"]

    with pytest.raises(ValueError, match="dependency|reference|duplicate|count|closed|exact"):
        _validate_sbom_parsed(monkeypatch, value)


def _replace_all_string_values(value, old: str, new: str) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if item == old:
                value[key] = new
            else:
                _replace_all_string_values(item, old, new)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            if item == old:
                value[index] = new
            else:
                _replace_all_string_values(item, old, new)


@pytest.mark.parametrize(
    "case",
    ["component", "purl-ref", "edge", "tool", "property", "url"],
)
def test_semantically_valid_but_different_sbom_is_rejected(monkeypatch, case):
    value = _sbom_fixture_object()
    if case == "component":
        component = value["components"][0]  # type: ignore[index]
        old_ref = component["bom-ref"]
        new_ref = old_ref.replace("@0.0.5", "@0.0.6")
        component["version"] = "0.0.6"
        _replace_all_string_values(value, old_ref, new_ref)
    elif case == "purl-ref":
        component = value["components"][0]  # type: ignore[index]
        old_ref = component["bom-ref"]
        new_ref = "pkg:pypi/annotated-doc-renamed@0.0.5"
        component["name"] = "annotated-doc-renamed"
        _replace_all_string_values(value, old_ref, new_ref)
    elif case == "edge":
        node = next(
            item for item in value["dependencies"] if "pkg:pypi/idna@3.20" in item["dependsOn"]
        )
        node["dependsOn"][node["dependsOn"].index("pkg:pypi/idna@3.20")] = "pkg:pypi/h11@0.16.0"
    elif case == "tool":
        tool = value["metadata"]["tools"]["components"][0]  # type: ignore[index]
        tool["version"] = "13.3.1"
        tool["purl"] = "pkg:npm/%40cdxgen/cdxgen@13.3.1"
        tool["bom-ref"] = "pkg:npm/@cdxgen/cdxgen@13.3.1"
    elif case == "property":
        prop = next(
            item
            for item in value["metadata"]["properties"]  # type: ignore[index]
            if item["name"] == "aai:uv-generator"
        )
        prop["value"] = "uv==0.12.4"
    else:
        reference = value["components"][0]["externalReferences"][0]  # type: ignore[index]
        reference["url"] = "https://files.pythonhosted.org/packages/other-valid-file.whl"

    with pytest.raises(ValueError, match="SBOM|semantic|profile|exact"):
        _validate_sbom_parsed(monkeypatch, value)


def test_sbom_representational_array_order_is_canonicalized(monkeypatch):
    original = _validate_sbom()
    value = _sbom_fixture_object()
    value["components"].reverse()  # type: ignore[union-attr]
    value["dependencies"].reverse()  # type: ignore[union-attr]
    value["metadata"]["properties"].reverse()  # type: ignore[index]
    for component in value["components"]:  # type: ignore[union-attr]
        for key in ("properties", "externalReferences"):
            if key in component:
                component[key].reverse()
    for dependency in value["dependencies"]:  # type: ignore[union-attr]
        dependency["dependsOn"].reverse()

    reordered = _validate_sbom_parsed(monkeypatch, value)

    assert reordered == original
    assert reordered.semantics_sha256 == EXPECTED_SBOM_SEMANTICS_SHA256


def test_sbom_types_are_frozen_slotted_factory_sealed_and_private():
    sbom = _validate_sbom()
    component = sbom.components[0]
    dependency = sbom.dependencies[0]

    for value in (sbom, component, dependency):
        assert is_dataclass(value)
        assert not hasattr(value, "__dict__")
        with pytest.raises((TypeError, ValueError)):
            replace(value)
    with pytest.raises(FrozenInstanceError):
        sbom.version = 2  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        component.name = "changed"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        dependency.ref = "changed"  # type: ignore[misc]

    rendered = repr(sbom) + repr(sbom.components) + repr(sbom.dependencies)
    assert SBOM_FIXTURE_SHA256 not in rendered
    assert EXPECTED_SBOM_SEMANTICS_SHA256 not in rendered
    assert "files.pythonhosted.org" not in rendered
    assert LAYA_COMMIT not in rendered


@pytest.mark.parametrize("case", ["utf8", "json", "recursion", "url"])
def test_sbom_parser_error_chain_is_generic_and_private(case):
    if case == "utf8":
        marker = "private-sbom-utf8"
        payload = marker.encode("ascii") + b"\xff"
    elif case == "json":
        marker = "private-sbom-json"
        payload = f'{{"{marker}":['.encode("ascii")
    elif case == "recursion":
        marker = "private-sbom-recursion"
        payload = (
            b'{"private":' + b"[" * 2_000 + f'"{marker}"'.encode("ascii") + b"]" * 2_000 + b"}"
        )
    else:
        marker = "private-sbom-port"
        value = _sbom_fixture_object()
        value["components"][0]["externalReferences"][0]["url"] = (  # type: ignore[index]
            f"https://files.pythonhosted.org:{marker}/artifact.whl"
        )
        payload = json.dumps(value).encode("utf-8")

    with pytest.raises(ValueError) as captured:
        _validate_sbom(payload)

    error = captured.value
    rendered_chain = "".join(traceback.TracebackException.from_exception(error).format(chain=True))
    assert marker not in str(error)
    assert marker not in rendered_chain
    assert error.__cause__ is None
    assert error.__suppress_context__ is True
