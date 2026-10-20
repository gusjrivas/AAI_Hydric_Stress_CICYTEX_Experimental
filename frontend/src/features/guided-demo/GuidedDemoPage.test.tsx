import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { GuidedDemoPage } from "./GuidedDemoPage";
import * as cicytexApi from "../defense/cicytexApi";
import * as historicalApi from "../producer/historicalApi";
import * as provenanceApi from "../producer/provenanceApi";
import * as sensorLabApi from "../lab/sensorLabApi";
import * as qualityApi from "../quality/api";
import * as forecastApi from "../forecast/api";

const METRIC = { n: 0, tp: 0, tn: 0, fp: 0, fn: 0, mcc: null, precision: null, recall: null, f1: null, coverage: 0 };

function pred(method: string, alert: boolean, extra: Record<string, unknown> = {}) {
  return {
    method, score: alert ? 0.8 : 0.1, alert, target_date: "2023-07-07",
    observed_soil_moisture: null, observed_label: null, outcome: null, ...extra,
  };
}
function cySession(over: Record<string, unknown> = {}, ensembleAlert = false, members: boolean[] = [false, false, false], extra: Record<string, unknown> = {}) {
  return {
    session_id: "s1", sensor_id: "CP1_S1", emission_date: "2023-07-06", horizon_days: 1,
    revealed_through: "2023-07-06", threshold: 0.21, proxy_notice: "P20 estimado solo con entrenamiento; no es estres fisiologico observado.",
    predictions: [
      pred("logistic_regression", members[0], extra), pred("random_forest", members[1], extra),
      pred("hist_gradient_boosting_classifier", members[2], extra),
      pred("ensemble", ensembleAlert, extra), pred("persistence", false, extra),
    ],
    readings: [], metrics: { ensemble: METRIC }, feedback: null, can_advance: true, ...over,
  } as unknown as cicytexApi.CicytexSession;
}
const CY_PROV = {
  dataset_sha256: "a".repeat(64), git_commit: "b".repeat(40), seed: 4, ensemble_policy: "x",
  horizons: {},
} as unknown as cicytexApi.CicytexProvenance;

function component(family: string, alert: boolean) {
  return { family, alert, score: alert ? 0.9 : 0.1, decision_threshold: 0.5, calibrated_through: "x", model_reference: {} };
}
function producerBatch(sensor: string, asOf: string, target: string, alert: boolean, votes: boolean[], threshold = 0.3) {
  return {
    batch_id: `batch_${sensor}`, as_of_date: asOf, revision: 1, data_age_days: 0, server_today: asOf, provenance: "external_reanalysis",
    calendar_timezone: "UTC",
    slots: [
      {
        status: "available", horizon_days: 1, target_date: target, alert, forecast_id: "fc1", display_probability: null,
        event_threshold: { variable: "soil_moisture", comparison: "lt", value: threshold, unit: "m3/m3" },
        ensemble: {
          combined_alert: alert, combined_probability: alert ? 0.7 : 0.1, agreement_category: "x",
          positive_votes: votes.filter(Boolean).length,
          components: [component("logistic_regression", votes[0]), component("random_forest", votes[1]), component("hist_gradient_boosting_classifier", votes[2])],
        },
      },
      { status: "unavailable", horizon_days: 2, target_date: "x", reason_code: "already_available" },
    ],
  } as unknown as Awaited<ReturnType<typeof historicalApi.getHistoricalForecastBatch>>;
}
function readings(date: string, soil: number | null, flags: { imputed?: boolean; unverified?: boolean } = {}) {
  return {
    rows: [{
      date, soil_moisture: soil, origin: "external_reanalysis", quality_flags: [],
      imputed_variables: flags.imputed ? ["soil_moisture"] : [], unverified_variables: flags.unverified ? ["soil_moisture"] : [],
    }],
    units: { soil_moisture: "m3/m3" },
  } as unknown as Awaited<ReturnType<typeof historicalApi.getHistoricalReadings>>;
}
const BATCH_PROV = {
  snapshot_id: "c".repeat(64), as_of_date: "x", batch_id: "b", contract_version: "v", sensor_id: "s",
  horizons: [], not_persisted: ["full_config", "mlflow_run", "seed"],
} as unknown as Awaited<ReturnType<typeof provenanceApi.getBatchProvenance>>;

