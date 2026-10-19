import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { EmissionProvenancePanel } from "./EmissionProvenancePanel";
import * as provenanceApi from "./provenanceApi";
import type { BatchProvenance } from "./provenanceApi";

afterEach(() => vi.restoreAllMocks());

const COMMIT = "c".repeat(40);
const DATASET = "d".repeat(64);
const ref = (h: 1 | 2 | 3) => ({
  model_version: `joblib-${h}`, horizon_days: h, contract_version: "producer_daily_h123_v1",
  trained_through: "2026-09-15", calibration_version: "cal-v1", assessment_reference: null, calibrated_through: null,
});

function provenance(overrides: Partial<BatchProvenance["horizons"][number]> = {}): BatchProvenance {
  return {
    batch_id: "b-1", sensor_id: "s", as_of_date: "2026-09-18", contract_version: "producer_daily_h123_v1",
    snapshot_id: DATASET,
    horizons: [
      {
        horizon_days: 1, status: "available", reason_code: null, mode: "single", model_reference: ref(1),
        ensemble_identity_sha256: null, code_identity: { available: true, commit: COMMIT, dirty: false },
        components: [], ...overrides,
      },
      { horizon_days: 2, status: "unavailable", reason_code: "model_not_available", mode: null, model_reference: null, ensemble_identity_sha256: null, code_identity: null, components: [] },
      { horizon_days: 3, status: "unavailable", reason_code: "model_not_available", mode: null, model_reference: null, ensemble_identity_sha256: null, code_identity: null, components: [] },
    ],
    not_persisted: ["full_config", "mlflow_run", "seed"],
  };
}

const region = () => screen.findByRole("region", { name: /procedencia de la emisión/i });

describe("EmissionProvenancePanel", () => {
  it("shows dataset sha, commit/dirty, model version, calibration and trained_through", async () => {
    const spy = vi.spyOn(provenanceApi, "getBatchProvenance").mockResolvedValue(provenance());
    render(<EmissionProvenancePanel sensorId="s" batchId="b-1" />);
    const panel = await region();
    expect(spy).toHaveBeenCalledWith("s", "b-1");
    for (const text of [DATASET, COMMIT, "joblib-1", "cal-v1", "2026-09-15"]) {
      expect(panel).toHaveTextContent(text);
    }
    expect(panel).toHaveTextContent(/sin cambios locales/i);
    expect(panel).not.toHaveTextContent(/commit.*no registrado/i);
  });

  it("flags a dirty working tree at training time", async () => {
    vi.spyOn(provenanceApi, "getBatchProvenance").mockResolvedValue(
      provenance({ code_identity: { available: true, commit: COMMIT, dirty: true } }),
    );
    render(<EmissionProvenancePanel sensorId="s" batchId="b-1" />);
    expect(await region()).toHaveTextContent(/con cambios sin confirmar/i);
  });

  it("says no registrado (never inferred) when the bundle recorded no commit", async () => {
    vi.spyOn(provenanceApi, "getBatchProvenance").mockResolvedValue(provenance({ code_identity: null }));
    render(<EmissionProvenancePanel sensorId="s" batchId="b-1" />);
    const panel = await region();
    expect(panel).toHaveTextContent(/commit.*no registrado/is);
    expect(panel).not.toHaveTextContent(COMMIT);
  });

  it("distinguishes git unavailable at training time from not registered", async () => {
    vi.spyOn(provenanceApi, "getBatchProvenance").mockResolvedValue(
      provenance({ code_identity: { available: false, commit: null, dirty: null } }),
    );
    render(<EmissionProvenancePanel sensorId="s" batchId="b-1" />);
    expect(await region()).toHaveTextContent(/commit.*no disponible al entrenar/is);
  });

  it("declares config, MLflow and seed as no disponible", async () => {
    vi.spyOn(provenanceApi, "getBatchProvenance").mockResolvedValue(provenance());
    render(<EmissionProvenancePanel sensorId="s" batchId="b-1" />);
    const panel = await region();
    for (const label of ["Configuración completa", "Corrida de MLflow", "Semilla"]) {
      expect(within(panel).getByText(new RegExp(`${label}.*no disponible`, "is"))).toBeInTheDocument();
    }
  });

  it("lists the ensemble identity and per-component commit", async () => {
    vi.spyOn(provenanceApi, "getBatchProvenance").mockResolvedValue(
      provenance({
        mode: "ensemble", code_identity: null, ensemble_identity_sha256: "e".repeat(64),
        components: [
          { family: "random_forest", code_identity: { available: true, commit: COMMIT, dirty: false } },
          { family: "logistic_regression", code_identity: null },
        ],
      }),
    );
    render(<EmissionProvenancePanel sensorId="s" batchId="b-1" />);
    const panel = await region();
    expect(panel).toHaveTextContent("e".repeat(64));
    expect(panel).toHaveTextContent(new RegExp(`Random Forest.*${COMMIT}`, "is"));
    expect(panel).toHaveTextContent(/Regresión logística.*no registrado/is);
  });

  it("shows a loading state, then an error with retry that recovers", async () => {
    const spy = vi.spyOn(provenanceApi, "getBatchProvenance")
      .mockRejectedValueOnce(new Error("backend caído"))
      .mockResolvedValue(provenance());
    render(<EmissionProvenancePanel sensorId="s" batchId="b-1" />);
    expect(screen.getByRole("status")).toHaveTextContent(/cargando procedencia/i);
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/backend caído/);
    await userEvent.click(within(alert).getByRole("button", { name: /reintentar/i }));
    expect(await region()).toHaveTextContent(DATASET);
    expect(spy).toHaveBeenCalledTimes(2);
  });

  it("does not crash when the backend is down", async () => {
    vi.spyOn(provenanceApi, "getBatchProvenance").mockRejectedValue(new TypeError("Failed to fetch"));
    render(<EmissionProvenancePanel sensorId="s" batchId="b-1" />);
    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: /procedencia de la emisión/i })).toBeNull();
  });

  it("ignores a late response from a previous batch", async () => {
    let resolveFirst: (value: BatchProvenance) => void = () => {};
    const spy = vi.spyOn(provenanceApi, "getBatchProvenance")
      .mockImplementationOnce(() => new Promise((resolve) => { resolveFirst = resolve; }))
      .mockResolvedValue({ ...provenance(), batch_id: "b-2", snapshot_id: "f".repeat(64) });
    const { rerender } = render(<EmissionProvenancePanel sensorId="s" batchId="b-1" />);
    rerender(<EmissionProvenancePanel sensorId="s" batchId="b-2" />);
    expect(await region()).toHaveTextContent("f".repeat(64));
    resolveFirst(provenance());
    await waitFor(() => expect(spy).toHaveBeenCalledTimes(2));
    expect(screen.getByRole("region", { name: /procedencia de la emisión/i })).toHaveTextContent("f".repeat(64));
  });
});
