from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    import pandas as pd


CICYTEX_SENSOR_IDS = tuple(f"CP{point}_S{probe}" for point in range(1, 8) for probe in range(1, 4))


def _non_empty_unique(values: tuple[str, ...], field_name: str) -> None:
    if (
        not isinstance(values, tuple)
        or not values
        or any(not isinstance(value, str) or not value.strip() for value in values)
        or len(set(values)) != len(values)
    ):
        raise ValueError(f"{field_name} must be a non-empty tuple of unique names")


@dataclass(frozen=True, slots=True)
class CicytexDatasetContract:
    """Versioned scientific contract for one normalized CICYTEX dataset source."""

    version: str
    sensor_ids: tuple[str, ...]
    required_columns: tuple[str, ...]
    timestamp_column: str
    moisture_column: str
    sensor_id_column: str
    filename_template: str
    moisture_unit: str
    moisture_bounds: tuple[float, float]
    allow_missing_moisture: bool

    def __post_init__(self) -> None:
        if not isinstance(self.version, str) or not self.version.strip():
            raise ValueError("version must be non-empty")
        _non_empty_unique(self.sensor_ids, "sensor_ids")
        _non_empty_unique(self.required_columns, "required_columns")
        identity_columns = (
            self.timestamp_column,
            self.moisture_column,
            self.sensor_id_column,
        )
        if any(not isinstance(value, str) or not value.strip() for value in identity_columns):
            raise ValueError("identity column names must be non-empty")
        if not set(identity_columns).issubset(self.required_columns):
            raise ValueError("required_columns must include all identity columns")
        if "{sensor_id}" not in self.filename_template:
            raise ValueError("filename_template must include {sensor_id}")
        if not isinstance(self.moisture_unit, str) or not self.moisture_unit.strip():
            raise ValueError("moisture_unit must be non-empty")
        if not isinstance(self.moisture_bounds, tuple) or len(self.moisture_bounds) != 2:
            raise ValueError("moisture_bounds must contain lower and upper bounds")
        lower, upper = self.moisture_bounds
        if (
            isinstance(lower, bool)
            or isinstance(upper, bool)
            or not isinstance(lower, (int, float))
            or not isinstance(upper, (int, float))
            or not math.isfinite(float(lower))
            or not math.isfinite(float(upper))
            or float(lower) >= float(upper)
        ):
            raise ValueError("moisture_bounds must be finite and strictly increasing")
        if not isinstance(self.allow_missing_moisture, bool):
            raise ValueError("allow_missing_moisture must be boolean")

    def file_name_for(self, sensor_id: str) -> str:
        if sensor_id not in self.sensor_ids:
            raise ValueError(f"Unexpected CICYTEX sensor: {sensor_id}")
        return self.filename_template.format(sensor_id=sensor_id)


@runtime_checkable
class CicytexDatasetSource(Protocol):
    """Port implemented by sources that materialize the normalized pandas boundary."""

    @property
    def contract(self) -> CicytexDatasetContract: ...

    def load(self) -> pd.DataFrame: ...


CICYTEX_NORMALIZED_V1 = CicytexDatasetContract(
    version="cicytex-normalized-v1",
    sensor_ids=CICYTEX_SENSOR_IDS,
    required_columns=("timestamp", "soil_moisture", "sensor_id"),
    timestamp_column="timestamp",
    moisture_column="soil_moisture",
    sensor_id_column="sensor_id",
    filename_template="cicytex__{sensor_id}.csv",
    moisture_unit="m3/m3",
    moisture_bounds=(0.0, 1.0),
    allow_missing_moisture=True,
)
