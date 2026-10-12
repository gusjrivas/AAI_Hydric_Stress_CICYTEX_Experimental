"""Pure validation of the pinned Laya dependency lock evidence."""

from __future__ import annotations

import hashlib
import json as _json_parser
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


def _reject_duplicate_json_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _reject_nonfinite_json_number(_value: str) -> None:
    raise ValueError("JSON number must be finite")


def _strict_json_loads(text: str) -> object:
    return _json_parser.loads(
        text,
        object_pairs_hook=_reject_duplicate_json_keys,
        parse_constant=_reject_nonfinite_json_number,
    )


class _JsonReader:
    loads = staticmethod(_strict_json_loads)
    dumps = staticmethod(_json_parser.dumps)


# A narrow facade permits parser substitution without mutating the process module.
json = _JsonReader()

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
_EXPECTED_SBOM_SEMANTICS_SHA256 = "c2feadbd7103a8b27a435a682ee7ba4a9fdc90e4ebbf358b2f0b892bb73721fe"
_CYCLONEDX_SCHEMA = "https://cyclonedx.org/schema/bom-1.6.schema.json"
_LOCK_SHA256 = "e968771680b9c6e683163230ebd98b43541325ccb36d6959d1f9ed5565bd5526"
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


@dataclass(frozen=True, slots=True, repr=False)
class SbomComponent:
    name: str
    version: str
    component_type: str
    purl: str
    bom_ref: str
    external_references: tuple[tuple[str, str, str], ...]
    properties: tuple[tuple[str, str], ...]
    tags: tuple[str, ...]
    hashes: tuple[tuple[str, str], ...]
    _factory_token: InitVar[object]

    def __post_init__(self, _factory_token: object) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise ValueError("SBOM component construction is factory-sealed")
        if not _PACKAGE_NAME.fullmatch(self.name):
            raise ValueError("SBOM component name is not canonical")
        expected_bom_ref = f"pkg:pypi/{self.name}@{self.version}"
        expected_purl = expected_bom_ref.replace("+", "%2B")
        if self.bom_ref != expected_bom_ref or self.purl != expected_purl:
            raise ValueError("SBOM component identity is invalid")
        if self.hashes:
            raise ValueError("SBOM component hash claims are forbidden")

    __repr__ = _private_repr


@dataclass(frozen=True, slots=True, repr=False)
class SbomDependency:
    ref: str
    depends_on: tuple[str, ...]
    _factory_token: InitVar[object]

    def __post_init__(self, _factory_token: object) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise ValueError("SBOM dependency construction is factory-sealed")
        if len(self.depends_on) != len(set(self.depends_on)):
            raise ValueError("SBOM dependency edges are not exact")

    __repr__ = _private_repr


@dataclass(frozen=True, slots=True, repr=False)
class ValidatedLayaCycloneDxSbom:
    bom_format: str
    spec_version: str
    version: int
    schema: str
    tool_name: str
    tool_version: str
    lifecycle: str
    lock_sha256: str
    uv_version: str
    root_component: SbomComponent
    components: tuple[SbomComponent, ...]
    dependencies: tuple[SbomDependency, ...]
    identity_count: int
    semantics_sha256: str
    _factory_token: InitVar[object]

    def __post_init__(self, _factory_token: object) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise ValueError("SBOM construction is factory-sealed")
        if type(self.version) is not int:
            raise TypeError("SBOM version must be a plain integer")
        if self.semantics_sha256 != _EXPECTED_SBOM_SEMANTICS_SHA256:
            raise ValueError("SBOM semantic commitment is invalid")
        if self.identity_count != len(self.components) + 1:
            raise ValueError("SBOM identity count is invalid")

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


def _sbom_string(value: object, *, context: str, url: bool = False) -> str:
    limit = MAX_SBOM_URL_LENGTH if url else MAX_SBOM_STRING_LENGTH
    if not isinstance(value, str) or not value or len(value) > limit:
        kind = "URL" if url else "string"
        raise ValueError(f"SBOM {context} {kind} length exceeds its limit or is invalid")
    return value


