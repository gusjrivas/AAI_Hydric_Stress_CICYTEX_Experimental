"""Offline composition for deterministic OpenAPI TypeScript artifacts."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path

_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
_BACKEND_ROOT = _REPOSITORY_ROOT / "backend"
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.main import app  # noqa: E402

from openapi_typescript_toolchain import (  # noqa: E402
    build_openapi_typescript_manifest,
    canonical_openapi_json_bytes,
    validate_openapi_operation_ids,
    verify_openapi_typescript_manifest,
)

_ARTIFACT_NAMES = ("openapi.json", "openapi.ts", "openapi-manifest.json")
_DEFAULT_ARTIFACT_ROOT = _REPOSITORY_ROOT / "artifacts" / "openapi-typescript"
_DEFAULT_FRONTEND_ROOT = _REPOSITORY_ROOT / "frontend"


class OpenApiArtifactDriftError(ValueError):
    """Raised when tracked OpenAPI artifacts differ from a clean regeneration."""


def generate_openapi_typescript_artifacts(
    output_directory: Path,
    *,
    frontend_root: Path = _DEFAULT_FRONTEND_ROOT,
) -> None:
    """Generate the three integrity-bound artifacts using the local executable."""

    output_root = _require_directory_argument(output_directory, "output directory")
    frontend = _require_directory_argument(frontend_root, "frontend root")
    openapi_bytes = _application_openapi_bytes()
    generator_version = _generator_version(frontend)

    with tempfile.TemporaryDirectory(prefix="openapi-typescript-generate-") as temporary:
        temporary_root = Path(temporary)
        openapi_path = temporary_root / "openapi.json"
        typescript_path = temporary_root / "openapi.ts"
        openapi_path.write_bytes(openapi_bytes)
        _run_local_generator(frontend, openapi_path, typescript_path)
        typescript_bytes = typescript_path.read_bytes()

    manifest = build_openapi_typescript_manifest(
        openapi_bytes,
        typescript_bytes,
        generator_version=generator_version,
    )
    verify_openapi_typescript_manifest(manifest, openapi_bytes, typescript_bytes)
    manifest_bytes = canonical_openapi_json_bytes(asdict(manifest))

    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / _ARTIFACT_NAMES[0]).write_bytes(openapi_bytes)
    (output_root / _ARTIFACT_NAMES[1]).write_bytes(typescript_bytes)
    (output_root / _ARTIFACT_NAMES[2]).write_bytes(manifest_bytes)


def check_openapi_typescript_artifacts(
    artifact_directory: Path,
    *,
    frontend_root: Path = _DEFAULT_FRONTEND_ROOT,
) -> None:
    """Regenerate elsewhere and compare without mutating tracked artifacts."""

    tracked_root = _require_directory_argument(artifact_directory, "artifact directory")
    frontend = _require_directory_argument(frontend_root, "frontend root")
    with tempfile.TemporaryDirectory(prefix="openapi-typescript-check-") as temporary:
        candidate_root = Path(temporary) / "artifacts"
        generate_openapi_typescript_artifacts(candidate_root, frontend_root=frontend)
        for artifact_name in _ARTIFACT_NAMES:
            tracked_path = tracked_root / artifact_name
            try:
                tracked_bytes = tracked_path.read_bytes()
            except OSError:
                raise OpenApiArtifactDriftError(
                    f"tracked artifact is unavailable: {artifact_name}"
                ) from None
            if tracked_bytes != (candidate_root / artifact_name).read_bytes():
                raise OpenApiArtifactDriftError(f"tracked artifact drift: {artifact_name}")


def _application_openapi_bytes() -> bytes:
    document = app.openapi()
    validate_openapi_operation_ids(document)
    return canonical_openapi_json_bytes(document)


def _generator_version(frontend_root: Path) -> str:
    try:
        package = json.loads((frontend_root / "package.json").read_bytes())
        version = package["devDependencies"]["openapi-typescript"]
    except (KeyError, OSError, TypeError, ValueError):
        raise RuntimeError("local generator metadata is unavailable") from None
    if type(version) is not str or not version or not version[0].isdigit():
        raise RuntimeError("local generator version is not exact")
    return version


def _run_local_generator(frontend_root: Path, input_path: Path, output_path: Path) -> None:
    binary_name = "openapi-typescript.cmd" if os.name == "nt" else "openapi-typescript"
    executable = frontend_root / "node_modules" / ".bin" / binary_name
    if not executable.is_file():
        raise RuntimeError("local generator executable is unavailable")
    try:
        completed = subprocess.run(
            [str(executable), str(input_path), "-o", str(output_path)],
            cwd=frontend_root,
            check=False,
            capture_output=True,
            shell=os.name == "nt",
        )
    except OSError:
        raise RuntimeError("local generator execution failed") from None
    if completed.returncode != 0 or not output_path.is_file():
        diagnostic = completed.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"local generator execution failed: {diagnostic or 'no diagnostic'}")


def _require_directory_argument(value: object, label: str) -> Path:
    if not isinstance(value, Path):
        raise TypeError(f"{label} must be a Path")
    return value.resolve()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("generate", "check"))
    parser.add_argument("--output", type=Path, default=_DEFAULT_ARTIFACT_ROOT)
    parser.add_argument("--frontend-root", type=Path, default=_DEFAULT_FRONTEND_ROOT)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    if arguments.mode == "generate":
        generate_openapi_typescript_artifacts(
            arguments.output,
            frontend_root=arguments.frontend_root,
        )
    else:
        check_openapi_typescript_artifacts(
            arguments.output,
            frontend_root=arguments.frontend_root,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
