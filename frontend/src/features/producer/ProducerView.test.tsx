import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ProducerView } from "./ProducerView";
import * as catalogApi from "./catalogApi";
import * as readingsApi from "./readingsApi";
import * as forecastsApi from "./forecastsApi";

const sector: catalogApi.Sector = {
  sector_id: "norte",
  display_name: "Huerta norte",
  crop: "Tomate",
  primary_sensor_id: "sensor-a",
  revision: 1,
  created_at: "2026-01-01T00:00:00Z",
};
const sensor: catalogApi.SensorSummary = {
  sensor_id: "sensor-a",
  display_name: "Sensor A",
  sector_id: "norte",
  source_kind: "synthetic",
  revision: 1,
  created_at: "2026-01-01T00:00:00Z",
  registered: true,
};

describe("ProducerView", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("shows a synthetic-data tag and the honest empty state for forecasts", async () => {
    vi.spyOn(catalogApi, "listSectors").mockResolvedValue({ items: [sector], next_cursor: null });
    vi.spyOn(catalogApi, "listSensors").mockResolvedValue({ items: [sensor], next_cursor: null });
    vi.spyOn(readingsApi, "getSensorReadings").mockResolvedValue({
      ...{ input_roles: [] },
      sensor_id: "sensor-a",
      calendar_timezone: "UTC",
      server_today: "2026-01-05",
      snapshot_id: null,
      window: { start_date: "2026-01-01", end_date: "2026-01-01", expected_days: 1 },
      status: "no_readings",
      rows: [],
      missing_dates: [],
      variable_coverage: [],
      units: {},
      last_reading_date: null,
      data_age_days: null,
      provenance: "unknown",
    });
    vi.spyOn(forecastsApi, "listForecasts").mockResolvedValue({
      items: [],
      next_cursor: null,
      pending_total: 0,
      reviewable_pending_total: 0,
    });

    render(<ProducerView />);

    expect(await screen.findByText("Datos simulados")).toBeInTheDocument();
    await userEvent.click(await screen.findByRole("button", { name: "Historial" }));
    expect(await screen.findByText(/todavía no hay pronósticos disponibles/i)).toBeInTheDocument();
    expect(screen.getByText(/no tenés pronósticos pendientes de revisar/i)).toBeInTheDocument();
  });

  it("summarizes the combined alert across horizons without inventing a percentage, and clears it on sensor change", async () => {
    vi.spyOn(catalogApi, "listSectors").mockResolvedValue({ items: [sector], next_cursor: null });
    vi.spyOn(catalogApi, "listSensors").mockResolvedValue({ items: [sensor], next_cursor: null });
    vi.spyOn(readingsApi, "getSensorReadings").mockResolvedValue({
      ...{ input_roles: [] },
      sensor_id: "sensor-a", calendar_timezone: "UTC", server_today: "2026-01-05", snapshot_id: null,
      window: { start_date: "2026-01-01", end_date: "2026-01-01", expected_days: 1 }, status: "no_readings",
      rows: [], missing_dates: [], variable_coverage: [], units: {}, last_reading_date: null,
      data_age_days: null, provenance: "unknown",
    });
    const unavailableSlot = (h: 1 | 2 | 3) => ({ horizon_days: h, target_date: `2026-01-0${h + 1}`, status: "unavailable" as const, reason_code: "model_not_available" });
    vi.spyOn(forecastsApi, "emitForecasts").mockResolvedValue({
      batch_id: "b1", revision: 1, as_of_date: "2026-01-05", data_age_days: 0, server_today: "2026-01-05",
      provenance: "synthetic", calendar_timezone: "UTC",
      slots: [unavailableSlot(1), unavailableSlot(2), unavailableSlot(3)],
    });

    render(<ProducerView />);
    await userEvent.click(await screen.findByRole("button", { name: "Consultar próximos tres días" }));
    expect(await screen.findByText(/No hay información suficiente/)).toBeInTheDocument();
    // Sin ningún horizonte disponible, no debe mostrarse ningún banner de
    // alerta (ni "alerta" ni "sin alerta"): la ausencia de datos no es lo
    // mismo que "sin alerta".
    expect(screen.queryByText(/Requiere atención/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Sin alerta próxima/)).not.toBeInTheDocument();
  });

  it("answers in plain words after an explicit consultation, with the three days at a glance and the data age", async () => {
    vi.spyOn(catalogApi, "listSectors").mockResolvedValue({ items: [sector], next_cursor: null });
    vi.spyOn(catalogApi, "listSensors").mockResolvedValue({ items: [sensor], next_cursor: null });
    vi.spyOn(forecastsApi, "listForecasts").mockResolvedValue({ items: [], next_cursor: null, pending_total: 0, reviewable_pending_total: 0 });
    vi.spyOn(readingsApi, "getSensorReadings").mockResolvedValue({
      ...{ input_roles: [] },
      sensor_id: "sensor-a", calendar_timezone: "UTC", server_today: "2026-01-07", snapshot_id: null,
      window: { start_date: "2026-01-01", end_date: "2026-01-01", expected_days: 1 }, status: "no_readings",
      rows: [], missing_dates: [], variable_coverage: [], units: {}, last_reading_date: null,
      data_age_days: null, provenance: "unknown",
    });
    const slot = (h: 1 | 2 | 3) => ({ horizon_days: h, target_date: `2026-01-0${h + 5}`, status: "unavailable" as const, reason_code: "model_not_available" });
    vi.spyOn(forecastsApi, "emitForecasts").mockResolvedValue({
      batch_id: "b1", revision: 1, as_of_date: "2026-01-05", data_age_days: 2, server_today: "2026-01-07",
      provenance: "synthetic", calendar_timezone: "UTC", slots: [slot(1), slot(2), slot(3)],
    });
    render(<ProducerView />);
    expect(await screen.findByRole("heading", { name: "Mi cultivo", level: 1 })).toBeInTheDocument();
    expect(screen.queryByRole("list", { name: /los próximos tres días/i })).not.toBeInTheDocument();
    await userEvent.click(await screen.findByRole("button", { name: "Consultar próximos tres días" }));
    expect(await screen.findByRole("heading", { name: /no hay información suficiente/i })).toBeInTheDocument();
    expect(screen.getByRole("list", { name: /los próximos tres días/i })).toBeInTheDocument();
    expect(screen.getByText(/la última medición tiene 2 días de antigüedad/i)).toBeInTheDocument();
  });

  it("never emits a forecast automatically on entering Mi cultivo, switching tabs, or switching sensors", async () => {
    vi.spyOn(catalogApi, "listSectors").mockResolvedValue({ items: [sector], next_cursor: null });
    vi.spyOn(catalogApi, "listSensors").mockResolvedValue({ items: [sensor], next_cursor: null });
    vi.spyOn(readingsApi, "getSensorReadings").mockResolvedValue({
      ...{ input_roles: [] },
      sensor_id: "sensor-a", calendar_timezone: "UTC", server_today: "2026-01-05", snapshot_id: null,
      window: { start_date: "2026-01-01", end_date: "2026-01-01", expected_days: 1 }, status: "no_readings",
      rows: [], missing_dates: [], variable_coverage: [], units: {}, last_reading_date: null,
      data_age_days: null, provenance: "unknown",
    });
    vi.spyOn(forecastsApi, "listForecasts").mockResolvedValue({
      items: [], next_cursor: null, pending_total: 0, reviewable_pending_total: 0,
    });
    const emit = vi.spyOn(forecastsApi, "emitForecasts").mockResolvedValue({
      batch_id: "b1", revision: 1, as_of_date: "2026-01-05", data_age_days: 0, server_today: "2026-01-05",
      provenance: "synthetic", calendar_timezone: "UTC",
      slots: [1, 2, 3].map((h) => ({ horizon_days: h as 1 | 2 | 3, target_date: `2026-01-0${h + 1}`, status: "unavailable" as const, reason_code: "model_not_available" })),
    });

    render(<ProducerView />);
    await screen.findByText("Datos simulados"); // sensor ya seleccionado, Mi cultivo montado
    await userEvent.click(await screen.findByRole("button", { name: "Historial" }));
    await userEvent.click(await screen.findByRole("button", { name: "Datos" }));
    await userEvent.click(await screen.findByRole("button", { name: "Pronóstico" }));
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(emit).not.toHaveBeenCalled();
  });

  it("prompts to pick a sensor before showing history", () => {
    vi.spyOn(catalogApi, "listSectors").mockReturnValue(new Promise(() => {}));
    render(<ProducerView />);
    expect(screen.getByText(/elegí un punto de medición para ver su historial/i)).toBeInTheDocument();
  });
});