def _sbom_properties(value: object, *, context: str) -> tuple[tuple[str, str], ...]:
    if not isinstance(value, list):
        raise ValueError(f"SBOM {context} properties must be a list")
    result: list[tuple[str, str]] = []
    for raw_property in value:
        prop = _mapping(raw_property, context=f"SBOM {context} property")
        _exact_keys(prop, {"name", "value"}, context=f"SBOM {context} property")
        result.append(
            (
                _sbom_string(prop["name"], context=f"{context} property name"),
                _sbom_string(prop["value"], context=f"{context} property value"),
            )
        )
    if len(result) != len({name for name, _value in result}):
        raise ValueError(f"SBOM {context} properties contain a duplicate")
    return tuple(sorted(result))


def _sbom_external_reference(value: object) -> tuple[str, str, str]:
    reference = _mapping(value, context="SBOM component external reference")
    _exact_keys(
        reference,
        {"type", "url", "comment"},
        context="SBOM component external reference",
    )
    kind = _sbom_string(reference["type"], context="external reference type")
    comment = _sbom_string(reference["comment"], context="external reference comment")
    url = _sbom_string(reference["url"], context="external reference", url=True)
    if (kind, comment) not in {
        ("distribution", "wheel"),
        ("distribution", "sdist"),
        ("vcs", "vcs"),
    }:
        raise ValueError("SBOM component external reference profile is invalid")
    try:
        parsed = urlsplit(url)
        allowed = (
            parsed.username is None
            and parsed.password is None
            and parsed.port is None
            and (
                (
                    kind == "distribution"
                    and parsed.scheme == "https"
                    and parsed.hostname in _ALLOWED_ARTIFACT_HOSTS
                )
                or (
                    kind == "vcs"
                    and parsed.scheme == "git+https"
                    and parsed.hostname == "github.com"
                )
            )
        )
    except ValueError:
        raise ValueError("SBOM component external reference URL is invalid") from None
    if not allowed:
        raise ValueError("SBOM component external reference URL is invalid")
    return kind, url, comment


def _validate_sbom_evidence(value: object) -> None:
    expected = {
        "identity": [
            {
                "field": "purl",
                "confidence": 1,
                "methods": [
                    {"technique": "manifest-analysis", "confidence": 1, "value": "uv.lock"}
                ],
                "concludedValue": "uv.lock",
            }
        ]
    }
    if value != expected:
        raise ValueError("SBOM component evidence profile is not exact")


def _parse_sbom_component(value: object) -> SbomComponent:
    component = _mapping(value, context="SBOM component")
    required = {
        "group",
        "name",
        "version",
        "purl",
        "externalReferences",
        "type",
        "bom-ref",
        "properties",
        "evidence",
    }
    if set(component) not in (required, required | {"tags"}):
        raise ValueError("SBOM component fields are not exact")
    if component["group"] != "":
        raise ValueError("SBOM component group profile is not exact")
    name = _sbom_string(component["name"], context="component name")
    version = _sbom_string(component["version"], context="component version")
    if not _PACKAGE_NAME.fullmatch(name):
        raise ValueError("SBOM component name is not canonical")
    purl = _sbom_string(component["purl"], context="component purl", url=True)
    bom_ref = _sbom_string(component["bom-ref"], context="component reference", url=True)
    canonical_ref = f"pkg:pypi/{name}@{version}"
    encoded_purl = f"pkg:pypi/{name}@{version.replace('+', '%2B')}"
    if purl != encoded_purl or bom_ref != canonical_ref:
        raise ValueError("SBOM component purl reference profile is not exact")
    component_type = _sbom_string(component["type"], context="component type")
    if component_type not in {"library", "framework"}:
        raise ValueError("SBOM component type profile is not exact")
    raw_references = component["externalReferences"]
    if not isinstance(raw_references, list) or not raw_references:
        raise ValueError("SBOM component external references are invalid")
    references = tuple(sorted(_sbom_external_reference(item) for item in raw_references))
    properties = _sbom_properties(component["properties"], context="component")
    raw_tags = component.get("tags", [])
    if not isinstance(raw_tags, list):
        raise ValueError("SBOM component tags must be a list")
    tags = tuple(_sbom_string(item, context="component tag") for item in raw_tags)
    if len(tags) != len(set(tags)):
        raise ValueError("SBOM component tags contain a duplicate")
    _validate_sbom_evidence(component["evidence"])
    return SbomComponent(
        name,
        version,
        component_type,
        purl,
        bom_ref,
        references,
        properties,
        tags,
        (),
        _factory_token=_FACTORY_TOKEN,
    )


