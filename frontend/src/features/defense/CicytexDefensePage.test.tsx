import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { CicytexDefensePage } from "./CicytexDefensePage";
import * as api from "./cicytexApi";

const CATALOG: api.CicytexCatalog = {
  sensors: ["CP1_S1"],
  emission_dates: ["2023-07-06"],
  emission_dates_by_horizon: { "1": ["2023-07-06"] },
  horizons: [1],
  first_legitimate_emission: "2023-07-06",
  last_observation: "2023-07-25",
};

const METRIC = {
  n: 0,
  tp: 0,
  tn: 0,
  fp: 0,
  fn: 0,
  mcc: null,
  precision: null,
  recall: null,
  f1: null,
  coverage: 0,
};

function session(overrides: Partial<api.CicytexSession> = {}): api.CicytexSession {
  return {
    session_id: "session-1",
    sensor_id: "CP1_S1",
    emission_date: "2023-07-06",
    horizon_days: 1,
    revealed_through: "2023-07-06",
    threshold: 0.25,
    proxy_notice: "proxy",
    predictions: [
      {
        method: "ensemble",
        score: 0.4,
        alert: false,
        target_date: "2023-07-07",
        observed_soil_moisture: null,
        observed_label: null,
        outcome: null,
      },
    ],
    readings: [{ date: "2023-07-06", soil_moisture: 0.3 }],
    metrics: {
      ensemble: METRIC,
      logistic_regression: METRIC,
      random_forest: METRIC,
      hist_gradient_boosting_classifier: METRIC,
      persistence: METRIC,
    },
    feedback: null,
    can_advance: true,
    ...overrides,
  };
}

describe("CicytexDefensePage generated nullability", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(api, "getCicytexCatalog").mockResolvedValue(CATALOG);
  });

  it("keeps future observations and null feedback hidden without inventing values", async () => {
    vi.spyOn(api, "createCicytexSession").mockResolvedValue(session());
    render(<CicytexDefensePage />);
    await waitFor(() => expect(api.getCicytexCatalog).toHaveBeenCalledOnce());

    fireEvent.click(screen.getByRole("button", { name: "Abrir emisión congelada" }));

    await waitFor(() => screen.getByText(/La realidad permanece oculta/i));
    expect(screen.getByText("Oculto hasta avanzar")).toBeInTheDocument();
    expect(screen.getByText("Pendiente")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: /Feedback humano/i })).not.toBeInTheDocument();
  });

  it("renders the session when every generated metric slot is explicitly null", async () => {
    vi.spyOn(api, "createCicytexSession").mockResolvedValue(
      session({
        metrics: {
          ensemble: null,
          logistic_regression: null,
          random_forest: null,
          hist_gradient_boosting_classifier: null,
          persistence: null,
        },
      }),
    );
    render(<CicytexDefensePage />);
    await waitFor(() => expect(api.getCicytexCatalog).toHaveBeenCalledOnce());

    fireEvent.click(screen.getByRole("button", { name: "Abrir emisión congelada" }));

    await waitFor(() =>
      expect(
        screen.getByRole("heading", { name: "Comparación acumulada revelada" }),
      ).toBeInTheDocument(),
    );
  });
});

