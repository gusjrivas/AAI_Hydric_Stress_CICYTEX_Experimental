from __future__ import annotations

import hashlib
import io
import json
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from experiment_runner.cicytex.dataset_contract import (
    CICYTEX_NORMALIZED_V1,
    CicytexDatasetContract,
)

SENSORS = CICYTEX_NORMALIZED_V1.sensor_ids
CICYTEX_SNAPSHOT_MANIFEST_VERSION = "cicytex-normalized-snapshot-v1"
CICYTEX_DATASET_PROVENANCE_VERSION = "cicytex-dataset-provenance-v2"


class CicytexSnapshotChangedError(RuntimeError):
    """Raised when a declared input changes while its snapshot is captured."""


@dataclass(frozen=True, slots=True)
class CicytexInputFile:
    """Content identity for one contract-declared normalized CSV."""

    sensor_id: str
    file_name: str
    size_bytes: int
    sha256: str

    def __post_init__(self) -> None:
        if not self.sensor_id or not self.file_name:
            raise ValueError("sensor_id y file_name deben ser no vacíos")
        if (
            Path(self.file_name).name != self.file_name
            or "/" in self.file_name
            or "\\" in self.file_name
        ):
            raise ValueError("file_name debe ser un nombre relativo seguro")
        if isinstance(self.size_bytes, bool) or self.size_bytes < 0:
            raise ValueError("size_bytes debe ser no negativo")
        if len(self.sha256) != 64 or any(char not in "0123456789abcdef" for char in self.sha256):
            raise ValueError("sha256 debe ser hexadecimal SHA-256 en minúsculas")

    def to_dict(self) -> dict[str, str | int]:
        return {
            "sensor_id": self.sensor_id,
            "file_name": self.file_name,
            "size_bytes": self.size_bytes,
            "sha256": self.sha256,
        }