def _parse_sbom_dependency(value: object) -> SbomDependency:
    node = _mapping(value, context="SBOM dependency")
    _exact_keys(node, {"ref", "dependsOn"}, context="SBOM dependency")
    ref = _sbom_string(node["ref"], context="dependency reference", url=True)
    raw_edges = node["dependsOn"]
    if not isinstance(raw_edges, list):
        raise ValueError("SBOM dependency edges must be a list")
    edges = tuple(
        sorted(_sbom_string(item, context="dependency edge", url=True) for item in raw_edges)
    )
    return SbomDependency(ref, edges, _factory_token=_FACTORY_TOKEN)


def _parse_sbom_metadata(value: object) -> tuple[str, str, str, str, str, SbomComponent]:
    metadata = _mapping(value, context="SBOM metadata")
    _exact_keys(
        metadata,
        {"tools", "authors", "lifecycles", "component", "properties"},
        context="SBOM metadata",
    )
    tools = _mapping(metadata["tools"], context="SBOM tools")
    _exact_keys(tools, {"components"}, context="SBOM tools")
    tool_components = tools["components"]
    expected_tool = {
        "group": "@cdxgen",
        "name": "cdxgen",
        "version": "13.3.0",
        "purl": "pkg:npm/%40cdxgen/cdxgen@13.3.0",
        "type": "application",
        "bom-ref": "pkg:npm/@cdxgen/cdxgen@13.3.0",
        "publisher": "OWASP Foundation",
        "authors": [{"name": "OWASP Foundation"}],
    }
    if tool_components != [expected_tool]:
        raise ValueError("SBOM tool profile is not exact")
    if metadata["authors"] != [{"name": "OWASP Foundation"}]:
        raise ValueError("SBOM author profile is not exact")
    if metadata["lifecycles"] != [{"phase": "pre-build"}]:
        raise ValueError("SBOM lifecycle profile is not exact")
    root = _mapping(metadata["component"], context="SBOM root component")
    _exact_keys(
        root,
        {"name", "version", "properties", "type", "bom-ref", "purl"},
        context="SBOM root component",
    )
    root_properties = _sbom_properties(root["properties"], context="root component")
    if (
        root["name"] != "laya-runtime-supply"
        or root["version"] != "0.0.0"
        or root["type"] != "application"
        or root["purl"] != "pkg:pypi/laya-runtime-supply@0.0.0"
        or root["bom-ref"] != root["purl"]
        or root_properties
        != (("cdx:pypi:requiresPython", "==3.11.10"), ("internal:SrcFile", "pyproject.toml"))
    ):
        raise ValueError("SBOM root component profile is not exact")
    root_component = SbomComponent(
        root["name"],
        root["version"],
        root["type"],
        root["purl"],
        root["bom-ref"],
        (),
        root_properties,
        (),
        (),
        _factory_token=_FACTORY_TOKEN,
    )
    properties = dict(_sbom_properties(metadata["properties"], context="metadata"))
    expected_properties = {
        "cdx:bom:componentSrcFiles": "pyproject.toml\\nuv.lock",
        "cdx:bom:componentTypes": "pypi",
        "aai:uv-lock:sha256": _LOCK_SHA256,
        "aai:uv-generator": "uv==0.12.3",
    }
    if properties != expected_properties:
        raise ValueError("SBOM metadata property profile is not exact")
    return "cdxgen", "13.3.0", "pre-build", _LOCK_SHA256, "0.12.3", root_component