describe("CicytexDefensePage operation robustness", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  function deferred<T>() {
    let resolve!: (value: T) => void;
    const promise = new Promise<T>((r) => {
      resolve = r;
    });
    return { promise, resolve };
  }

  it("offers a retry when the catalog fails and recovers on success", async () => {
    const catalog = vi
      .spyOn(api, "getCicytexCatalog")
      .mockRejectedValueOnce(new Error("sin conexión"))
      .mockResolvedValue(CATALOG);
    render(<CicytexDefensePage />);

    await screen.findByRole("alert");
    fireEvent.click(screen.getByRole("button", { name: "Reintentar" }));

    await waitFor(() => expect(catalog).toHaveBeenCalledTimes(2));
    await waitFor(() => expect(screen.queryByRole("alert")).not.toBeInTheDocument());
    expect(screen.getByRole("button", { name: "Abrir emisión congelada" })).toBeEnabled();
  });

  it("ignores a late session response after the selection changed", async () => {
    vi.spyOn(api, "getCicytexCatalog").mockResolvedValue({
      ...CATALOG,
      sensors: ["CP1_S1", "CP1_S2"],
    });
    const pending = deferred<api.CicytexSession>();
    vi.spyOn(api, "createCicytexSession").mockReturnValue(pending.promise);
    render(<CicytexDefensePage />);
    await waitFor(() => expect(api.getCicytexCatalog).toHaveBeenCalledOnce());

    fireEvent.click(screen.getByRole("button", { name: "Abrir emisión congelada" }));
    fireEvent.change(screen.getByLabelText("Sonda"), { target: { value: "CP1_S2" } });
    await act(async () => {
      pending.resolve(session({ sensor_id: "CP1_S1" }));
    });

    expect(screen.queryByText(/Decisión de la arquitectura/i)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Abrir emisión congelada" })).toBeEnabled();
  });

  it("submits feedback once even if the form is submitted twice", async () => {
    vi.spyOn(api, "getCicytexCatalog").mockResolvedValue(CATALOG);
    vi.spyOn(api, "createCicytexSession").mockResolvedValue(
      session({
        predictions: [
          {
            method: "ensemble",
            score: 0.4,
            alert: false,
            target_date: "2023-07-07",
            observed_soil_moisture: 0.3,
            observed_label: 0,
            outcome: "VN",
          },
        ],
      }),
    );
    const pending = deferred<api.ReplayFeedback>();
    const submit = vi.spyOn(api, "submitCicytexFeedback").mockReturnValue(pending.promise);
    render(<CicytexDefensePage />);
    await waitFor(() => expect(api.getCicytexCatalog).toHaveBeenCalledOnce());
    fireEvent.click(screen.getByRole("button", { name: "Abrir emisión congelada" }));
    const form = (await screen.findByRole("button", { name: "Registrar feedback" })).closest("form")!;

    fireEvent.submit(form);
    fireEvent.submit(form);

    expect(submit).toHaveBeenCalledTimes(1);
  });

  it("shows a loading state until the catalog arrives", async () => {
    const pending = deferred<api.CicytexCatalog>();
    vi.spyOn(api, "getCicytexCatalog").mockReturnValue(pending.promise);
    render(<CicytexDefensePage />);

    expect(screen.getByRole("status")).toHaveTextContent(/Cargando catálogo/i);
    await act(async () => {
      pending.resolve(CATALOG);
    });
    expect(screen.queryByText(/Cargando catálogo/i)).not.toBeInTheDocument();
  });
});