const next = () => screen.getByRole("button", { name: /^siguiente sitio/i });
const advance = () => screen.getByRole("button", { name: /^avanzar un día/i });

async function toStep(user: ReturnType<typeof userEvent.setup>, n: number) {
  for (let i = 1; i < n; i += 1) {
    await screen.findByText(/^(sin alerta|alerta prevista)$/i);
    await user.click(next());
  }
}

beforeEach(() => {
  vi.restoreAllMocks();
  vi.spyOn(cicytexApi, "createCicytexSession").mockResolvedValue(cySession({}, false, [false, false, false]) as never);
  vi.spyOn(cicytexApi, "getCicytexProvenance").mockResolvedValue(CY_PROV);
  vi.spyOn(provenanceApi, "getBatchProvenance").mockResolvedValue(BATCH_PROV);
  vi.spyOn(historicalApi, "getHistoricalForecastBatch").mockImplementation(async (sensor) =>
    sensor === "pergamino-ensemble-demo"
      ? producerBatch(sensor, "2023-06-13", "2023-06-14", true, [true, true, false])
      : producerBatch(sensor, "2024-10-20", "2024-10-21", false, [false, false, false]));
});

describe("GuidedDemoPage · estructura del recorrido", () => {
  it("shows a progress bar «Paso 1 de 4» and the CICYTEX step first, with honest framing", async () => {
    render(<GuidedDemoPage />);
    expect(screen.getByText("Paso 1 de 4")).toBeInTheDocument();
    const bar = screen.getByRole("progressbar", { name: /progreso del recorrido/i });
    expect(bar).toHaveAttribute("value", "1");
    expect(bar).toHaveAttribute("max", "4");
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(/recorrido guiado/i);
    expect(screen.getByRole("heading", { level: 2, name: /CICYTEX/ })).toBeInTheDocument();
    const honesty = screen.getByRole("note", { name: /alcance del recorrido/i });
    expect(honesty).toHaveTextContent(/es un recorrido, no una evaluación/i);
    expect(honesty).toHaveTextContent(/apoyo a la decisión/i);
    expect(honesty).toHaveTextContent(/no riega ni decide cuánto regar/i);
    await screen.findByText(/sin alerta/i);
    expect(document.body.textContent).not.toMatch(/laya/i);
  });

  it("walks the four sites in order and moves focus to the new step heading", async () => {
    const user = userEvent.setup();
    render(<GuidedDemoPage />);
    for (const [n, name] of [[2, /Pergamino/], [3, /Melchor Romero/], [4, /sensores simulados/i]] as const) {
      await screen.findByText(/^(sin alerta|alerta prevista)$|generar datos/i);
      await user.click(next());
      expect(screen.getByText(`Paso ${n} de 4`)).toBeInTheDocument();
      const heading = screen.getByRole("heading", { level: 2, name });
      expect(heading).toHaveFocus();
    }
    expect(screen.queryByRole("button", { name: /^siguiente sitio/i })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /sitio anterior/i }));
    expect(screen.getByText("Paso 3 de 4")).toBeInTheDocument();
  });

  it("restarts a step from its initial state when coming back to it (no stale reveal)", async () => {
    const user = userEvent.setup();
    vi.spyOn(cicytexApi, "advanceCicytexSession").mockResolvedValue(
      cySession({ can_advance: false }, false, [false, false, false], { observed_soil_moisture: 0.254, observed_label: 0, outcome: "VN" }) as never);
    render(<GuidedDemoPage />);
    await screen.findByText("Sin alerta");
    await user.click(advance());
    await screen.findByRole("region", { name: /qué ocurrió después/i });
    await user.click(next());
    await screen.findByText("Alerta prevista");
    await user.click(screen.getByRole("button", { name: /sitio anterior/i }));
    await screen.findByText("Sin alerta");
    expect(screen.queryByRole("region", { name: /qué ocurrió después/i })).not.toBeInTheDocument();
    expect(advance()).toBeEnabled();
  });
});

