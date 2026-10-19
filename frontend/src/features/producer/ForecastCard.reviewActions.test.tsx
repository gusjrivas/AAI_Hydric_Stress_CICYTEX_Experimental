import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { readFileSync } from "node:fs";
import { ForecastCard } from "./ForecastCard";
import * as forecastsApi from "./forecastsApi";
import type { Forecast, ForecastReview } from "./forecastsApi";

const css = readFileSync("src/features/producer/ForecastsSection.css", "utf-8");

const baseForecast: Forecast = {
  forecast_id: "fc-1",
  sensor_id: "sensor-a",
  batch_id: "batch-1",
  as_of_date: "2026-01-01",
  horizon_days: 1,
  target_date: "2026-01-02",
  contract_version: "producer_daily_h123_v1",
  issued_at: "2026-01-01T00:05:00Z",
  snapshot_id: "snap-1",
  alert: true,
  score: 0.72,
  score_kind: "calibrated_probability",
  display_probability: 0.72,
  probability_status: "development_assessed",
  probability_reason_code: null,
  decision_threshold: 0.5,
  event_threshold: { variable: "soil_moisture", value: 0.18, unit: "m3/m3", comparison: "lt" },
  model_reference: {
    model_version: "v1",
    horizon_days: 1,
    contract_version: "producer_daily_h123_v1",
    trained_through: "2025-12-31",
    calibration_version: "cal-1",
    assessment_reference: "assessment-1",
  },
  review: {
    status: "pending",
    revision: 0,
    review_open_at: "2026-01-02T00:00:00Z",
    reviewable: true,
    blocked_reason: null,
    latest_review: null,
    training_eligibility: "no_review",
    applied_review_references: [],
  },
  ensemble: null,
};

const savedReview: ForecastReview = {
  ...baseForecast.review,
  status: "confirmed",
  revision: 1,
  latest_review: {
    review_id: "rev-1",
    request_id: "req-x",
    revision: 1,
    forecast_id: "fc-1",
    action: "confirm",
    observed_label: true,
    comment: null,
    reviewed_at: "2026-01-02T10:00:00Z",
  },
};

function choices() {
  return {
    confirm: screen.getByRole("button", { name: /confirmar resultado/i }),
    reject: screen.getByRole("button", { name: /rechazar resultado/i }),
  };
}

