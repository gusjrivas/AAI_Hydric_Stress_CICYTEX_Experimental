import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { StrictMode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { HistoricalReplayPage } from "./HistoricalReplayPage";
import * as api from "./api";
import { ReplayNotFoundError } from "./api";

const CANDIDATE: api.ReplayCandidateInfo = {
  experiment_id: "4",
  run_id: "1157696b7bb941e394c5af530c762b07",
  config_name: "base",
  seed: 4,
  horizon_days: 3,
  periodo_inicio: "2024-10-19",
  periodo_fin: "2024-12-31",
  disclaimers: {
    reproduccion_retrospectiva: true,
    proxy_estadistico_relativo: true,
    utilidad_agronomica_demostrada: false,
  },
  limitaciones: ["Calibración no acreditada para este run."],
  evidencia: {
    package_id: "base-seed4-1157696b7b-v2",
    dataset_name: "melchor_romero_2024_consolidado",
    commit_sha: "2a40ee68c52d2eb5e2040a36b1029f756f9c048a",
    split_date: "2024-10-19",
    training_max_date: "2024-10-15",
    day_convention: "UTC_naive_midnight",
    issuance_assumption: "Supuesto de disponibilidad diaria documentado.",
  },
  regla_etiqueta: {
    variable: "soil_moisture",
    unidad: "m3/m3",
    operador: "less_than",
    umbral: 0.31678178906440735,
    percentil: 20.0,
  },
};

const ORIGINS = ["2024-10-19", "2024-10-20"];

function clockText(isoDate: string) {
  return (_content: string, element: Element | null) =>
    element?.tagName.toLowerCase() === "p" &&
    element?.textContent === `Fecha simulada: ${isoDate}`;
}

function baseMocks() {
  vi.spyOn(api, "getCandidate").mockResolvedValue(CANDIDATE);
  vi.spyOn(api, "listOrigins").mockResolvedValue({
    origins: ORIGINS.map((o) => ({ timestamp_origen: o })),
  });
  vi.spyOn(api, "getHistory").mockResolvedValue({ simulated_date: "2024-10-19", rows: [] });
  vi.spyOn(api, "getFeedback").mockResolvedValue({ timestamp_origen: "2024-10-19", feedback: [] });
}

describe("HistoricalReplayPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("shows an unavailable message when the backend feature is disabled", async () => {
    vi.spyOn(api, "getCandidate").mockRejectedValue(new ReplayNotFoundError("Not Found"));
    vi.spyOn(api, "listOrigins").mockResolvedValue({ origins: [] });

    render(<HistoricalReplayPage />);

    await waitFor(() => screen.getByText(/no está habilitada/i));
  });

  it("selects the first available origin and shows the prediction without future fields", async () => {
    baseMocks();
    vi.spyOn(api, "getPrediction").mockResolvedValue({
      timestamp_origen: "2024-10-19",
      target_timestamp: "2024-10-22",
      experiment_id: "4",
      run_id: "1157696b7bb941e394c5af530c762b07",
      config_name: "base",
      seed: 4,
      horizon_days: 3,
      disclaimers: CANDIDATE.disclaimers,
      y_pred: 0,
    });

    render(<HistoricalReplayPage />);

    await waitFor(() => screen.getByText("No inferior al umbral de humedad (0)"));
    expect(screen.queryByText(/Coincidencia con la predicción/i)).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: /Feedback de demostración/i })).not.toBeInTheDocument();
  });

  it("reveals the observation and the feedback form exactly at the target date", async () => {
    baseMocks();
    vi.spyOn(api, "getPrediction").mockImplementation(async (_origin, simulatedDate) => {
      const base = {
        timestamp_origen: "2024-10-19",
        target_timestamp: "2024-10-22",
        experiment_id: "4",
        run_id: "1157696b7bb941e394c5af530c762b07",
        config_name: "base",
        seed: 4,
        horizon_days: 3,
        disclaimers: CANDIDATE.disclaimers,
        y_pred: 0,
      };
      if (simulatedDate < "2024-10-22") return base;
      return {
        ...base,
        target_observed: true,
        y_true: 1,
        coincide: false,
        medicion_original: { estado: "medida", valor: 0.28 },
      };
    });

    render(<HistoricalReplayPage />);
    await waitFor(() => screen.getByText(clockText("2024-10-19")));

    fireEvent.click(screen.getByText("Avanzar ▶"));
    fireEvent.click(screen.getByText("Avanzar ▶"));
    fireEvent.click(screen.getByText("Avanzar ▶"));

    await waitFor(() => screen.getByText(clockText("2024-10-22")));
    await waitFor(() => screen.getByText(/Coincidencia con la predicción/i));
    expect(screen.getByText("Discrepa")).toBeInTheDocument();
    await waitFor(() => screen.getByRole("heading", { name: /Feedback de demostración/i }));
  });

  it("ignores a late response from a previous simulated date", async () => {
    baseMocks();
    let resolveFirst: (value: api.ReplayPredictionResponse) => void = () => {};
    const firstPromise = new Promise<api.ReplayPredictionResponse>((resolve) => {
      resolveFirst = resolve;
    });
    const predictionSpy = vi
      .spyOn(api, "getPrediction")
      .mockImplementationOnce(() => firstPromise)
      .mockImplementation(async () => ({
        timestamp_origen: "2024-10-19",
        target_timestamp: "2024-10-22",
        experiment_id: "4",
        run_id: "1157696b7bb941e394c5af530c762b07",
        config_name: "base",
        seed: 4,
        horizon_days: 3,
        disclaimers: CANDIDATE.disclaimers,
        y_pred: 0,
      }));

    render(<HistoricalReplayPage />);
    await waitFor(() => expect(predictionSpy).toHaveBeenCalledTimes(1));

    // Avanza el reloj antes de que responda la primera consulta (todavía
    // en vuelo): la segunda consulta (para la nueva fecha) sí resuelve.
    fireEvent.click(screen.getByText("Avanzar ▶"));
    await waitFor(() => expect(predictionSpy).toHaveBeenCalledTimes(2));

    // Ahora "llega tarde" la respuesta del corte anterior (2024-10-19),
    // ya no vigente — no debe reemplazar el estado mostrado para 2024-10-20.
    resolveFirst({
      timestamp_origen: "2024-10-19",
      target_timestamp: "2024-10-22",
      experiment_id: "4",
      run_id: "1157696b7bb941e394c5af530c762b07",
      config_name: "base",
      seed: 4,
      horizon_days: 3,
      disclaimers: CANDIDATE.disclaimers,
      y_pred: 1, // valor distinto, para detectar si contamina
    });

    await waitFor(() => screen.getByText(clockText("2024-10-20")));
    expect(screen.getByText("No inferior al umbral de humedad (0)")).toBeInTheDocument();
  });

  function predictionAt(overrides: Partial<api.ReplayPredictionResponse> = {}): api.ReplayPredictionResponse {
    return {
      timestamp_origen: "2024-10-19",
      target_timestamp: "2024-10-22",
      experiment_id: "4",
      run_id: "1157696b7bb941e394c5af530c762b07",
      config_name: "base",
      seed: 4,
      horizon_days: 3,
      disclaimers: CANDIDATE.disclaimers,
      y_pred: 0,
      target_observed: true,
      y_true: 1,
      coincide: false,
      medicion_original: { estado: "medida", valor: 0.28 },
      ...overrides,
    };
  }

  it("does not show origin A's feedback while origin B's own query is still pending (Paso 4.1 §1)", async () => {
    baseMocks();
    vi.spyOn(api, "getPrediction").mockResolvedValue(predictionAt());
    let resolveFeedbackB: (value: api.ReplayFeedbackListResponse) => void = () => {};
    const feedbackBPromise = new Promise<api.ReplayFeedbackListResponse>((resolve) => {
      resolveFeedbackB = resolve;
    });
    vi.spyOn(api, "getFeedback")
      .mockResolvedValueOnce({
        timestamp_origen: "2024-10-19",
        feedback: [
          {
            timestamp_origen: "2024-10-19",
            estado_validacion: "confirmada",
            etiqueta_corregida: null,
            observacion: "Feedback de A",
            registered_at: "2026-01-01T00:00:00Z",
            simulated_at: "2024-10-22",
          },
        ],
      })
      .mockImplementationOnce(() => feedbackBPromise);

    render(<HistoricalReplayPage />);
    await waitFor(() => screen.getByText(/Feedback de A/));

    fireEvent.change(screen.getByLabelText("Origen de la predicción"), {
      target: { value: "2024-10-20" },
    });

    // Mientras la consulta de feedback de B sigue en vuelo, no debe seguir
    // mostrándose el feedback de A ni un formulario (aislamiento §1).
    await waitFor(() => screen.getByText(/Cargando feedback…/));
    expect(screen.queryByText(/Feedback de A/)).not.toBeInTheDocument();

    resolveFeedbackB({ timestamp_origen: "2024-10-20", feedback: [] });
    await waitFor(() => screen.getByRole("button", { name: /Registrar feedback/i }));
    expect(screen.queryByText(/Feedback de A/)).not.toBeInTheDocument();
  });

  it("does not let a feedback POST started for A populate B after navigating away", async () => {
    baseMocks();
    vi.spyOn(api, "getPrediction").mockResolvedValue(predictionAt());
    vi.spyOn(api, "getFeedback").mockResolvedValue({ timestamp_origen: "2024-10-19", feedback: [] });
    let resolvePost: (value: api.ReplayFeedbackEntry) => void = () => {};
    const postPromise = new Promise<api.ReplayFeedbackEntry>((resolve) => {
      resolvePost = resolve;
    });
    vi.spyOn(api, "createFeedback").mockReturnValue(postPromise);

    render(<HistoricalReplayPage />);
    await waitFor(() => screen.getByRole("button", { name: /Registrar feedback/i }));

    fireEvent.click(screen.getByRole("button", { name: /Registrar feedback/i }));

    // Navega a otro origen antes de que responda el POST de A.
    fireEvent.change(screen.getByLabelText("Origen de la predicción"), {
      target: { value: "2024-10-20" },
    });
    await waitFor(() => screen.getByRole("button", { name: /Registrar feedback/i }));

    resolvePost({
      timestamp_origen: "2024-10-19",
      estado_validacion: "confirmada",
      etiqueta_corregida: null,
      observacion: "Feedback de A tardío",
      registered_at: "2026-01-01T00:00:00Z",
      simulated_at: "2024-10-22",
    });

    // La respuesta tardía del POST de A no debe aparecer en la pantalla de B.
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(screen.queryByText(/Feedback de A tardío/)).not.toBeInTheDocument();
  });

  it("shows the saved feedback entry after a successful POST, replacing the empty state", async () => {
    baseMocks();
    vi.spyOn(api, "getPrediction").mockResolvedValue(predictionAt());
    vi.spyOn(api, "getFeedback").mockResolvedValue({ timestamp_origen: "2024-10-19", feedback: [] });
    vi.spyOn(api, "createFeedback").mockResolvedValue({
      timestamp_origen: "2024-10-19",
      estado_validacion: "confirmada",
      etiqueta_corregida: null,
      observacion: "Feedback recién guardado",
      registered_at: "2026-01-01T00:00:00Z",
      simulated_at: "2024-10-22",
    });

    render(<HistoricalReplayPage />);
    await waitFor(() => screen.getByRole("button", { name: /Registrar feedback/i }));

    fireEvent.click(screen.getByRole("button", { name: /Registrar feedback/i }));

    await waitFor(() => screen.getByText(/Feedback recién guardado/));
    expect(screen.queryByRole("button", { name: /Registrar feedback/i })).not.toBeInTheDocument();
  });

  it("keeps the correct state after out-of-order A→B→A navigation", async () => {
    baseMocks();
    const responses = new Map<string, () => void>();
    vi.spyOn(api, "getPrediction").mockImplementation(
      (origin) =>
        new Promise((resolve) => {
          responses.set(origin, () =>
            resolve(predictionAt({ timestamp_origen: origin, y_pred: origin === "2024-10-19" ? 0 : 1 })),
          );
        }),
    );

    render(<HistoricalReplayPage />);
    await waitFor(() => expect(responses.has("2024-10-19")).toBe(true));

    fireEvent.change(screen.getByLabelText("Origen de la predicción"), {
      target: { value: "2024-10-20" },
    });
    await waitFor(() => expect(responses.has("2024-10-20")).toBe(true));

    fireEvent.change(screen.getByLabelText("Origen de la predicción"), {
      target: { value: "2024-10-19" },
    });

    // Resuelve fuera de orden: primero la última consulta de "19" (la
    // vigente), luego las dos anteriores, ya obsoletas.
    responses.get("2024-10-19")?.();
    await waitFor(() => screen.getByText("No inferior al umbral de humedad (0)"));
    responses.get("2024-10-20")?.();
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(screen.getByText("No inferior al umbral de humedad (0)")).toBeInTheDocument();
  });

  it("shows no future result while a retreat is loading", async () => {
    baseMocks();
    let resolveRetreat: () => void = () => {};
    vi.spyOn(api, "getPrediction").mockImplementation(async (_origin, simulatedDate) => {
      if (simulatedDate === "2024-10-19") {
        return new Promise((resolve) => {
          resolveRetreat = () => resolve(predictionAt({ target_observed: undefined, y_true: undefined }));
        });
      }
      return predictionAt();
    });

    render(<HistoricalReplayPage />);
    await waitFor(() => screen.getByText(clockText("2024-10-19")));

    // Avanza a un corte cuya consulta resuelve de inmediato y revela la
    // observación.
    fireEvent.click(screen.getByText("Avanzar ▶"));
    await waitFor(() => screen.getByText(/Coincidencia con la predicción/i));

    // Retrocede: la nueva consulta (para "2024-10-19") queda en vuelo.
    fireEvent.click(screen.getByText("◀ Retroceder"));

    // Mientras la consulta del retroceso está en vuelo, no debe seguir
    // mostrándose la observación revelada del corte posterior.
    await waitFor(() => screen.getByText(/Cargando predicción…/));
    expect(screen.queryByText(/Coincidencia con la predicción/i)).not.toBeInTheDocument();

    resolveRetreat();
    await waitFor(() => screen.getByText(/todavía no revelada/i));
  });

  it("does not show the feedback form when target_observed is false", async () => {
    baseMocks();
    vi.spyOn(api, "getPrediction").mockResolvedValue(
      predictionAt({ target_observed: false, y_true: undefined, coincide: undefined, medicion_original: undefined }),
    );

    render(<HistoricalReplayPage />);

    await waitFor(() => screen.getByText(/no maduró en este run/i));
    expect(screen.queryByRole("heading", { name: /Feedback de demostración/i })).not.toBeInTheDocument();
  });

  it("distinguishes a history fetch error from an empty history", async () => {
    vi.spyOn(api, "getCandidate").mockResolvedValue(CANDIDATE);
    vi.spyOn(api, "listOrigins").mockResolvedValue({
      origins: ORIGINS.map((o) => ({ timestamp_origen: o })),
    });
    vi.spyOn(api, "getFeedback").mockResolvedValue({ timestamp_origen: "2024-10-19", feedback: [] });
    vi.spyOn(api, "getPrediction").mockResolvedValue(predictionAt({ target_observed: undefined, y_true: undefined }));
    vi.spyOn(api, "getHistory").mockRejectedValue(new Error("500"));

    render(<HistoricalReplayPage />);

    await waitFor(() => screen.getByText(/Error al consultar el historial/i));
    expect(screen.queryByText(/Todavía no hay historial disponible/i)).not.toBeInTheDocument();
  });

  it("distinguishes a feedback fetch error from an empty feedback list, and does not silently enable the form", async () => {
    baseMocks();
    vi.spyOn(api, "getPrediction").mockResolvedValue(predictionAt());
    vi.spyOn(api, "getFeedback").mockRejectedValue(new Error("500"));

    render(<HistoricalReplayPage />);

    await waitFor(() => screen.getByText(/No se pudo consultar el feedback existente/i));
    expect(screen.queryByRole("button", { name: /Registrar feedback/i })).not.toBeInTheDocument();
  });

  it("never renders origin A's prediction/history/feedback under origin B's selection, not even immediately after switching", async () => {
    // A propósito, las promesas de B nunca resuelven en este test: si el
    // guardado de "primer render" dependiera de que el useEffect ya
    // limpió el estado, esto se rompería igual de mal que si dependiera de
    // que la promesa de B ya resolvió. La garantía real (Paso 4.1.1 §1) es
    // que el render filtra por selección vigente, no por si algo ya corrió.
    baseMocks();
    vi.spyOn(api, "getPrediction").mockResolvedValue(predictionAt());
    vi.spyOn(api, "getHistory").mockResolvedValue({
      simulated_date: "2024-10-19",
      rows: [{ fecha: "2024-10-19", estado: "medida", soil_moisture: 0.3 }],
    });
    vi.spyOn(api, "getFeedback").mockResolvedValue({
      timestamp_origen: "2024-10-19",
      feedback: [
        {
          timestamp_origen: "2024-10-19",
          estado_validacion: "confirmada",
          etiqueta_corregida: null,
          observacion: "Feedback de A, no debe verse bajo B",
          registered_at: "2026-01-01T00:00:00Z",
          simulated_at: "2024-10-22",
        },
      ],
    });

    render(<HistoricalReplayPage />);
    await waitFor(() => screen.getByText(/Feedback de A, no debe verse bajo B/));
    await waitFor(() => screen.getByText("Discrepa"));

    // A partir de aquí, las consultas para B quedan colgadas para siempre.
    vi.spyOn(api, "getPrediction").mockReturnValue(new Promise(() => {}));
    vi.spyOn(api, "getHistory").mockReturnValue(new Promise(() => {}));
    vi.spyOn(api, "getFeedback").mockReturnValue(new Promise(() => {}));

    fireEvent.change(screen.getByLabelText("Origen de la predicción"), {
      target: { value: "2024-10-20" },
    });

    // Ningún dato de A puede seguir visible bajo la selección B, en ningún
    // render posterior al cambio (las promesas de B nunca resuelven).
    expect(screen.queryByText(/Feedback de A, no debe verse bajo B/)).not.toBeInTheDocument();
    expect(screen.queryByText("Discrepa")).not.toBeInTheDocument();
    expect(screen.getByText("Cargando predicción…")).toBeInTheDocument();
    expect(screen.getByText("Cargando historial…")).toBeInTheDocument();
    expect(screen.queryByText("Cargando feedback…")).not.toBeInTheDocument(); // aún no revelado bajo B
  });

  it("still shows real data under StrictMode's dev mount→cleanup→mount double-invoke (regression: mountedRef must not latch to false)", async () => {
    // Este proyecto activa StrictMode en `main.tsx`. Una guarda de
    // "sigue montado" que solo pone `mountedRef.current = false` en la
    // limpieza (sin reafirmar `true` en el propio montaje) queda
    // permanentemente en `false` después del doble montaje que React hace
    // a propósito en desarrollo bajo StrictMode — bloqueando para siempre
    // cualquier actualización de estado real, aunque las promesas
    // resuelvan bien. Encontrado verificando el arranque en un navegador
    // real (Paso 4.1.1 §2), no por ningún test previo (ninguno usaba
    // `StrictMode`).
    baseMocks();
    vi.spyOn(api, "getPrediction").mockResolvedValue(predictionAt({ target_observed: undefined, y_true: undefined }));

    render(
      <StrictMode>
        <HistoricalReplayPage />
      </StrictMode>,
    );

    await waitFor(() => screen.getByText("No inferior al umbral de humedad (0)"));
  });
});
