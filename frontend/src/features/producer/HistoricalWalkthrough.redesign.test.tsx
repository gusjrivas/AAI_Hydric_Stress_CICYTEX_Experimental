import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { HistoricalWalkthrough } from "./HistoricalWalkthrough";
import * as historicalApi from "./historicalApi";
import type { ForecastBatch } from "./forecastsApi";
import type { ReadingRow, ReadingsResult } from "./readingsApi";

afterEach(() => vi.restoreAllMocks());

const unavailableBatch = (asOf: string): ForecastBatch => ({
  batch_id: `batch-${asOf}`,
  revision: 1,
  as_of_date: asOf,
  data_age_days: 0,
  server_today: asOf,
  provenance: "external_reanalysis",
  calendar_timezone: "UTC",
  slots: [1, 2, 3].map((h) => ({
    horizon_days: h as 1 | 2 | 3,
    target_date: `2023-06-${13 + h}`,
    status: "unavailable" as const,
    reason_code: "model_not_available",
  })),
});

function row(date: string, soil: number | null, imputed = false): ReadingRow {
  return {
    date, soil_moisture: soil, relative_humidity: null, solar_radiation: null, temperature: null,
    precipitation: null, wind_speed: null, et0: null, origin: "external_reanalysis", quality_flags: [],
    imputed_variables: imputed ? ["soil_moisture"] : [], unverified_variables: [],
  };
}

const readings = (end: string): ReadingsResult => ({
  ...{ input_roles: [] },
  sensor_id: "pergamino-ensemble-demo", calendar_timezone: "UTC", server_today: end, snapshot_id: null,
  window: { start_date: "2023-06-08", end_date: end, expected_days: 6 }, status: "ready",
  rows: [row("2023-06-08", 0.34), row("2023-06-09", 0.33), row("2023-06-10", null), row("2023-06-11", 0.32, true), row("2023-06-12", 0.31), row("2023-06-13", 0.3)],
  missing_dates: ["2023-06-10"],
  variable_coverage: [{ variable: "soil_moisture", observed_days: 4, missing_days: 1, imputed_days: 1, unverified_days: 0 }],
  units: { soil_moisture: "m3/m3" }, last_reading_date: end, data_age_days: 0, provenance: "external_reanalysis",
});

describe("HistoricalWalkthrough — rediseño", () => {
  it("summarizes data source, emission, applicable dates and the clock in one reading strip", async () => {
    vi.spyOn(historicalApi, "getHistoricalForecastBatch").mockResolvedValue(unavailableBatch("2023-06-13"));
    vi.spyOn(historicalApi, "getHistoricalReadings").mockResolvedValue(readings("2023-06-13"));
    render(<HistoricalWalkthrough sensorId="pergamino-ensemble-demo" defense />);
    const strip = screen.getByText("Datos que se ven").closest("dl") as HTMLElement;
    expect(within(strip).getByText("Datos externos")).toBeInTheDocument();
    expect(within(strip).getByText(/horizontes \+1, \+2 y \+3 días/i)).toBeInTheDocument();
    expect(within(strip).getByText(/se revelan datos hasta esta fecha/i)).toBeInTheDocument();
    expect(await screen.findByRole("group", { name: /cobertura de la humedad del suelo/i })).toHaveTextContent(/4 con dato.*1 imputado.*0 sin verificar.*1 sin dato/i);
  });

  it("advances and rewinds the clock one day at a time within the allowed range", async () => {
    const batch = vi.spyOn(historicalApi, "getHistoricalForecastBatch").mockResolvedValue(unavailableBatch("2023-06-13"));
    vi.spyOn(historicalApi, "getHistoricalReadings").mockResolvedValue(readings("2023-06-13"));
    render(<HistoricalWalkthrough sensorId="pergamino-ensemble-demo" defense />);
    const back = screen.getByRole("button", { name: /día anterior/i });
    const forward = screen.getByRole("button", { name: /día siguiente/i });
    expect(back).toBeDisabled();
    await userEvent.click(forward);
    await waitFor(() => expect(batch).toHaveBeenLastCalledWith("pergamino-ensemble-demo", "2023-06-13", "2023-06-14"));
    expect(back).toBeEnabled();
    await userEvent.click(back);
    await waitFor(() => expect(batch).toHaveBeenLastCalledWith("pergamino-ensemble-demo", "2023-06-13", undefined));
  });

  it("draws the moisture chart from revealed readings and keeps the table as the accessible alternative", async () => {
    vi.spyOn(historicalApi, "getHistoricalForecastBatch").mockResolvedValue(unavailableBatch("2023-06-13"));
    vi.spyOn(historicalApi, "getHistoricalReadings").mockResolvedValue(readings("2023-06-13"));
    render(<HistoricalWalkthrough sensorId="pergamino-ensemble-demo" defense />);
    expect(await screen.findByRole("img", { name: /4 observados, 1 imputados, 0 de procedencia no verificada y 1 sin dato/i })).toBeInTheDocument();
    expect(screen.getByRole("table")).toBeInTheDocument();
    expect(screen.getByText(/sin observación en la fuente/i)).toBeInTheDocument();
  });

  it("keeps heading levels contiguous: h2 under the site title in defense mode, h3 elsewhere", async () => {
    vi.spyOn(historicalApi, "getHistoricalForecastBatch").mockResolvedValue(unavailableBatch("2023-06-13"));
    vi.spyOn(historicalApi, "getHistoricalReadings").mockResolvedValue(readings("2023-06-13"));
    const { unmount } = render(<HistoricalWalkthrough sensorId="pergamino-ensemble-demo" defense />);
    expect(screen.getByRole("heading", { name: "Recorrido histórico", level: 2 })).toBeInTheDocument();
    await screen.findByRole("heading", { name: /procedencia y calidad de datos/i, level: 3 });
    unmount();
    render(<HistoricalWalkthrough sensorId="sensor-a" />);
    expect(screen.getByRole("heading", { name: "Recorrido histórico", level: 3 })).toBeInTheDocument();
  });
});