describe("ForecastCard review choices (equal weight, no induced answer)", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("gives Confirmar and Rechazar the same class, with no primary variant, in a stable order", () => {
    render(<ForecastCard sensorId="sensor-a" forecast={baseForecast} />);
    const { confirm, reject } = choices();
    expect(confirm.className).not.toBe("");
    expect(confirm.className).toBe(reject.className);
    expect(`${confirm.className} ${reject.className}`).not.toMatch(/primary|principal|danger|cta/i);
    expect(confirm.compareDocumentPosition(reject) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("describes both choices with the same explanation element", () => {
    render(<ForecastCard sensorId="sensor-a" forecast={baseForecast} />);
    const { confirm, reject } = choices();
    const id = confirm.getAttribute("aria-describedby");
    expect(id).toBeTruthy();
    expect(reject.getAttribute("aria-describedby")).toBe(id);
    expect(document.getElementById(id as string)?.textContent).toMatch(/confirmar|rechazar/i);
  });

  it("preselects nothing and moves no focus on render", () => {
    render(<ForecastCard sensorId="sensor-a" forecast={baseForecast} />);
    const { confirm, reject } = choices();
    expect(document.activeElement).toBe(document.body);
    for (const button of [confirm, reject]) {
      expect(button).not.toHaveAttribute("aria-pressed", "true");
      expect(button).not.toHaveAttribute("autofocus");
    }
    expect(screen.queryByRole("button", { name: /guardar opinión/i })).not.toBeInTheDocument();
  });

  it("reaches both choices with Tab and activates each with Enter or Space", async () => {
    const user = userEvent.setup();
    const { unmount } = render(<ForecastCard sensorId="sensor-a" forecast={baseForecast} />);
    const reached: string[] = [];
    for (let i = 0; i < 6; i += 1) {
      await user.tab();
      reached.push(document.activeElement?.textContent ?? "");
    }
    expect(reached.some((text) => /^confirmar resultado$/i.test(text))).toBe(true);
    expect(reached.some((text) => /^rechazar resultado$/i.test(text))).toBe(true);
    choices().confirm.focus();
    await user.keyboard("{Enter}");
    expect(screen.getByRole("button", { name: /guardar opinión/i })).toBeInTheDocument();
    unmount();

    render(<ForecastCard sensorId="sensor-a" forecast={baseForecast} />);
    choices().reject.focus();
    await user.keyboard(" ");
    expect(screen.getByText(/^No, el suelo no mostró falta de agua/i)).toBeInTheDocument();
  });

  it("guarantees a 44px touch target for both choices at <=600px", () => {
    const media = css.match(/@media\s*\(max-width:\s*600px\)\s*\{([\s\S]*?\})\s*\}/);
    expect(media).not.toBeNull();
    expect(media?.[1]).toMatch(/\.forecast-card-choice[^{]*\{[^}]*min-height:\s*44px/);
  });

  it("does not style one choice differently from the other in CSS", () => {
    expect(css).not.toMatch(/forecast-card-choice[^{]*(:first-child|:last-child|:nth-child)/);
  });
});

describe("ForecastCard review submission safety", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("sends a single POST on repeated clicks or submits and disables both actions while pending", async () => {
    let resolve!: (value: ForecastReview) => void;
    const spy = vi.spyOn(forecastsApi, "submitReview").mockImplementation(
      () => new Promise<ForecastReview>((r) => { resolve = r; }),
    );
    render(<ForecastCard sensorId="sensor-a" forecast={baseForecast} />);
    await userEvent.click(choices().confirm);
    const save = screen.getByRole("button", { name: /guardar opinión/i });
    fireEvent.click(save);
    fireEvent.click(save);
    const form = save.closest("form") as HTMLFormElement;
    fireEvent.submit(form);
    fireEvent.submit(form);
    expect(spy).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("button", { name: /guardando/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /cancelar/i })).toBeDisabled();
    resolve(savedReview);
    await screen.findByText(/tu opinión quedó guardada/i);
    expect(spy).toHaveBeenCalledTimes(1);
  });

  it("keeps focus on a stable status element when the submit button gets disabled and after saving", async () => {
    let resolve!: (value: ForecastReview) => void;
    vi.spyOn(forecastsApi, "submitReview").mockImplementation(
      () => new Promise<ForecastReview>((r) => { resolve = r; }),
    );
    const user = userEvent.setup();
    render(<ForecastCard sensorId="sensor-a" forecast={baseForecast} />);
    await user.click(choices().confirm);
    await user.click(screen.getByRole("button", { name: /guardar opinión/i }));
    const pendingStatus = document.activeElement as HTMLElement;
    expect(pendingStatus).not.toBe(document.body);
    expect(pendingStatus).toHaveAttribute("role", "status");
    expect(pendingStatus).toHaveAttribute("tabindex", "-1");
    resolve(savedReview);
    await screen.findByText(/tu opinión quedó guardada/i);
    await waitFor(() => {
      expect(document.activeElement).toHaveAttribute("role", "status");
      expect(document.activeElement).toHaveTextContent(/tu opinión quedó guardada/i);
    });
  });

  it("blocks a second submit dispatched in the same tick, before React flushes state (synchronous guard)", async () => {
    const spy = vi.spyOn(forecastsApi, "submitReview").mockImplementation(() => new Promise<ForecastReview>(() => {}));
    render(<ForecastCard sensorId="sensor-a" forecast={baseForecast} />);
    await userEvent.click(choices().confirm);
    const form = screen.getByRole("button", { name: /guardar opinión/i }).closest("form") as HTMLFormElement;
    act(() => {
      form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
      form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    });
    expect(spy).toHaveBeenCalledTimes(1);
  });

  describe("focus stays on a stable, meaningful element on error paths", () => {
    async function submitWith(error: Error, props: Partial<React.ComponentProps<typeof ForecastCard>> = {}) {
      vi.spyOn(forecastsApi, "submitReview").mockRejectedValue(error);
      const user = userEvent.setup();
      render(<ForecastCard sensorId="sensor-a" forecast={baseForecast} {...props} />);
      await user.click(choices().confirm);
      await user.click(screen.getByRole("button", { name: /guardar opinión/i }));
    }
    function expectFocusedText(text: RegExp) {
      return waitFor(() => {
        expect(document.activeElement).not.toBe(document.body);
        expect(document.activeElement).toHaveAttribute("tabindex", "-1");
        expect(document.activeElement).toHaveTextContent(text);
      });
    }

    it("revision conflict", async () => {
      await submitWith(new forecastsApi.RevisionConflictError(1), {
        refetchFn: async () => ({ ...baseForecast, review: savedReview }),
      });
      await expectFocusedText(/ya estás viendo el resultado actualizado/i);
    });

    it("idempotency conflict", async () => {
      await submitWith(new forecastsApi.ReviewIdempotencyConflictError());
      await expectFocusedText(/ya se había usado con otro contenido/i);
    });

    it("demo write locked", async () => {
      await submitWith(new forecastsApi.DemoWriteLockedError());
      await expectFocusedText(/demostración/i);
    });

    it("review not open", async () => {
      await submitWith(new forecastsApi.ReviewNotOpenError(null));
      await expectFocusedText(/todavía no se puede revisar/i);
    });

    it("forecast not found", async () => {
      await submitWith(new forecastsApi.ForecastNotFoundError());
      await expectFocusedText(/no se encontró ese pronóstico/i);
    });

    it("target observation blocked (form stays mounted)", async () => {
      await submitWith(new forecastsApi.TargetObservationBlockedError("review_not_open"));
      await waitFor(() => {
        expect(document.activeElement).not.toBe(document.body);
        expect(document.activeElement).toHaveAttribute("tabindex", "-1");
        expect(document.activeElement).not.toHaveTextContent(/^$/);
      });
    });

    it("network error focuses the alert, not an empty status", async () => {
      await submitWith(new Error("Sin conexión"));
      await waitFor(() => {
        expect(document.activeElement).toHaveAttribute("role", "alert");
        expect(document.activeElement).toHaveTextContent(/sin conexión/i);
        expect(document.activeElement).toHaveAttribute("tabindex", "-1");
      });
    });
  });

  it("returns focus to a stable element when the form is cancelled", async () => {
    const user = userEvent.setup();
    render(<ForecastCard sensorId="sensor-a" forecast={baseForecast} />);
    await user.click(choices().reject);
    await user.click(screen.getByRole("button", { name: /cancelar/i }));
    expect(document.activeElement).not.toBe(document.body);
    expect(document.activeElement).toHaveAttribute("tabindex", "-1");
    expect(choices().confirm).not.toHaveFocus();
    expect(choices().reject).not.toHaveFocus();
  });
});
