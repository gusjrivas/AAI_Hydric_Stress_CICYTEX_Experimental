from pathlib import Path

import pandas as pd

from experiment_runner.cicytex.ingestion import load_normalized_cicytex
from experiment_runner.cicytex.training_protocol import build_features, temporal_split


def test_ingestion_preserves_sensor_identity_and_units(tmp_path: Path):
    columns = ["timestamp", "soil_moisture", "sensor_id"]
    for point in range(1, 8):
        for probe in range(1, 4):
            sensor = f"CP{point}_S{probe}"
            pd.DataFrame([["2023-01-01", 0.2, sensor]], columns=columns).to_csv(
                tmp_path / f"cicytex__{sensor}.csv", index=False
            )
    result = load_normalized_cicytex(tmp_path)
    assert len(result) == 21
    assert result.sensor_id.nunique() == 21
    assert result.soil_moisture.between(0, 1).all()


def test_features_never_cross_sensor_boundary():
    rows = []
    for sensor, base in [("CP1_S1", 0.1), ("CP1_S2", 0.8)]:
        for day in range(12):
            rows.append(
                {
                    "sensor_id": sensor,
                    "timestamp": pd.Timestamp("2023-01-01") + pd.to_timedelta(day, unit="D"),
                    "soil_moisture": base + day / 1000,
                }
            )
    frame = build_features(pd.DataFrame(rows), horizon=1)
    first_second_sensor = frame[frame.sensor_id == "CP1_S2"].iloc[0]
    assert pd.isna(first_second_sensor.lag1)


def test_target_is_strictly_future_and_split_is_temporal():
    rows = [
        {
            "sensor_id": "CP1_S1",
            "timestamp": pd.Timestamp("2023-01-01") + pd.to_timedelta(day, unit="D"),
            "soil_moisture": 0.2 + day / 1000,
        }
        for day in range(100)
    ]
    frame = build_features(pd.DataFrame(rows), horizon=3).dropna()
    assert (frame.target_timestamp - frame.timestamp == pd.to_timedelta(3, unit="D")).all()
    split = temporal_split(frame.target_timestamp)
    assert split.train_end < split.calibration_end < split.validation_end < split.evaluation_end


def test_compose_uses_only_cicytex_names_and_exclusive_ports():
    compose = Path("compose.cicytex.yml").read_text(encoding="utf-8")
    assert "name: aai-cicytex-experiment" in compose
    assert all(port in compose for port in ("5500:5000", "55432:5432", "59000:9000", "59001:9001"))
    assert "aai-cicytex-experiment-postgres" in compose
    assert "mlflow_postgres_data" not in compose