describe("CICYTEX", () => {
  it("shows a big traffic light with how many of the 3 models agree, and no probabilities", async () => {
    render(<GuidedDemoPage />);
    expect(await screen.findByText("Sin alerta")).toBeInTheDocument();
    expect(screen.getByText("3 de 3 modelos coinciden con este resultado")).toBeInTheDocument();
    expect(cicytexApi.createCicytexSession).toHaveBeenCalledWith("CP1_S1", "2023-07-06", 1);
    const panel = screen.getByRole("region", { name: /CICYTEX/ });
    expect(panel.textContent).not.toMatch(/\d%|0[.,]\d{2}/);
  });

  it("counts the models that agree with the shown result when the alert is predicted", async () => {
    vi.mocked(cicytexApi.createCicytexSession).mockResolvedValue(cySession({}, true, [true, true, false]) as never);
    render(<GuidedDemoPage />);
    expect(await screen.findByText("Alerta prevista")).toBeInTheDocument();
    expect(screen.getByText("2 de 3 modelos coinciden con este resultado")).toBeInTheDocument();
  });

  it("hides the observed outcome until «Avanzar un día» and then reveals it", async () => {
    const user = userEvent.setup();
    vi.spyOn(cicytexApi, "advanceCicytexSession").mockResolvedValue(
      cySession({ revealed_through: "2023-07-07", can_advance: false }, false, [false, false, false], {
        observed_soil_moisture: 0.254, observed_label: 0, outcome: "VN",
      }) as never);
    render(<GuidedDemoPage />);
    await screen.findByText("Sin alerta");
    expect(screen.queryByText(/no hubo humedad baja/i)).not.toBeInTheDocument();
    await user.click(advance());
    const result = await screen.findByRole("region", { name: /qué ocurrió después/i });
    expect(result).toHaveTextContent(/no hubo humedad baja/i);
    expect(result).toHaveTextContent(/0[.,]254/);
    expect(result).toHaveFocus();
    expect(screen.getByRole("button", { name: /^avanzar un día/i })).toBeDisabled();
  });

  it("says low moisture did occur when the revealed label is 1", async () => {
    const user = userEvent.setup();
    vi.spyOn(cicytexApi, "advanceCicytexSession").mockResolvedValue(
      cySession({ can_advance: false }, false, [false, false, false], { observed_soil_moisture: 0.19, observed_label: 1, outcome: "FN" }) as never);
    render(<GuidedDemoPage />);
    await screen.findByText("Sin alerta");
    await user.click(advance());
    const result = await screen.findByRole("region", { name: /qué ocurrió después/i });
    expect(result).toHaveTextContent(/sí hubo humedad baja/i);
    expect(result).not.toHaveTextContent(/no hubo humedad baja/i);
  });

  it("shows the backend proxy notice next to the observed moisture", async () => {
    const user = userEvent.setup();
    vi.spyOn(cicytexApi, "advanceCicytexSession").mockResolvedValue(
      cySession({ can_advance: false }, false, [false, false, false], { observed_soil_moisture: 0.254, observed_label: 0, outcome: "VN" }) as never);
    render(<GuidedDemoPage />);
    await screen.findByText("Sin alerta");
    await user.click(advance());
    const result = await screen.findByRole("region", { name: /qué ocurrió después/i });
    expect(result).toHaveTextContent(/no es estres fisiologico observado/i);
  });

  it("does not claim «No hubo humedad baja» when the revealed label is missing", async () => {
    const user = userEvent.setup();
    vi.spyOn(cicytexApi, "advanceCicytexSession").mockResolvedValue(
      cySession({ can_advance: false }, false, [false, false, false], { observed_soil_moisture: null, observed_label: null, outcome: "VN" }) as never);
    render(<GuidedDemoPage />);
    await screen.findByText("Sin alerta");
    await user.click(advance());
    const result = await screen.findByRole("region", { name: /qué ocurrió después/i });
    expect(result).not.toHaveTextContent(/no hubo humedad baja|sí hubo humedad baja|el pronóstico (no )?coincidió/i);
    expect(result).toHaveTextContent(/no hay una observación concluyente/i);
  });

  it("leaves no current traffic light next to the alert when advancing fails", async () => {
    const user = userEvent.setup();
    vi.spyOn(cicytexApi, "advanceCicytexSession").mockRejectedValueOnce(new Error("x"));
    render(<GuidedDemoPage />);
    await screen.findByText("Sin alerta");
    await user.click(advance());
    await screen.findByRole("alert");
    expect(screen.queryByText(/^(sin alerta|alerta prevista)$/i)).not.toBeInTheDocument();
  });

  it("collapses technical detail and shows dataset hash and commit only when they exist", async () => {
    const user = userEvent.setup();
    render(<GuidedDemoPage />);
    await screen.findByText("Sin alerta");
    const details = screen.getByText("Ver detalle técnico").closest("details")!;
    expect(details).not.toHaveAttribute("open");
    await user.click(screen.getByText("Ver detalle técnico"));
    await waitFor(() => expect(details).toHaveTextContent("a".repeat(64)));
    expect(details).toHaveTextContent("b".repeat(40));
    expect(screen.getByText(/de dónde sale/i).closest("p")).toHaveTextContent(/CICYTEX/);
  });

  it("declares «no disponible» when provenance fails", async () => {
    const user = userEvent.setup();
    vi.mocked(cicytexApi.getCicytexProvenance).mockRejectedValue(new Error("boom"));
    render(<GuidedDemoPage />);
    await screen.findByText("Sin alerta");
    await user.click(screen.getByText("Ver detalle técnico"));
    const details = screen.getByText("Ver detalle técnico").closest("details")!;
    await waitFor(() => expect(details).toHaveTextContent(/dataset.*no disponible/i));
    expect(details).toHaveTextContent(/commit.*no disponible/i);
  });

  it("declares «no disponible» for a missing commit but still shows the dataset hash", async () => {
    const user = userEvent.setup();
    vi.mocked(cicytexApi.getCicytexProvenance).mockResolvedValue({ ...CY_PROV, git_commit: "" } as never);
    render(<GuidedDemoPage />);
    await screen.findByText("Sin alerta");
    await user.click(screen.getByText("Ver detalle técnico"));
    const details = screen.getByText("Ver detalle técnico").closest("details")!;
    await waitFor(() => expect(details).toHaveTextContent("a".repeat(64)));
    expect(details).toHaveTextContent(/commit.*no disponible/i);
  });

  it("shows a Spanish role=alert with «Reintentar» when the session cannot be opened", async () => {
    const user = userEvent.setup();
    vi.mocked(cicytexApi.createCicytexSession).mockRejectedValueOnce(new Error("HTTP 500 raw"));
    render(<GuidedDemoPage />);
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/no se pudo cargar/i);
    expect(alert.textContent).not.toMatch(/HTTP 500/);
    expect(screen.queryByText(/^(sin alerta|alerta prevista)$/i)).not.toBeInTheDocument();
    await user.click(within(alert).getByRole("button", { name: "Reintentar" }));
    expect(await screen.findByText("Sin alerta")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("shows an alert with «Reintentar» when advancing fails and keeps the outcome hidden", async () => {
    const user = userEvent.setup();
    vi.spyOn(cicytexApi, "advanceCicytexSession").mockRejectedValueOnce(new Error("x"));
    render(<GuidedDemoPage />);
    await screen.findByText("Sin alerta");
    await user.click(advance());
    const alert = await screen.findByRole("alert");
    expect(within(alert).getByRole("button", { name: "Reintentar" })).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: /qué ocurrió después/i })).not.toBeInTheDocument();
  });
});

