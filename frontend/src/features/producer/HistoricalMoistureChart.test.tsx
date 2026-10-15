import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { HistoricalMoistureChart } from "./HistoricalMoistureChart";
import type { ReadingRow, ReadingsResult } from "./readingsApi";

function row(date: string, soil: number | null, flags: Partial<ReadingRow> = {}): ReadingRow {
  return {
    date,
    soil_moisture: soil,
    relative_humidity: null,
    solar_radiation: null,
    temperature: null,
    precipitation: null,
    wind_speed: null,
    et0: null,
    origin: "external_reanalysis",
    quality_flags: [],
    imputed_variables: [],
    unverified_variables: [],
    ...flags,
  };
}

function readings(rows: ReadingRow[], start = "2023-06-04", end = "2023-06-09"): ReadingsResult {
  return {
    ...{ input_roles: [] },
    sensor_id: "pergamino-ensemble-demo",
    calendar_timezone: "UTC",
    server_today: end,
    snapshot_id: null,
    window: { start_date: start, end_date: end, expected_days: 6 },
    status: "ready",
    rows,
    missing_dates: [],
    variable_coverage: [],
    units: { soil_moisture: "m3/m3" },
    last_reading_date: end,
    data_age_days: 0,
    provenance: "external_reanalysis",
  };
}

const BASE_ROWS = [
  row("2023-06-04", 0.34),
  row("2023-06-05", 0.33),
  row("2023-06-06", null),
  row("2023-06-07", 0.32, { imputed_variables: ["soil_moisture"] }),
  row("2023-06-08", 0.31),
  row("2023-06-09", 0.3, { unverified_variables: ["soil_moisture"] }),
];

describe("HistoricalMoistureChart", () => {
  it("describes observed, imputed, unverified and missing days separately, never as measurements", () => {
    const { container } = render(
      <HistoricalMoistureChart readings={readings(BASE_ROWS)} emissionDate="2023-06-07" revealedThrough="2023-06-09" threshold={null} />,
    );
    const chart = screen.getByRole("img", { name: /3 observados, 1 imputados, 1 de procedencia no verificada y 1 sin dato/i });
    expect(chart).toBeInTheDocument();
    expect(container.querySelectorAll(".hmc-chart .hmc-obs").length).toBe(3);
    expect(container.querySelectorAll(".hmc-chart path.hmc-imp").length).toBe(1);
    expect(container.querySelectorAll(".hmc-chart rect.hmc-unv").length).toBe(1);
    expect(screen.getByText(/imputado \(no es una medición\)/i)).toBeInTheDocument();
  });

  it("does not connect across a missing day", () => {
    const { container } = render(
      <HistoricalMoistureChart readings={readings(BASE_ROWS.slice(0, 4))} emissionDate="2023-06-04" revealedThrough="2023-06-07" threshold={null} />,
    );
    // 04-05 conectados; 05-06 y 06-07 no (06 es un hueco).
    expect(container.querySelectorAll(".hmc-line").length).toBe(1);
    expect(container.querySelectorAll(".hmc-chart path.hmc-miss").length).toBe(1);
  });

  it("never draws values after the revealed clock, even if the payload contained them", () => {
    const { container } = render(
      <HistoricalMoistureChart readings={readings(BASE_ROWS)} emissionDate="2023-06-04" revealedThrough="2023-06-05" threshold={null} />,
    );
    expect(container.querySelectorAll(".hmc-chart .hmc-obs").length).toBe(2);
    expect(container.querySelectorAll(".hmc-chart path.hmc-imp").length).toBe(0);
    expect(screen.getByText(/aún no revelado/i)).toBeInTheDocument();
  });

  it("shows the protocol threshold only when it is provided in comparable units", () => {
    const { rerender } = render(
      <HistoricalMoistureChart readings={readings(BASE_ROWS)} emissionDate="2023-06-07" revealedThrough="2023-06-09" threshold={0.313} />,
    );
    expect(screen.getAllByText(/umbral 31.3 %/i).length).toBeGreaterThan(0);
    rerender(<HistoricalMoistureChart readings={readings(BASE_ROWS)} emissionDate="2023-06-07" revealedThrough="2023-06-09" threshold={null} />);
    expect(screen.queryByText(/umbral 31.3 %/i)).not.toBeInTheDocument();
  });

  it("draws what was observed after the emission differently from what existed when it was issued", () => {
    const { container } = render(
      <HistoricalMoistureChart readings={readings(BASE_ROWS)} emissionDate="2023-06-05" revealedThrough="2023-06-09" threshold={null} />,
    );
    // Observados: 04 y 05 (hasta la emisión); 08 (posterior). 06 es hueco, 07 imputado y 09 no verificado.
    expect(container.querySelectorAll(".hmc-chart .hmc-obs:not(.hmc-obs--later)").length).toBe(2);
    expect(container.querySelectorAll(".hmc-chart .hmc-obs--later").length).toBe(1);
    expect(screen.getByRole("img", { name: /1 observados son posteriores a la emisión del 5 jun/i })).toBeInTheDocument();
    expect(screen.getByText("Observado hasta la emisión")).toBeInTheDocument();
    expect(screen.getByText("Observado después de la emisión")).toBeInTheDocument();
  });
});
