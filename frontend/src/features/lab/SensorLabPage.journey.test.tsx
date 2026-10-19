import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { SensorLabPage } from "./SensorLabPage";
import * as sensorLabApi from "./sensorLabApi";
import * as qualityApi from "../quality/api";
import * as forecastApi from "../forecast/api";
import { LAB_HISTORY_DAYS, LAB_SEED } from "./useSensorLabScenarios";
import type { QualityReport } from "../quality/api";

function quality(): QualityReport {
  return {
    sensor_id: "lab-test",
    total_rows: LAB_HISTORY_DAYS,
    period_start: "2026-01-01",
    period_end: "2026-04-30",
    missing_pct: { soil_moisture: 0 },
    duplicate_timestamps: [],
    out_of_range: {},
    anomalies_detected: 0,
    anomaly_method: "isolation_forest",
    anomaly_contamination: 0.05,
    anomaly_columns: ["soil_moisture"],
    is_diagnostic_only: true,
    note: "Diagnóstico exploratorio.",
  };
}

const stepA = () => screen.getByRole("button", { name: /generar historial de prueba/i });
const stepB = () => screen.getByRole("button", { name: /introducir una lectura anómala/i });
const reset = () => screen.getByRole("button", { name: /iniciar una sesión nueva/i });
const panel = () => screen.getByRole("region", { name: "Trazabilidad de esta sesión de prueba" });

describe("SensorLabPage · jerarquía de acciones y trazabilidad", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(forecastApi, "listFeedback").mockResolvedValue({ rows: [] });
    vi.spyOn(forecastApi, "runForecast").mockResolvedValue({
      verdicts: [{ fecha: "2026-04-01", alerta: false, probabilidad: 0.1, fecha_objetivo: "2026-04-04" }],
      train_rows: 90,
      test_rows: 20,
    });
    vi.spyOn(sensorLabApi, "ingestLabReading").mockResolvedValue({
      timestamp: "2026-04-30T00:00:00Z",
      filas_totales: LAB_HISTORY_DAYS,
    });
    vi.spyOn(qualityApi, "getQualityReport").mockResolvedValue(quality());
  });

  it("marks only the current phase step as primary; the rest and the reset are secondary", async () => {
    const user = userEvent.setup();
    render(<SensorLabPage />);
    expect(stepA()).toHaveClass("sl-btn-primary");
    expect(stepB()).not.toHaveClass("sl-btn-primary");
    expect(reset()).not.toHaveClass("sl-btn-primary");
    expect(reset()).toHaveClass("sl-btn-secondary");

    await user.click(stepA());
    await waitFor(() => expect(stepB()).toBeEnabled());
    expect(stepB()).toHaveClass("sl-btn-primary");
    expect(stepA()).not.toHaveClass("sl-btn-primary");
  });

  it("explains why the disabled steps are unavailable through a linked note", () => {
    render(<SensorLabPage />);
    const b = stepB();
    expect(b).toBeDisabled();
    const noteId = b.getAttribute("aria-describedby");
    expect(noteId).toBeTruthy();
    const note = document.getElementById(noteId as string);
    expect(note).toHaveTextContent(/se habilita al completar el paso anterior/i);
    expect(stepA()).not.toHaveAttribute("aria-describedby");
  });

  it("states the true reason for each reachable phase through the linked note", async () => {
    const user = userEvent.setup();
    render(<SensorLabPage />);
    const stepC = () => screen.getByRole("button", { name: /simular una interrupción/i });
    const stepD = () => screen.getByRole("button", { name: /simular la recuperación/i });
    const noteOf = (button: HTMLElement) => document.getElementById(button.getAttribute("aria-describedby") as string);

    expect(noteOf(stepB())).toHaveTextContent(/solo está disponible el paso A/i);
    await user.click(stepA());
    await waitFor(() => expect(stepB()).toBeEnabled());
    expect(noteOf(stepC())).toHaveTextContent(/solo está disponible el paso B/i);
    await user.click(stepB());
    await waitFor(() => expect(stepC()).toBeEnabled());
    expect(noteOf(stepD())).toHaveTextContent(/solo está disponible el paso C/i);
    await user.click(stepC());
    await waitFor(() => expect(stepD()).toBeEnabled());
    expect(noteOf(stepB())).toHaveTextContent(/solo está disponible el paso D/i);
    await user.click(stepD());
    await waitFor(() => expect(stepD()).toBeDisabled());
    expect(noteOf(stepD())).toHaveTextContent(/el recorrido A–D terminó/i);
  });

  it("shows the traceability panel with sensor, seed, synthetic provenance and fictitious clock", () => {
    render(<SensorLabPage />);
    const p = within(panel());
    expect(p.getByText(/^lab-/)).toBeInTheDocument();
    expect(p.getByText(String(LAB_SEED))).toBeInTheDocument();
    expect(p.getByText("Procedencia de las lecturas").nextElementSibling).toHaveTextContent(/^sintético$/);
    expect(panel()).toHaveTextContent(/el reloj es ficticio/i);
  });

  it("declares unavailable the artifacts that do not exist in this journey", () => {
    render(<SensorLabPage />);
    for (const label of [
      "Commit",
      "SHA-256 del dataset",
      "Corridas de MLflow",
      "Versión de modelo",
      "Linaje de recalibración",
    ]) {
      const dt = within(panel()).getByText(label);
      expect(dt.nextElementSibling).toHaveTextContent(/no disponible/i);
    }
  });

  it("states that data and human review are synthetic and give no scientific evidence", () => {
    render(<SensorLabPage />);
    expect(panel()).toHaveTextContent(/datos y la revisión humana son sintéticos/i);
    expect(panel()).toHaveTextContent(/no aportan evidencia científica/i);
  });
});