describe("CicytexDefensePage feedback draft isolation", () => {
  const REVEALED: api.CicytexSession["predictions"] = [
    {
      method: "ensemble",
      score: 0.4,
      alert: false,
      target_date: "2023-07-07",
      observed_soil_moisture: 0.3,
      observed_label: 0,
      outcome: "VN",
    },
  ];

  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(api, "getCicytexCatalog").mockResolvedValue({
      ...CATALOG,
      sensors: ["CP1_S1", "CP1_S2"],
    });
  });

  async function openAndDraft(note: string) {
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Abrir emisión congelada" })).toBeEnabled(),
    );
    fireEvent.click(screen.getByRole("button", { name: "Abrir emisión congelada" }));
    fireEvent.click(await screen.findByLabelText(/No coincide/));
    fireEvent.change(screen.getByLabelText(/Observación opcional/), { target: { value: note } });
  }

  it("starts a clean draft after the sensor changes and a new session opens", async () => {
    vi.spyOn(api, "createCicytexSession")
      .mockResolvedValueOnce(session({ session_id: "s1", predictions: REVEALED }))
      .mockResolvedValueOnce(session({ session_id: "s2", sensor_id: "CP1_S2", predictions: REVEALED }));
    render(<CicytexDefensePage />);
    await openAndDraft("nota del contexto anterior");

    fireEvent.change(screen.getByLabelText("Sonda"), { target: { value: "CP1_S2" } });
    fireEvent.click(screen.getByRole("button", { name: "Abrir emisión congelada" }));
    await screen.findByRole("button", { name: "Registrar feedback" });

    expect(screen.getByLabelText(/Observación opcional/)).toHaveValue("");
    expect(screen.getByLabelText(/Sí, coincide/)).toBeChecked();
  });

  it("clears the draft when the session is reset", async () => {
    vi.spyOn(api, "createCicytexSession").mockResolvedValue(session({ predictions: REVEALED }));
    vi.spyOn(api, "resetCicytexSession").mockResolvedValue(session({ predictions: REVEALED }));
    render(<CicytexDefensePage />);
    await openAndDraft("nota previa al reinicio");

    fireEvent.click(screen.getByRole("button", { name: "Reiniciar" }));
    await waitFor(() => expect(api.resetCicytexSession).toHaveBeenCalled());

    await waitFor(() => expect(screen.getByLabelText(/Observación opcional/)).toHaveValue(""));
    expect(screen.getByLabelText(/Sí, coincide/)).toBeChecked();
  });

  it("clears the draft when another session is opened for the same selection", async () => {
    vi.spyOn(api, "createCicytexSession")
      .mockResolvedValueOnce(session({ session_id: "s1", predictions: REVEALED }))
      .mockResolvedValueOnce(session({ session_id: "s2", predictions: REVEALED }));
    render(<CicytexDefensePage />);
    await openAndDraft("nota de la sesión 1");

    fireEvent.click(screen.getByRole("button", { name: "Abrir emisión congelada" }));
    await waitFor(() => expect(api.createCicytexSession).toHaveBeenCalledTimes(2));

    await waitFor(() => expect(screen.getByLabelText(/Observación opcional/)).toHaveValue(""));
  });

  it("does not apply a late feedback response to a different session or leak its draft", async () => {
    vi.spyOn(api, "createCicytexSession")
      .mockResolvedValueOnce(session({ session_id: "s1", predictions: REVEALED }))
      .mockResolvedValueOnce(session({ session_id: "s2", sensor_id: "CP1_S2", predictions: REVEALED }));
    let resolveLate!: (value: api.ReplayFeedback) => void;
    vi.spyOn(api, "submitCicytexFeedback").mockReturnValue(
      new Promise((resolve) => {
        resolveLate = resolve;
      }),
    );
    render(<CicytexDefensePage />);
    await openAndDraft("nota que se envía tarde");
    fireEvent.click(screen.getByRole("button", { name: "Registrar feedback" }));

    fireEvent.change(screen.getByLabelText("Sonda"), { target: { value: "CP1_S2" } });
    fireEvent.click(screen.getByRole("button", { name: "Abrir emisión congelada" }));
    await screen.findByRole("button", { name: "Registrar feedback" });
    await act(async () => {
      resolveLate({
        estado_validacion: "rechazada",
        observacion: "nota que se envía tarde",
        registered_at: "2023-07-07T00:00:00Z",
      } as api.ReplayFeedback);
    });

    expect(screen.queryByText(/Feedback registrado/)).not.toBeInTheDocument();
    expect(screen.getByLabelText(/Observación opcional/)).toHaveValue("");
  });

  it("clears the draft on a selection change even if the backend repeats the session id", async () => {
    vi.spyOn(api, "createCicytexSession")
      .mockResolvedValueOnce(session({ session_id: "same", predictions: REVEALED }))
      .mockResolvedValueOnce(session({ session_id: "same", sensor_id: "CP1_S2", predictions: REVEALED }));
    render(<CicytexDefensePage />);
    await openAndDraft("nota con id repetido");

    fireEvent.change(screen.getByLabelText("Sonda"), { target: { value: "CP1_S2" } });
    fireEvent.click(screen.getByRole("button", { name: "Abrir emisión congelada" }));
    await waitFor(() => expect(api.createCicytexSession).toHaveBeenCalledTimes(2));

    await waitFor(() => expect(screen.getByLabelText(/Observación opcional/)).toHaveValue(""));
  });

  it("keeps the draft when advancing the clock and when submitting fails", async () => {
    vi.spyOn(api, "createCicytexSession").mockResolvedValue(session({ predictions: REVEALED }));
    vi.spyOn(api, "advanceCicytexSession").mockResolvedValue(session({ predictions: REVEALED }));
    vi.spyOn(api, "submitCicytexFeedback").mockRejectedValue(new Error("sin red"));
    render(<CicytexDefensePage />);
    await openAndDraft("nota que debe sobrevivir");

    fireEvent.click(screen.getByRole("button", { name: "Día siguiente" }));
    await waitFor(() => expect(api.advanceCicytexSession).toHaveBeenCalled());
    fireEvent.click(await screen.findByRole("button", { name: "Registrar feedback" }));
    await screen.findByRole("alert");

    expect(screen.getByLabelText(/Observación opcional/)).toHaveValue("nota que debe sobrevivir");
    expect(screen.getByLabelText(/No coincide/)).toBeChecked();
  });
});

