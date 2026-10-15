import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ProducerHistoryPanel } from "./ProducerHistoryPanel";
import * as api from "./readingsApi";
import { SensorNotFoundError } from "./readingsApi";

const readings: api.ReadingsResult = {
  ...{ input_roles: [] },
  sensor_id: "sensor-a",
  calendar_timezone: "UTC",
  server_today: "2026-01-05",
  snapshot_id: "abc",
  window: { start_date: "2026-01-01", end_date: "2026-01-03", expected_days: 3 },
  status: "ready",
  rows: [
    { date: "2026-01-01", soil_moisture: 0.3, relative_humidity: 60, solar_radiation: 15, temperature: 20, precipitation: 0, wind_speed: 2, et0: 4, origin: "synthetic", quality_flags: [], imputed_variables: [], unverified_variables: [] },
    { date: "2026-01-02", soil_moisture: null, relative_humidity: 61, solar_radiation: 16, temperature: 21, precipitation: 0, wind_speed: 2, et0: 4, origin: "synthetic", quality_flags: [], imputed_variables: [], unverified_variables: [] },
    { date: "2026-01-03", soil_moisture: 0.2, relative_humidity: 58, solar_radiation: 14, temperature: 22, precipitation: 2, wind_speed: 3, et0: 5, origin: "synthetic", quality_flags: [], imputed_variables: [], unverified_variables: [] },
  ],
  missing_dates: ["2026-01-02"],
  variable_coverage: [],
  units: { soil_moisture: "m3/m3", temperature: "degC", precipitation: "mm/day", relative_humidity: "%", solar_radiation: "MJ/m2/day", wind_speed: "m/s", et0: "mm/day" },
  last_reading_date: "2026-01-03",
  data_age_days: 2,
  provenance: "synthetic",
};

describe("ProducerHistoryPanel", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("shows provenance, missing dates, data age, units and the reading table", async () => {
    vi.spyOn(api, "getSensorReadings").mockResolvedValue(readings);
    render(<ProducerHistoryPanel sensorId="sensor-a" />);
    await screen.findByText(/solo para demostración/i);
    expect(screen.getByText(/antigüedad: 2 días/i)).toBeInTheDocument();
    expect(screen.getByText(/1 fecha falta/i)).toBeInTheDocument();
    expect(screen.getAllByText("20.0 %").length).toBeGreaterThan(0);
    // Bug real detectado contra el backend v2: mostraba el código crudo
    // del backend ("degC", "mm/day") en vez de una unidad legible.
    expect(screen.getAllByText("20.0 °C").length).toBeGreaterThan(0);
    expect(screen.getAllByText("0.0 mm").length).toBeGreaterThan(0);
    expect(screen.queryByText(/degc|mm\/day/i)).not.toBeInTheDocument();
    await userEvent.click(screen.getByText(/ver mediciones por fecha/i));
    expect(screen.getByRole("table")).toBeVisible();
    expect(screen.getByText("Sin medición")).toBeInTheDocument();
  });

  it("changes the query window between 7 and 30 days", async () => {
    const spy = vi.spyOn(api, "getSensorReadings").mockResolvedValue(readings);
    render(<ProducerHistoryPanel sensorId="sensor-a" />);
    await screen.findByText(/solo para demostración/i);
    expect(spy).toHaveBeenLastCalledWith("sensor-a", 30);
    await userEvent.selectOptions(screen.getByRole("combobox"), "7");
    await waitFor(() => expect(spy).toHaveBeenLastCalledWith("sensor-a", 7));
  });

  it("discards an obsolete sensor response", async () => {
    let resolve!: (data: api.ReadingsResult) => void;
    vi.spyOn(api, "getSensorReadings")
      .mockReturnValueOnce(new Promise((r) => { resolve = r; }))
      .mockResolvedValueOnce({ ...readings, sensor_id: "sensor-b", status: "no_readings", rows: [] });
    const { rerender } = render(<ProducerHistoryPanel sensorId="sensor-a" />);
    rerender(<ProducerHistoryPanel sensorId="sensor-b" />);
    await screen.findByText(/todavía no hay mediciones para este punto/i);
    resolve(readings);
    await waitFor(() => expect(screen.queryByText(/solo para demostración/i)).not.toBeInTheDocument());
  });

  it("distinguishes an error from an empty history and retries", async () => {
    vi.spyOn(api, "getSensorReadings")
      .mockRejectedValueOnce(new SensorNotFoundError("sensor-a"))
      .mockResolvedValue({ ...readings, status: "no_readings", rows: [] });
    render(<ProducerHistoryPanel sensorId="sensor-a" />);
    await screen.findByRole("alert");
    expect(screen.queryByText(/todavía no hay mediciones/i)).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Reintentar mediciones" }));
    await screen.findByText(/todavía no hay mediciones para este punto/i);
  });
});
