import hashlib
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
MAX_UV_LOCK_BYTES = 2 * 1024 * 1024
MAX_UV_LOCK_PACKAGES = 512
MAX_DISTRIBUTIONS_PER_PACKAGE = 256
MAX_UV_LOCK_STRING_LENGTH = 1_024
MAX_UV_LOCK_URL_LENGTH = 4_096
MARKER = (
    "implementation_name == 'cpython' and platform_machine == 'x86_64' "
    "and sys_platform == 'linux'"
)
EXCLUDE_NEWER = "2026-10-10T09:19:05Z"
LAYA_COMMIT = "68804629e8ccd9d616d48a40e87de9fabbeae069"
LAYA_GIT = "https://github.com/NandhaKishorM/laya?rev=" f"{LAYA_COMMIT}#{LAYA_COMMIT}"
PYTORCH_INDEX = "https://download.pytorch.org/whl/cpu"
ALLOWED_REGISTRIES = {"https://pypi.org/simple", PYTORCH_INDEX}
ALLOWED_ARTIFACT_HOSTS = {"files.pythonhosted.org", "download-r2.pytorch.org"}


def _fixture_path() -> Path:
    return Path(__file__).parent / "fixtures" / "laya" / "runtime_dependency" / "uv.lock"


def _fixture_bytes() -> bytes:
    return _fixture_path().read_bytes()


def _fixture_object() -> dict[str, object]:
    return tomllib.loads(_fixture_bytes().decode("utf-8"))


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


def _package(lock, name: str):
    return next(item for item in lock.packages if item.name == name)


def test_committed_uv_lock_fixture_is_exact_generated_evidence():
    payload = _fixture_bytes()

    assert len(payload) == FIXTURE_SIZE_BYTES
    assert hashlib.sha256(payload).hexdigest() == FIXTURE_SHA256
    assert len(_fixture_object()["package"]) == 45


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


def test_package_input_order_is_canonicalized(monkeypatch):
    original = _validate()
    value = _fixture_object()
    value["package"] = list(reversed(value["package"]))  # type: ignore[arg-type]

    reordered = _validate_parsed(monkeypatch, value)

    assert reordered == original
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


def test_dependency_references_are_closed_over_locked_packages(monkeypatch):
    value = _fixture_object()
    value["package"][0]["dependencies"] = [{"name": "private-missing-package"}]  # type: ignore[index]

    with pytest.raises(ValueError, match="dependency|package|missing|closure") as error:
        _validate_parsed(monkeypatch, value)

    assert "private-missing-package" not in str(error.value)


def test_dependency_cycles_are_not_rejected_by_the_structural_validator(monkeypatch):
    value = _fixture_object()
    packages = value["package"]
    assert isinstance(packages, list)
    packages[0]["dependencies"] = [{"name": packages[1]["name"]}]
    packages[1]["dependencies"] = [{"name": packages[0]["name"]}]

    lock = _validate_parsed(monkeypatch, value)

    assert len(lock.packages) == 45


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