describe("Pergamino y Melchor Romero", () => {
  it("shows Pergamino's alert from its own emission and agreement, with its own source", async () => {
    const user = userEvent.setup();
    render(<GuidedDemoPage />);
    await toStep(user, 2);
    expect(await screen.findByText("Alerta prevista")).toBeInTheDocument();
    expect(screen.getByText("2 de 3 modelos coinciden con este resultado")).toBeInTheDocument();
    expect(historicalApi.getHistoricalForecastBatch).toHaveBeenCalledWith("pergamino-ensemble-demo", "2023-06-13");
    expect(screen.getByText(/de dónde sale/i).closest("p")).toHaveTextContent(/ERA5-Land.*NASA POWER/);
    expect(screen.getByText(/de dónde sale/i).closest("p")).not.toHaveTextContent(/ESA CCI/);
  });

  it("reveals the observed value after advancing and says whether moisture was low", async () => {
    const user = userEvent.setup();
    const spy = vi.spyOn(historicalApi, "getHistoricalReadings").mockResolvedValue(readings("2023-06-14", 0.25));
    render(<GuidedDemoPage />);
    await toStep(user, 2);
    await screen.findByText("Alerta prevista");
    expect(spy).not.toHaveBeenCalled();
    await user.click(advance());
    const result = await screen.findByRole("region", { name: /qué ocurrió después/i });
    expect(spy).toHaveBeenCalledWith("pergamino-ensemble-demo", "2023-06-14", expect.any(Number));
    expect(result).toHaveTextContent(/25[.,]0 %/);
    expect(result).toHaveTextContent(/sí hubo humedad baja/i);
    expect(result).toHaveTextContent(/el pronóstico coincidió/i);
  });

  it("does not claim a result when the target-day value is imputed", async () => {
    const user = userEvent.setup();
    vi.spyOn(historicalApi, "getHistoricalReadings").mockResolvedValue(readings("2023-06-14", 0.4, { imputed: true }));
    render(<GuidedDemoPage />);
    await toStep(user, 2);
    await screen.findByText("Alerta prevista");
    await user.click(advance());
    const result = await screen.findByRole("region", { name: /qué ocurrió después/i });
    expect(result).toHaveTextContent(/no es una observación independiente/i);
    expect(result).not.toHaveTextContent(/no hubo humedad baja|sí hubo humedad baja|el pronóstico coincidió/i);
  });

  it("leaves no current traffic light next to the alert when the readings request fails", async () => {
    const user = userEvent.setup();
    vi.spyOn(historicalApi, "getHistoricalReadings").mockRejectedValueOnce(new Error("x"));
    render(<GuidedDemoPage />);
    await toStep(user, 2);
    await screen.findByText("Alerta prevista");
    await user.click(advance());
    await screen.findByRole("alert");
    expect(screen.queryByText(/^(sin alerta|alerta prevista)$/i)).not.toBeInTheDocument();
  });

  it("says there is no observation when the source has none for the target day", async () => {
    const user = userEvent.setup();
    vi.spyOn(historicalApi, "getHistoricalReadings").mockResolvedValue(readings("2023-06-14", null));
    render(<GuidedDemoPage />);
    await toStep(user, 2);
    await screen.findByText("Alerta prevista");
    await user.click(advance());
    expect(await screen.findByText(/sin observación en la fuente/i)).toBeInTheDocument();
  });

  it("uses Melchor Romero's own dataset and shows the emission provenance in the technical detail", async () => {
    const user = userEvent.setup();
    render(<GuidedDemoPage />);
    await toStep(user, 3);
    expect(await screen.findByText("Sin alerta")).toBeInTheDocument();
    expect(historicalApi.getHistoricalForecastBatch).toHaveBeenCalledWith("melchor-romero-demo", "2024-10-20");
    const source = screen.getByText(/de dónde sale/i).closest("p")!;
    expect(source).toHaveTextContent(/ESA CCI/);
    expect(source).not.toHaveTextContent(/ERA5/);
    const details = screen.getByText("Ver detalle técnico").closest("details")!;
    expect(details).not.toHaveAttribute("open");
    await user.click(screen.getByText("Ver detalle técnico"));
    await waitFor(() => expect(details).toHaveTextContent("c".repeat(64)));
  });

  it("shows a Spanish role=alert with «Reintentar» when the emission cannot be loaded", async () => {
    const user = userEvent.setup();
    const calls = vi.mocked(historicalApi.getHistoricalForecastBatch);
    render(<GuidedDemoPage />);
    await screen.findByText("Sin alerta");
    calls.mockRejectedValueOnce(new Error("Failed to fetch"));
    await user.click(next());
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/no se pudo cargar/i);
    await user.click(within(alert).getByRole("button", { name: "Reintentar" }));
    expect(await screen.findByText("Alerta prevista")).toBeInTheDocument();
  });
});