def _canonical_sbom_semantics_sha256(value: dict[str, Any]) -> str:
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

    def normalize(current: object, *, parent_key: str | None = None) -> object:
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

    try:
        encoded = json.dumps(
            normalize(value),
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("ascii")
    except (TypeError, ValueError, RecursionError):
        raise ValueError("SBOM semantic profile cannot be canonicalized") from None
    return hashlib.sha256(encoded).hexdigest()


def _validate_laya_cyclonedx_sbom_bytes(payload: bytes) -> ValidatedLayaCycloneDxSbom:
    """Validate the deterministic local CycloneDX evidence profile."""

    if not isinstance(payload, bytes):
        raise TypeError("SBOM payload must be bytes")
    if len(payload) > MAX_CYCLONEDX_SBOM_BYTES:
        raise ValueError("SBOM payload size exceeds limit")
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError:
        raise ValueError("SBOM payload is not strict UTF-8") from None
    try:
        parsed = json.loads(text)
    except Exception:
        raise ValueError("SBOM payload is not valid strict JSON") from None
    root = _mapping(parsed, context="SBOM payload")
    _exact_keys(
        root,
        {
            "bomFormat",
            "specVersion",
            "version",
            "metadata",
            "components",
            "dependencies",
            "$schema",
        },
        context="SBOM",
    )
    if (
        root["bomFormat"] != "CycloneDX"
        or root["specVersion"] != "1.6"
        or type(root["version"]) is not int
        or root["version"] != 1
        or root["$schema"] != _CYCLONEDX_SCHEMA
    ):
        raise ValueError("SBOM CycloneDX version schema profile is not exact")
    raw_components = root["components"]
    raw_dependencies = root["dependencies"]
    if not isinstance(raw_components, list) or not isinstance(raw_dependencies, list):
        raise ValueError("SBOM component and dependency collections must be lists")
    if (
        len(raw_components) > MAX_SBOM_COMPONENTS
        or len(raw_dependencies) > MAX_SBOM_DEPENDENCY_NODES
    ):
        raise ValueError("SBOM component or dependency count exceeds limit")
    edge_count = 0
    for raw_node in raw_dependencies:
        if isinstance(raw_node, dict) and isinstance(raw_node.get("dependsOn"), list):
            edge_count += len(raw_node["dependsOn"])
            if edge_count > MAX_SBOM_DEPENDENCY_EDGES:
                raise ValueError("SBOM dependency edge count exceeds limit")
    if len(raw_components) != 44 or len(raw_dependencies) != 45:
        raise ValueError("SBOM component or dependency count is not exact")
    metadata = _parse_sbom_metadata(root["metadata"])
    components = tuple(
        sorted(
            (_parse_sbom_component(item) for item in raw_components), key=lambda item: item.bom_ref
        )
    )
    dependencies = tuple(
        sorted(
            (_parse_sbom_dependency(item) for item in raw_dependencies), key=lambda item: item.ref
        )
    )
    identities = {metadata[-1].bom_ref, *(component.bom_ref for component in components)}
    if len(identities) != 45 or len({component.purl for component in components}) != 44:
        raise ValueError("SBOM component identities contain a duplicate or are not exact")
    if (
        len({node.ref for node in dependencies}) != 45
        or {node.ref for node in dependencies} != identities
        or any(edge not in identities for node in dependencies for edge in node.depends_on)
        or sum(len(node.depends_on) for node in dependencies) != 70
    ):
        raise ValueError("SBOM dependency graph is not closed and exact")
    semantics_sha256 = _canonical_sbom_semantics_sha256(root)
    if semantics_sha256 != _EXPECTED_SBOM_SEMANTICS_SHA256:
        raise ValueError("SBOM semantic profile is not exact")
    tool_name, tool_version, lifecycle, lock_sha256, uv_version, root_component = metadata
    return ValidatedLayaCycloneDxSbom(
        "CycloneDX",
        "1.6",
        1,
        _CYCLONEDX_SCHEMA,
        tool_name,
        tool_version,
        lifecycle,
        lock_sha256,
        uv_version,
        root_component,
        components,
        dependencies,
        45,
        semantics_sha256,
        _factory_token=_FACTORY_TOKEN,
    )


def validate_laya_cyclonedx_sbom_bytes(payload: bytes) -> ValidatedLayaCycloneDxSbom:
    """Validate SBOM bytes while suppressing all private parser context."""

    try:
        return _validate_laya_cyclonedx_sbom_bytes(payload)
    except (TypeError, ValueError) as error:
        raise type(error)(str(error)) from None
