import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ProducerDataScreen } from "./ProducerDataScreen";
import * as readingsApi from "./readingsApi";
import type { ReadingsResult } from "./readingsApi";

afterEach(() => vi.restoreAllMocks());

const baseReadings: ReadingsResult = {
  ...{ input_roles: [] },
  sensor_id: "sensor-a",
  calendar_timezone: "UTC",
  server_today: "2023-06-20",
  snapshot_id: "snap-1",
  window: { start_date: "2023-06-11", end_date: "2023-06-20", expected_days: 10 },
  status: "ready",
  rows: [
    { date: "2023-06-19", soil_moisture: 0.2, relative_humidity: 60, solar_radiation: 18, temperature: 22, precipitation: 0, wind_speed: 3, et0: 4, origin: "external_reanalysis", quality_flags: [], imputed_variables: [], unverified_variables: [] },
    { date: "2023-06-20", soil_moisture: null, relative_humidity: 61, solar_radiation: null, temperature: null, precipitation: 0, wind_speed: 3, et0: 4, origin: "external_reanalysis", quality_flags: ["non_finite:solar_radiation"], imputed_variables: [], unverified_variables: [] },
  ],
  missing_dates: ["2023-06-15"],
  variable_coverage: [{ variable: "soil_moisture", observed_days: 9, missing_days: 1, imputed_days: 0, unverified_days: 0 }],
  units: { soil_moisture: "%", temperature: "degC", precipitation: "mm/day", relative_humidity: "%", solar_radiation: "MJ/m2/day", wind_speed: "m/s", et0: "mm/day" },
  last_reading_date: "2023-06-19",
  data_age_days: 1,
  provenance: "external_reanalysis",
};

describe("ProducerDataScreen", () => {
  it("shows variables, units, provenance and per-day quality flags only when the backend reports them", async () => {
    vi.spyOn(readingsApi, "getSensorReadings").mockResolvedValue(baseReadings);
    render(<ProducerDataScreen sensorId="sensor-a" />);

    expect(await screen.findByText("Datos externos de ERA5-Land y NASA POWER")).toBeInTheDocument();
    expect(screen.getByText("Humedad del suelo")).toBeInTheDocument();
    expect(screen.getByText("% del volumen del suelo")).toBeInTheDocument();
    expect(screen.getByText("Valor fuera de rango registrado en Radiación solar")).toBeInTheDocument();
    expect(screen.getByText(/ver fechas sin medición/i)).toBeInTheDocument();
  });

  it("never claims anomalies when none are backed by quality_flags", async () => {
    vi.spyOn(readingsApi, "getSensorReadings").mockResolvedValue({
      ...baseReadings,
      rows: baseReadings.rows.map((row) => ({ ...row, quality_flags: [], imputed_variables: [], unverified_variables: [] })),
    });
    render(<ProducerDataScreen sensorId="sensor-a" />);
    expect(await screen.findByText(/no se registraron anomalías/i)).toBeInTheDocument();
  });
});