describe("Sensores simulados (laboratorio)", () => {
  beforeEach(() => {
    vi.spyOn(sensorLabApi, "ingestLabReading").mockResolvedValue({ timestamp: "2026-04-30T00:00:00Z", filas_totales: 120 });
    vi.spyOn(qualityApi, "getQualityReport").mockResolvedValue({
      sensor_id: "lab", total_rows: 120, period_start: "2026-01-01", period_end: "2026-04-30", missing_pct: {},
      duplicate_timestamps: [], out_of_range: { temperature: ["2026-05-01T00:00:00Z"] }, anomalies_detected: 0,
      anomaly_method: "isolation_forest", anomaly_contamination: 0.05, anomaly_columns: [], is_diagnostic_only: true, note: "n",
    } as never);
    vi.spyOn(forecastApi, "listFeedback").mockResolvedValue({
      rows: [{ fecha: "2026-04-30", alerta_generada: 0, estado_validacion: "pendiente", etiqueta_corregida: null, observacion: null, y_proba: 0.12, fecha_objetivo: "2026-05-03" }],
    } as never);
    vi.spyOn(forecastApi, "runForecast").mockResolvedValue({
      verdicts: [{ fecha: "2026-04-30", alerta: false, probabilidad: 0.12, fecha_objetivo: "2026-05-03" }], train_rows: 1, test_rows: 1,
    } as never);
  });

  it("is labelled SIMULACIÓN without a physical sensor and offers scenario A first", async () => {
    const user = userEvent.setup();
    render(<GuidedDemoPage />);
    await toStep(user, 4);
    const panel = screen.getByRole("region", { name: /sensores simulados/i });
    expect(panel).toHaveTextContent(/SIMULACIÓN/);
    expect(panel).toHaveTextContent(/sin sensor físico/i);
    expect(screen.queryByText(/^(sin alerta|alerta prevista)$/i)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^avanzar un día/i })).toBeDisabled();
    await user.click(screen.getByRole("button", { name: /generar datos simulados/i }));
    expect(await screen.findByText("Sin alerta")).toBeInTheDocument();
    expect(panel).toHaveTextContent(/escenario A/i);
    expect(screen.queryByRole("region", { name: /qué ocurrió después/i })).not.toBeInTheDocument();
  });

  it("does not claim a model comparison or a probability in the laboratory", async () => {
    const user = userEvent.setup();
    render(<GuidedDemoPage />);
    await toStep(user, 4);
    await user.click(screen.getByRole("button", { name: /generar datos simulados/i }));
    await screen.findByText("Sin alerta");
    const panel = screen.getByRole("region", { name: /sensores simulados/i });
    expect(panel).toHaveTextContent(/comparación entre modelos no está disponible/i);
    expect(panel.textContent).not.toMatch(/\d de 3 modelos/);
    expect(panel.textContent).not.toMatch(/0[.,]12|12 ?%/);
  });

  it("advances to scenario B and calls the anomaly a measurement problem, not low moisture", async () => {
    const user = userEvent.setup();
    render(<GuidedDemoPage />);
    await toStep(user, 4);
    await user.click(screen.getByRole("button", { name: /generar datos simulados/i }));
    await screen.findByText("Sin alerta");
    await waitFor(() => expect(advance()).toBeEnabled());
    await user.click(advance());
    const result = await screen.findByRole("region", { name: /qué ocurrió después/i });
    expect(result).toHaveTextContent(/escenario B/i);
    expect(result).toHaveTextContent(/anomalía de medición/i);
    expect(result).toHaveTextContent(/no es humedad baja/i);
    expect(screen.getByRole("button", { name: /^avanzar un día/i })).toBeDisabled();
  });

  it("keeps scenario A's traffic light after scenario B emits a different, later forecast", async () => {
    const user = userEvent.setup();
    const rowA = { fecha: "2026-04-30", alerta_generada: 0, estado_validacion: "pendiente", etiqueta_corregida: null, observacion: null, y_proba: 0.12, fecha_objetivo: "2026-05-03" };
    const rowB = { ...rowA, fecha: "2026-05-01", alerta_generada: 1, fecha_objetivo: "2026-05-04" };
    vi.mocked(forecastApi.runForecast)
      .mockResolvedValueOnce({ verdicts: [{ fecha: "2026-04-30", alerta: false, probabilidad: 0.12, fecha_objetivo: "2026-05-03" }], train_rows: 1, test_rows: 1 } as never)
      .mockResolvedValueOnce({ verdicts: [{ fecha: "2026-05-01", alerta: true, probabilidad: 0.9, fecha_objetivo: "2026-05-04" }], train_rows: 1, test_rows: 1 } as never);
    vi.mocked(forecastApi.listFeedback)
      .mockResolvedValueOnce({ rows: [] } as never)
      .mockResolvedValueOnce({ rows: [rowA] } as never)
      .mockResolvedValue({ rows: [rowB, rowA] } as never);
    render(<GuidedDemoPage />);
    await toStep(user, 4);
    await user.click(screen.getByRole("button", { name: /generar datos simulados/i }));
    await screen.findByText("Sin alerta");
    await waitFor(() => expect(advance()).toBeEnabled());
    await user.click(advance());
    await screen.findByRole("region", { name: /qué ocurrió después/i });
    expect(screen.getByText("Sin alerta")).toBeInTheDocument();
    expect(screen.queryByText("Alerta prevista")).not.toBeInTheDocument();
    expect(screen.getByRole("region", { name: /sensores simulados/i })).toHaveTextContent(/30 de abr/);
  });

  it("declares technical identity as not available for synthetic data", async () => {
    const user = userEvent.setup();
    render(<GuidedDemoPage />);
    await toStep(user, 4);
    await user.click(screen.getByText("Ver detalle técnico"));
    const details = screen.getByText("Ver detalle técnico").closest("details")!;
    expect(details).toHaveTextContent(/commit.*no disponible/i);
    expect(screen.getByText(/de dónde sale/i).closest("p")).toHaveTextContent(/sintéticos/i);
  });

  it("shows a Spanish role=alert with «Reintentar» when scenario A fails, and recovers with a new session", async () => {
    const user = userEvent.setup();
    vi.mocked(sensorLabApi.ingestLabReading).mockRejectedValueOnce(new TypeError("Failed to fetch"));
    render(<GuidedDemoPage />);
    await toStep(user, 4);
    await user.click(screen.getByRole("button", { name: /generar datos simulados/i }));
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/no se pudo/i);
    await user.click(within(alert).getByRole("button", { name: "Reintentar" }));
    await waitFor(() => expect(screen.queryByRole("alert")).not.toBeInTheDocument());
    expect(screen.getByRole("button", { name: /generar datos simulados/i })).toBeEnabled();
  });
});
