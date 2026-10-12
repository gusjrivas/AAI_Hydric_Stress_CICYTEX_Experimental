"""Pure validation of the pinned Laya dependency lock evidence."""

from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from dataclasses import InitVar, dataclass
from typing import Any
from urllib.parse import urlsplit

try:
    import tomllib as _toml_parser
except ModuleNotFoundError:  # pragma: no cover - Python 3.10 compatibility
    import tomli as _toml_parser


class _TomlReader:
    loads = staticmethod(_toml_parser.loads)
    TOMLDecodeError = _toml_parser.TOMLDecodeError


# A narrow facade keeps parser substitution local to this contract module.
tomllib = _TomlReader()

MAX_UV_LOCK_BYTES = 2 * 1024 * 1024
MAX_UV_LOCK_PACKAGES = 512
MAX_DISTRIBUTIONS_PER_PACKAGE = 256
MAX_UV_LOCK_STRING_LENGTH = 1_024
MAX_UV_LOCK_URL_LENGTH = 4_096

_MARKER = (
    "implementation_name == 'cpython' and platform_machine == 'x86_64' "
    "and sys_platform == 'linux'"
)
_EXCLUDE_NEWER = "2026-10-10T09:19:05Z"
_LAYA_COMMIT = "68804629e8ccd9d616d48a40e87de9fabbeae069"
_LAYA_GIT = f"https://github.com/NandhaKishorM/laya?rev={_LAYA_COMMIT}#{_LAYA_COMMIT}"
_LAYA_METADATA_GIT = f"https://github.com/NandhaKishorM/laya?rev={_LAYA_COMMIT}"
_PYTORCH_INDEX = "https://download.pytorch.org/whl/cpu"
_PYPI_INDEX = "https://pypi.org/simple"
_TORCH_WHEEL = (
    "https://download-r2.pytorch.org/whl/cpu/"
    "torch-2.14.0%2Bcpu-cp311-cp311-manylinux_2_28_x86_64.whl"
)
_ALLOWED_REGISTRIES = frozenset({_PYPI_INDEX, _PYTORCH_INDEX})
_ALLOWED_ARTIFACT_HOSTS = frozenset({"files.pythonhosted.org", "download-r2.pytorch.org"})
_EXPECTED_PROFILE_SHA256 = "6aeabdd83e78efb1a8a0bfeba61f2d9f4c9505cbde40dcee22020866451c75ed"
_EXPECTED_SEMANTICS_SHA256 = "c4e1d2876569217c106d9a32fdfacb5a88c1fbd4808fe90c828ba8073a9ab45e"
_PACKAGE_NAME = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
_FACTORY_TOKEN = object()


def _private_repr(value: object) -> str:
    return f"<{type(value).__name__}: validated private evidence>"


@dataclass(frozen=True, slots=True, repr=False)
class LockedDistribution:
    url: str
    sha256: str
    size_bytes: int | None
    _factory_token: InitVar[object]

    def __post_init__(self, _factory_token: object) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise ValueError("distribution construction is factory-sealed")
        if not isinstance(self.url, str) or not isinstance(self.sha256, str):
            raise TypeError("distribution fields are invalid")
        if self.size_bytes is not None and (
            type(self.size_bytes) is not int or self.size_bytes <= 0
        ):
            raise ValueError("distribution size is invalid")

    __repr__ = _private_repr


@dataclass(frozen=True, slots=True, repr=False)
class LockedPackage:
    name: str
    version: str
    source_kind: str
    source_url: str
    dependencies: tuple[str, ...]
    optional_dependencies: tuple[tuple[str, tuple[str, ...]], ...]
    distributions: tuple[LockedDistribution, ...]
    _factory_token: InitVar[object]

    def __post_init__(self, _factory_token: object) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise ValueError("package construction is factory-sealed")
        if not _PACKAGE_NAME.fullmatch(self.name):
            raise ValueError("package name is not canonical")
        if self.source_kind not in {"registry", "git", "virtual"}:
            raise ValueError("package source is invalid")

    __repr__ = _private_repr


@dataclass(frozen=True, slots=True, repr=False)
class ValidatedLayaUvLock:
    version: int
    revision: int
    requires_python: str
    resolution_markers: tuple[str, ...]
    supported_markers: tuple[str, ...]
    required_markers: tuple[str, ...]
    exclude_newer: str
    build_constraints: tuple[tuple[str, str], ...]
    packages: tuple[LockedPackage, ...]
    semantics_sha256: str
    _factory_token: InitVar[object]

    def __post_init__(self, _factory_token: object) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise ValueError("lock construction is factory-sealed")
        if type(self.version) is not int or type(self.revision) is not int:
            raise TypeError("lock version and revision must be plain integers")
        if self.semantics_sha256 != _EXPECTED_SEMANTICS_SHA256:
            raise ValueError("lock semantic commitment is invalid")

    __repr__ = _private_repr


