import { fireEvent, render, screen, waitFor } from "@testing-library/react";
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