@dataclass(frozen=True, slots=True)
class CicytexDatasetManifest:
    """Deterministic identity of all normalized files consumed by a run."""

    contract_version: str
    files: tuple[CicytexInputFile, ...]
    manifest_version: str = CICYTEX_SNAPSHOT_MANIFEST_VERSION
    hash_algorithm: str = "sha256"
    dataset_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        if self.manifest_version != CICYTEX_SNAPSHOT_MANIFEST_VERSION:
            raise ValueError("manifest_version no soportada")
        if self.contract_version != CICYTEX_NORMALIZED_V1.version:
            raise ValueError("contract_version no soportada")
        if self.hash_algorithm != "sha256":
            raise ValueError("hash_algorithm no soportado")
        if not isinstance(self.files, tuple):
            raise ValueError("files debe ser una tupla inmutable")
        expected = tuple(
            (sensor_id, CICYTEX_NORMALIZED_V1.file_name_for(sensor_id))
            for sensor_id in CICYTEX_NORMALIZED_V1.sensor_ids
        )
        observed = tuple((entry.sensor_id, entry.file_name) for entry in self.files)
        if observed != expected:
            raise ValueError("files debe contener las 21 series en orden contractual")
        payload = self._identity_dict()
        canonical = json.dumps(
            payload,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        object.__setattr__(self, "dataset_sha256", hashlib.sha256(canonical).hexdigest())

    def _identity_dict(self) -> dict[str, Any]:
        return {
            "manifest_version": self.manifest_version,
            "contract_version": self.contract_version,
            "hash_algorithm": self.hash_algorithm,
            "files": [entry.to_dict() for entry in self.files],
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self._identity_dict(), "dataset_sha256": self.dataset_sha256}


@dataclass(frozen=True, slots=True)
class CicytexDatasetSnapshot:
    """Parsed dataset plus immutable content metadata from the same captured bytes.

    The manifest is immutable. The pandas DataFrame intentionally remains the mutable
    compatibility boundary expected by existing scientific code.
    """

    dataframe: pd.DataFrame
    manifest: CicytexDatasetManifest

    @property
    def dataset_sha256(self) -> str:
        return self.manifest.dataset_sha256


@dataclass(frozen=True, slots=True)
class CicytexArtifactIdentity:
    file_name: str
    size_bytes: int
    sha256: str

    def __post_init__(self) -> None:
        CicytexInputFile("artifact", self.file_name, self.size_bytes, self.sha256)

    def to_dict(self) -> dict[str, str | int]:
        return {
            "file_name": self.file_name,
            "size_bytes": self.size_bytes,
            "sha256": self.sha256,
        }


@dataclass(frozen=True, slots=True)
class CicytexDatasetQuality:
    rows: int
    sensors: int
    start: str
    end: str
    missing_soil_moisture: int
    duplicate_sensor_dates: int
    rows_per_sensor_min: int
    rows_per_sensor_max: int
    partial_days: int

    @classmethod
    def from_dataframe(cls, data: pd.DataFrame) -> CicytexDatasetQuality:
        return cls(**quality_summary(data))

    def to_dict(self) -> dict[str, int | str]:
        return {field_name: getattr(self, field_name) for field_name in self.__dataclass_fields__}


@dataclass(frozen=True, slots=True)
class CicytexDatasetProvenance:
    snapshot: CicytexDatasetSnapshot = field(repr=False, compare=False)
    primary_source: CicytexArtifactIdentity
    source_archive: CicytexArtifactIdentity
    dataset_quality: CicytexDatasetQuality
    dataframe_integrity_sha256: str = field(repr=False)
    provenance_schema_version: str = field(default=CICYTEX_DATASET_PROVENANCE_VERSION, init=False)
    derivation_status: str = field(default="external_derivative_unverified", init=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            "provenance_schema_version": self.provenance_schema_version,
            "derivation_status": self.derivation_status,
            "normalized_snapshot": self.snapshot.manifest.to_dict(),
            "primary_source": self.primary_source.to_dict(),
            "source_archive": self.source_archive.to_dict(),
            "dataset_quality": self.dataset_quality.to_dict(),
            "legacy_aliases": {
                "dataset_sha256": "primary_source.sha256",
                "zip_sha256": "source_archive.sha256",
            },
        }


def _fingerprint(path: Path) -> tuple[int | None, int | None, int, int]:
    stat = path.stat()
    return (
        getattr(stat, "st_dev", None),
        getattr(stat, "st_ino", None),
        stat.st_size,
        stat.st_mtime_ns,
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _artifact_identity(path: Path) -> CicytexArtifactIdentity:
    path = Path(path)
    before = _fingerprint(path)
    digest = sha256_file(path)
    after = _fingerprint(path)
    if before != after:
        raise CicytexSnapshotChangedError(f"El artefacto cambió durante la captura: {path.name}")
    return CicytexArtifactIdentity(path.name, after[2], digest)


@dataclass(frozen=True, slots=True)
class CsvCicytexDatasetSource:
    """CSV adapter for the versioned normalized CICYTEX dataset contract."""

    directory: Path
    contract: CicytexDatasetContract = CICYTEX_NORMALIZED_V1

    def __post_init__(self) -> None:
        object.__setattr__(self, "directory", Path(self.directory))

    def load_snapshot(self) -> CicytexDatasetSnapshot:
        root = self.directory.resolve()
        captured: list[tuple[str, Path, bytes]] = []
        fingerprints: dict[Path, tuple[int | None, int | None, int, int]] = {}
        for sensor in self.contract.sensor_ids:
            file_name = self.contract.file_name_for(sensor)
            path = self.directory / file_name
            if not path.is_file():
                raise FileNotFoundError(f"Falta la serie declarada: {path}")
            resolved = path.resolve()
            if not resolved.is_relative_to(root):
                raise ValueError(f"La serie declarada escapa del directorio: {file_name}")
            before = _fingerprint(path)
            raw = path.read_bytes()
            after = _fingerprint(path)
            if before != after or len(raw) != after[2]:
                raise CicytexSnapshotChangedError(
                    f"La serie cambió durante la captura: {file_name}"
                )
            fingerprints[path] = after
            captured.append((sensor, path, raw))

        for path, expected in fingerprints.items():
            try:
                current = _fingerprint(path)
            except FileNotFoundError as exc:
                raise CicytexSnapshotChangedError(
                    f"La serie desapareció durante la captura: {path.name}"
                ) from exc
            if current != expected:
                raise CicytexSnapshotChangedError(
                    f"La serie cambió durante la captura: {path.name}"
                )

        frames: list[pd.DataFrame] = []
        input_files: list[CicytexInputFile] = []
        timestamp = self.contract.timestamp_column
        moisture = self.contract.moisture_column
        sensor_column = self.contract.sensor_id_column
        for sensor, path, raw in captured:
            frame = pd.read_csv(io.BytesIO(raw))
            frame[timestamp] = pd.to_datetime(frame[timestamp], errors="raise")
            frame[moisture] = pd.to_numeric(frame[moisture], errors="coerce")
            if set(frame[sensor_column].dropna().unique()) != {sensor}:
                raise ValueError(f"Identidad de sonda inconsistente en {path.name}")
            frames.append(frame)
            input_files.append(
                CicytexInputFile(
                    sensor_id=sensor,
                    file_name=path.name,
                    size_bytes=len(raw),
                    sha256=hashlib.sha256(raw).hexdigest(),
                )
            )
        data = pd.concat(frames, ignore_index=True).sort_values([sensor_column, timestamp])
        if data.duplicated([sensor_column, timestamp]).any():
            raise ValueError("Hay fechas duplicadas dentro de una sonda")
        lower, upper = self.contract.moisture_bounds
        if not data[moisture].dropna().between(lower, upper).all():
            raise ValueError("Humedad volumétrica fuera de [0, 1] m3/m3")
        if not self.contract.allow_missing_moisture and data[moisture].isna().any():
            raise ValueError("Humedad volumétrica faltante no permitida")
        manifest = CicytexDatasetManifest(
            contract_version=self.contract.version,
            files=tuple(input_files),
        )
        return CicytexDatasetSnapshot(data.reset_index(drop=True), manifest)

    def load(self) -> pd.DataFrame:
        return self.load_snapshot().dataframe


def load_normalized_cicytex(directory: Path) -> pd.DataFrame:
    """Carga derivados CICYTEX preservando la fachada DataFrame histórica."""
    return CsvCicytexDatasetSource(directory).load()


def load_normalized_cicytex_snapshot(directory: Path) -> CicytexDatasetSnapshot:
    """Capture exact normalized bytes and materialize their versioned snapshot."""
    return CsvCicytexDatasetSource(directory).load_snapshot()


def quality_summary(data: pd.DataFrame) -> dict:
    counts = data.groupby("sensor_id", observed=True).size()
    observed = data["soil_moisture"].notna()
    partial_days = data.get("is_partial_day_soil_moisture")
    return {
        "rows": int(len(data)),
        "sensors": int(data["sensor_id"].nunique()),
        "start": data["timestamp"].min().date().isoformat(),
        "end": data["timestamp"].max().date().isoformat(),
        "missing_soil_moisture": int((~observed).sum()),
        "duplicate_sensor_dates": int(data.duplicated(["sensor_id", "timestamp"]).sum()),
        "rows_per_sensor_min": int(counts.min()),
        "rows_per_sensor_max": int(counts.max()),
        "partial_days": 0 if partial_days is None else int(partial_days.fillna(False).sum()),
    }


def _dataframe_integrity_sha256(data: pd.DataFrame) -> str:
    digest = hashlib.sha256()
    schema = [(str(column), str(dtype)) for column, dtype in data.dtypes.items()]
    digest.update(json.dumps(schema, ensure_ascii=True, separators=(",", ":")).encode("utf-8"))
    digest.update(pd.util.hash_pandas_object(data, index=True, categorize=True).values.tobytes())
    return digest.hexdigest()


def build_cicytex_dataset_provenance(
    snapshot: CicytexDatasetSnapshot,
    primary_source: Path,
    source_archive: Path,
) -> CicytexDatasetProvenance:
    """Describe the three independent CICYTEX input identities without overclaiming lineage."""
    return CicytexDatasetProvenance(
        snapshot=snapshot,
        primary_source=_artifact_identity(primary_source),
        source_archive=_artifact_identity(source_archive),
        dataset_quality=CicytexDatasetQuality.from_dataframe(snapshot.dataframe),
        dataframe_integrity_sha256=_dataframe_integrity_sha256(snapshot.dataframe),
    )


def validate_cicytex_dataset_provenance(
    provenance: CicytexDatasetProvenance,
    *,
    dataset_sha256: str,
    zip_sha256: str,
    data: pd.DataFrame,
) -> dict[str, Any]:
    """Validate the strict typed path before MLflow or model execution starts."""
    if not isinstance(provenance, CicytexDatasetProvenance):
        raise TypeError("provenance debe ser CicytexDatasetProvenance")
    if data is not provenance.snapshot.dataframe:
        raise ValueError("data debe ser el DataFrame del snapshot declarado")
    if _dataframe_integrity_sha256(data) != provenance.dataframe_integrity_sha256:
        raise ValueError("data cambió después de construir dataset_provenance")
    if CicytexDatasetQuality.from_dataframe(data) != provenance.dataset_quality:
        raise ValueError("dataset_quality no coincide con data")
    if dataset_sha256 != provenance.primary_source.sha256:
        raise ValueError("dataset_sha256 no coincide con primary_source.sha256")
    if zip_sha256 != provenance.source_archive.sha256:
        raise ValueError("zip_sha256 no coincide con source_archive.sha256")
    return provenance.to_dict()


def write_cicytex_dataset_provenance(
    output_dir: Path,
    provenance: CicytexDatasetProvenance,
    *,
    dataset_sha256: str,
    zip_sha256: str,
    data: pd.DataFrame,
) -> Path:
    """Persist a validated sidecar atomically, never overwriting different provenance."""
    content = assert_cicytex_provenance_slot(
        output_dir,
        provenance,
        dataset_sha256=dataset_sha256,
        zip_sha256=zip_sha256,
        data=data,
    )
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "cicytex_dataset_provenance.json"
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=output_dir, delete=False) as temporary:
            temporary_name = temporary.name
            temporary.write(content)
            temporary.flush()
            os.fsync(temporary.fileno())
        try:
            os.link(temporary_name, path)
        except FileExistsError:
            if path.read_bytes() != content:
                raise FileExistsError(f"Ya existe una procedencia CICYTEX diferente: {path}")
    finally:
        if temporary_name is not None:
            Path(temporary_name).unlink(missing_ok=True)
    return path


def assert_cicytex_provenance_slot(
    output_dir: Path,
    provenance: CicytexDatasetProvenance,
    *,
    dataset_sha256: str,
    zip_sha256: str,
    data: pd.DataFrame,
) -> bytes:
    """Fail before execution if output already belongs to different provenance."""
    serialized = validate_cicytex_dataset_provenance(
        provenance,
        dataset_sha256=dataset_sha256,
        zip_sha256=zip_sha256,
        data=data,
    )
    content = (json.dumps(serialized, indent=2, sort_keys=True, allow_nan=False) + "\n").encode(
        "utf-8"
    )
    path = Path(output_dir) / "cicytex_dataset_provenance.json"
    if path.exists():
        if path.read_bytes() != content:
            raise FileExistsError(f"Ya existe una procedencia CICYTEX diferente: {path}")
    return content