def _mapping(value: object, *, context: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{context} must be a table")
    return value


def _exact_keys(value: dict[str, Any], expected: set[str], *, context: str) -> None:
    if set(value) != expected:
        raise ValueError(f"{context} fields are not exact")


def _string(value: object, *, context: str, url: bool = False) -> str:
    limit = MAX_UV_LOCK_URL_LENGTH if url else MAX_UV_LOCK_STRING_LENGTH
    if not isinstance(value, str) or not value or len(value) > limit:
        kind = "URL" if url else "string"
        raise ValueError(f"{context} {kind} length exceeds its limit or is invalid")
    return value


def _string_list(value: object, *, context: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ValueError(f"{context} must be a list")
    return tuple(_string(item, context=context) for item in value)


def _parse_dependency(value: object) -> tuple[str, tuple[str, ...]]:
    item = _mapping(value, context="package dependency")
    if set(item) not in ({"name"}, {"name", "extra"}):
        raise ValueError("package dependency fields are not exact")
    name = _string(item.get("name"), context="package dependency name")
    if not _PACKAGE_NAME.fullmatch(name):
        raise ValueError("package dependency name is not canonical")
    extras = (
        _string_list(item["extra"], context="package dependency extra") if "extra" in item else ()
    )
    return name, extras


def _parse_distribution(
    value: object, *, package_name: str, distribution_kind: str
) -> LockedDistribution:
    item = _mapping(value, context="distribution")
    if set(item) not in (
        {"url", "hash", "size", "upload-time"},
        {"url", "hash", "upload-time"},
    ):
        raise ValueError("distribution fields are not exact")
    url = _string(item.get("url"), context="distribution", url=True)
    try:
        parsed = urlsplit(url)
        allowed = (
            parsed.scheme == "https"
            and parsed.username is None
            and parsed.password is None
            and parsed.hostname in _ALLOWED_ARTIFACT_HOSTS
            and parsed.port is None
        )
    except ValueError:
        raise ValueError("distribution URL is not allowed") from None
    if not allowed:
        raise ValueError("distribution URL is not allowed")
    raw_hash = _string(item.get("hash"), context="distribution hash")
    if not raw_hash.startswith("sha256:"):
        raise ValueError("distribution hash algorithm is invalid")
    digest = raw_hash.removeprefix("sha256:")
    if not _DIGEST.fullmatch(digest) or digest == "0" * 64:
        raise ValueError("distribution digest is invalid")
    _string(item.get("upload-time"), context="distribution upload time")
    if "size" in item:
        size = item["size"]
        if type(size) is not int or size <= 0:
            raise ValueError("distribution size must be a positive integer")
    else:
        # The sole size omission accepted by this contract is the exact pinned
        # torch CPU wheel below; no package, URL, or artifact-kind generalization
        # is permitted.
        if package_name != "torch" or distribution_kind != "wheel" or url != _TORCH_WHEEL:
            raise ValueError("torch profile distribution size is required")
        size = None
    return LockedDistribution(url, digest, size, _factory_token=_FACTORY_TOKEN)


def _parse_optional_dependencies(value: object) -> tuple[tuple[str, tuple[str, ...]], ...]:
    table = _mapping(value, context="optional dependencies")
    result: list[tuple[str, tuple[str, ...]]] = []
    for extra, raw_dependencies in table.items():
        extra_name = _string(extra, context="optional dependency group")
        if not isinstance(raw_dependencies, list):
            raise ValueError("optional dependencies must be a list")
        names: list[str] = []
        for raw_dependency in raw_dependencies:
            dependency = _mapping(raw_dependency, context="optional dependency")
            _exact_keys(dependency, {"name"}, context="optional dependency")
            name, extras = _parse_dependency(dependency)
            if extras:
                raise ValueError("optional dependency fields are not exact")
            names.append(name)
        result.append((extra_name, tuple(sorted(names))))
    return tuple(sorted(result))


def _validate_root_profile(
    item: dict[str, Any], dependencies: list[tuple[str, tuple[str, ...]]]
) -> None:
    if sorted(dependencies) != [("laya", ("serve",)), ("torch", ())]:
        raise ValueError("root package serve profile is invalid")
    metadata = _mapping(item.get("metadata"), context="root package metadata")
    _exact_keys(metadata, {"requires-dist"}, context="root package metadata")
    required = metadata["requires-dist"]
    expected = [
        {"name": "laya", "extras": ["serve"], "git": _LAYA_METADATA_GIT},
        {"name": "torch", "specifier": "==2.14.0", "index": _PYTORCH_INDEX},
    ]
    if not isinstance(required, list) or sorted(
        required, key=lambda value: json.dumps(value, sort_keys=True, separators=(",", ":"))
    ) != sorted(
        expected, key=lambda value: json.dumps(value, sort_keys=True, separators=(",", ":"))
    ):
        raise ValueError("root package metadata profile is invalid")


def _canonical_semantics_sha256(value: dict[str, Any]) -> str:
    normalized = deepcopy(value)
    packages = normalized["package"]
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
    try:
        encoded = json.dumps(
            normalized,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("ascii")
    except (TypeError, ValueError, RecursionError):
        raise ValueError("lock semantic profile cannot be canonicalized") from None
    return hashlib.sha256(encoded).hexdigest()


def _parse_package(value: object) -> LockedPackage:
    item = _mapping(value, context="package")
    allowed = {
        "name",
        "version",
        "source",
        "dependencies",
        "optional-dependencies",
        "metadata",
        "sdist",
        "wheels",
    }
    if not {"name", "version", "source"}.issubset(item) or not set(item).issubset(allowed):
        raise ValueError("package fields are not exact")
    name = _string(item["name"], context="package name")
    version = _string(item["version"], context="package version")
    if not _PACKAGE_NAME.fullmatch(name):
        raise ValueError("package name is not canonical")
    source = _mapping(item["source"], context="package source")
    if len(source) != 1:
        raise ValueError("package source fields are not exact")
    source_kind, raw_source_url = next(iter(source.items()))
    source_url = _string(raw_source_url, context="package source", url=source_kind != "virtual")
    if source_kind == "registry":
        if source_url not in _ALLOWED_REGISTRIES:
            raise ValueError("package registry source is not allowed")
    elif source_kind == "git":
        if source_url != _LAYA_GIT:
            raise ValueError("package git source is not allowed")
    elif source_kind == "virtual":
        if source_url != ".":
            raise ValueError("package virtual source is not allowed")
    else:
        raise ValueError("package source kind is not allowed")

    raw_dependencies = item.get("dependencies", [])
    if not isinstance(raw_dependencies, list):
        raise ValueError("package dependencies must be a list")
    parsed_dependencies = [_parse_dependency(dependency) for dependency in raw_dependencies]
    dependencies = tuple(sorted(name for name, _extras in parsed_dependencies))
    optional = (
        _parse_optional_dependencies(item["optional-dependencies"])
        if "optional-dependencies" in item
        else ()
    )

    raw_wheels = item.get("wheels", [])
    if not isinstance(raw_wheels, list):
        raise ValueError("package wheels must be a list")
    raw_sdist = [item["sdist"]] if "sdist" in item else []
    if len(raw_wheels) + len(raw_sdist) > MAX_DISTRIBUTIONS_PER_PACKAGE:
        raise ValueError("distribution count exceeds package limit")
    distributions = tuple(
        sorted(
            (
                *(
                    _parse_distribution(raw, package_name=name, distribution_kind="sdist")
                    for raw in raw_sdist
                ),
                *(
                    _parse_distribution(raw, package_name=name, distribution_kind="wheel")
                    for raw in raw_wheels
                ),
            ),
            key=lambda distribution: distribution.url,
        )
    )

    if source_kind == "registry":
        if not distributions or "metadata" in item or "optional-dependencies" in item:
            raise ValueError("registry package profile is invalid")
        expected_registry = _PYTORCH_INDEX if name == "torch" else _PYPI_INDEX
        if source_url != expected_registry:
            raise ValueError("registry package source profile is invalid")
    elif source_kind == "git":
        if name != "laya" or distributions or "metadata" in item:
            raise ValueError("laya package profile is invalid")
    elif source_kind == "virtual":
        if name != "laya-runtime-supply" or distributions or "optional-dependencies" in item:
            raise ValueError("root package profile is invalid")

    if name == "laya":
        if (
            version != "0.4.2"
            or dependencies != ("huggingface-hub", "numpy", "safetensors", "torch", "transformers")
            or optional != (("serve", ("fastapi", "python-multipart", "uvicorn")),)
        ):
            raise ValueError("laya package serve profile is invalid")
    elif name == "laya-runtime-supply":
        if version != "0.0.0":
            raise ValueError("root package profile is invalid")
        _validate_root_profile(item, parsed_dependencies)
    elif name == "torch":
        if version != "2.14.0+cpu" or tuple(item.url for item in distributions) != (_TORCH_WHEEL,):
            raise ValueError("torch package profile is invalid")

    return LockedPackage(
        name,
        version,
        source_kind,
        source_url,
        dependencies,
        optional,
        distributions,
        _factory_token=_FACTORY_TOKEN,
    )


def _header(value: dict[str, Any]) -> tuple[object, ...]:
    if type(value.get("version")) is not int or value["version"] != 1:
        raise ValueError("lock version profile is invalid")
    if type(value.get("revision")) is not int or value["revision"] != 3:
        raise ValueError("lock revision profile is invalid")
    requires_python = _string(value.get("requires-python"), context="lock Python profile")
    if requires_python != "==3.11.10":
        raise ValueError("lock Python profile is invalid")
    markers: list[tuple[str, ...]] = []
    for key in ("resolution-markers", "supported-markers", "required-markers"):
        current = _string_list(value.get(key), context="lock marker")
        if current != (_MARKER,):
            raise ValueError("lock marker profile is invalid")
        markers.append(current)
    options = _mapping(value.get("options"), context="lock options")
    _exact_keys(options, {"exclude-newer"}, context="lock options")
    exclude_newer = _string(options["exclude-newer"], context="lock exclude profile")
    if exclude_newer != _EXCLUDE_NEWER:
        raise ValueError("lock exclude profile is invalid")
    manifest = _mapping(value.get("manifest"), context="lock manifest")
    _exact_keys(manifest, {"build-constraints"}, context="lock manifest")
    constraints = manifest["build-constraints"]
    if constraints != [{"name": "setuptools", "specifier": "==84.0.0"}]:
        raise ValueError("lock build constraint profile is invalid")
    return (requires_python, *markers, exclude_newer, (("setuptools", "==84.0.0"),))


def validate_laya_uv_lock_bytes(payload: bytes) -> ValidatedLayaUvLock:
    """Validate lock bytes without consulting mutable external state."""

    if not isinstance(payload, bytes):
        raise TypeError("lock payload must be bytes")
    if len(payload) > MAX_UV_LOCK_BYTES:
        raise ValueError("lock payload size exceeds limit")
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError:
        raise ValueError("lock payload is not strict UTF-8") from None
    try:
        parsed = tomllib.loads(text)
    except Exception:
        raise ValueError("lock payload is not valid TOML") from None
    root = _mapping(parsed, context="lock payload")
    _exact_keys(
        root,
        {
            "version",
            "revision",
            "requires-python",
            "resolution-markers",
            "supported-markers",
            "required-markers",
            "options",
            "manifest",
            "package",
        },
        context="lock",
    )
    header = _header(root)
    raw_packages = root["package"]
    if not isinstance(raw_packages, list):
        raise ValueError("lock package collection must be a list")
    if len(raw_packages) > MAX_UV_LOCK_PACKAGES:
        raise ValueError("lock package count exceeds limit")
    if len(raw_packages) != 45:
        raise ValueError("lock package count is not exact")
    packages = tuple(
        sorted((_parse_package(item) for item in raw_packages), key=lambda item: item.name)
    )
    names = tuple(package.name for package in packages)
    if len(set(names)) != len(names):
        raise ValueError("lock package names contain a duplicate")
    profile = json.dumps([(item.name, item.version) for item in packages], separators=(",", ":"))
    if hashlib.sha256(profile.encode("utf-8")).hexdigest() != _EXPECTED_PROFILE_SHA256:
        raise ValueError("lock package profile is not exact")
    name_set = set(names)
    if any(
        dependency not in name_set
        for package in packages
        for dependency in (
            *package.dependencies,
            *(
                name
                for _extra, dependencies in package.optional_dependencies
                for name in dependencies
            ),
        )
    ):
        raise ValueError("lock dependency closure references a missing package")
    semantics_sha256 = _canonical_semantics_sha256(root)
    if semantics_sha256 != _EXPECTED_SEMANTICS_SHA256:
        raise ValueError("lock semantic profile is not exact")
    requires_python, resolution, supported, required, exclude_newer, constraints = header
    return ValidatedLayaUvLock(
        1,
        3,
        requires_python,
        resolution,
        supported,
        required,
        exclude_newer,
        constraints,
        packages,
        semantics_sha256,
        _factory_token=_FACTORY_TOKEN,
    )