describe("CicytexDefensePage visual journey", () => {
  const READINGS = [
    { date: "2023-07-04", soil_moisture: 0.31 },
    { date: "2023-07-05", soil_moisture: 0.29 },
    { date: "2023-07-06", soil_moisture: 0.27 },
  ];

  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(api, "getCicytexCatalog").mockResolvedValue(CATALOG);
  });

  async function open(next: api.CicytexSession) {
    vi.spyOn(api, "createCicytexSession").mockResolvedValue(next);
    render(<CicytexDefensePage />);
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Abrir emisión congelada" })).toBeEnabled(),
    );
    fireEvent.click(screen.getByRole("button", { name: "Abrir emisión congelada" }));
    await screen.findByText(/Decisión de la arquitectura/i);
  }

  it("states the last revealed observation against P20 as text, without future data", async () => {
    await open(session({ readings: READINGS, threshold: 0.25, revealed_through: "2023-07-06" }));

    const summary = screen.getByTestId("moisture-summary");
    expect(summary).toHaveTextContent("0.270");
    expect(summary).toHaveTextContent("2023-07-06");
    expect(summary).toHaveTextContent(/por encima del P20/i);
    expect(summary).not.toHaveTextContent("2023-07-07");
  });

  it("labels the chart axes with the revealed range", async () => {
    await open(session({ readings: READINGS, threshold: 0.25 }));

    const chart = screen.getByRole("img", { name: /Humedad revelada/i });
    expect(chart).toHaveTextContent("2023-07-04");
    expect(chart).toHaveTextContent("2023-07-06");
    expect(chart).toHaveTextContent(/m³\/m³/);
  });

  it("explains an empty cumulative comparison instead of showing a bare table", async () => {
    await open(session({ readings: READINGS }));

    expect(screen.getByText(/Todavía no hay objetivos revelados/i)).toBeInTheDocument();
  });

  it("puts the primary action 'Día siguiente' with the decision and keeps Reiniciar secondary", async () => {
    await open(session({ readings: READINGS }));

    const verdict = screen.getByText(/Decisión de la arquitectura/i).closest("section")!;
    expect(within(verdict).getByRole("button", { name: "Día siguiente" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reiniciar" })).toHaveClass("cy-secondary");
  });

  it("offers method details as progressive disclosure, open by default", async () => {
    await open(session({ readings: READINGS }));

    const details = screen.getByText("Detalle por método").closest("details")!;
    expect(details).toHaveAttribute("open");
  });
});
