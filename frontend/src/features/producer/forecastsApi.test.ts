import { afterEach, describe, expect, it, vi } from "vitest";
import { ProducerV2UnavailableError } from "./catalogApi";
import {
  DemoWriteLockedError,
  ForecastNotFoundError,
  ForecastCursorExpiredError,
  ReviewIdempotencyConflictError,
  ReviewNotOpenError,
  RevisionConflictError,
  alertOutlookSummary,
  displayProbability,
  emitForecasts,
  getForecast,
  listForecasts,
  submitReview,
} from "./forecastsApi";
import type { Forecast, ForecastBatch } from "./forecastsApi";

afterEach(() => vi.unstubAllGlobals());

const forecast: Forecast = {
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

function jsonResponse(status: number, body: unknown) {
  return { ok: status >= 200 && status < 300, status, json: async () => body };
}

describe("listForecasts", () => {
  it("builds the query string from filters and returns the list result", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse(200, { items: [forecast], next_cursor: "c1", pending_total: 3, reviewable_pending_total: 2 }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const result = await listForecasts("sensor-a", { reviewStatus: "pending", horizonDays: 1, limit: 10, cursor: "c0" });
    expect(result.pending_total).toBe(3);
    const url = new URL(fetchMock.mock.calls[0][0]);
    expect(url.pathname).toBe("/api/v2/sensors/sensor-a/forecasts");
    expect(url.searchParams.get("review_status")).toBe("pending");
    expect(url.searchParams.get("horizon_days")).toBe("1");
    expect(url.searchParams.get("limit")).toBe("10");
    expect(url.searchParams.get("cursor")).toBe("c0");
  });

  it("encodes sensor and every optional query without renaming cursors", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse(200, { items: [], next_cursor: null, pending_total: 0, reviewable_pending_total: 0 }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await listForecasts("sensor / á", {
      targetFrom: "2026-01-01",
      targetTo: "2026-01-31",
      horizonDays: 3,
      reviewStatus: "rejected",
      limit: 25,
      cursor: "cursor / á",
    });

    const url = new URL(fetchMock.mock.calls[0][0]);
    expect(url.pathname).toBe("/api/v2/sensors/sensor%20%2F%20%C3%A1/forecasts");
    expect(Object.fromEntries(url.searchParams)).toEqual({
      target_from: "2026-01-01",
      target_to: "2026-01-31",
      horizon_days: "3",
      review_status: "rejected",
      limit: "25",
      cursor: "cursor / á",
    });
  });

  it("treats a bodyless 404 as the v2 facade being unavailable", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 404, json: async () => { throw new Error("no body"); } }));
    await expect(listForecasts("sensor-a")).rejects.toBeInstanceOf(ProducerV2UnavailableError);
  });

  it("uses VITE_PRODUCER_API_BASE_URL, not VITE_API_BASE_URL, when both are configured with different values (-Mode all separation)", async () => {
    vi.stubEnv("VITE_API_BASE_URL", "http://127.0.0.1:8299");
    vi.stubEnv("VITE_PRODUCER_API_BASE_URL", "http://127.0.0.1:8199");
    vi.resetModules();
    const { listForecasts: freshListForecasts } = await import("./forecastsApi");
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse(200, { items: [forecast], next_cursor: null, pending_total: 0, reviewable_pending_total: 0 }),
    );
    vi.stubGlobal("fetch", fetchMock);
    await freshListForecasts("sensor-a");
    const url = new URL(fetchMock.mock.calls[0][0]);
    expect(url.origin).toBe("http://127.0.0.1:8199");
    expect(url.origin).not.toBe("http://127.0.0.1:8299");
    vi.unstubAllEnvs();
    vi.resetModules();
  });
});

describe("getForecast", () => {
  it("returns the forecast when found", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(200, forecast)));
    await expect(getForecast("sensor-a", "fc-1")).resolves.toEqual(forecast);
  });

  it("encodes both resource identifiers and preserves response identity", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(200, forecast));
    vi.stubGlobal("fetch", fetchMock);

    await expect(getForecast("sensor / á", "forecast / ñ")).resolves.toBe(forecast);
    expect(new URL(fetchMock.mock.calls[0][0]).pathname).toBe(
      "/api/v2/sensors/sensor%20%2F%20%C3%A1/forecasts/forecast%20%2F%20%C3%B1",
    );
  });

  it("maps forecast_not_found to ForecastNotFoundError", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(404, { error: { code: "forecast_not_found", message: "no", details: {}, request_id: "r" } }),
      ),
    );
    await expect(getForecast("sensor-a", "fc-x")).rejects.toBeInstanceOf(ForecastNotFoundError);
  });
});

describe("submitReview", () => {
  const request = { requestId: "req-1", expectedRevision: 0, action: "confirm" as const, comment: null };

  it("sends the exact request body the contract expects", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(201, forecast.review));
    vi.stubGlobal("fetch", fetchMock);
    await expect(submitReview("sensor-a", "fc-1", request)).resolves.toBe(forecast.review);
    const [url, init] = fetchMock.mock.calls[0];
    expect(new URL(url).pathname).toBe("/api/v2/sensors/sensor-a/forecasts/fc-1/reviews");
    expect(init.method).toBe("POST");
    expect(init.headers).toEqual({ "Content-Type": "application/json" });
    expect(JSON.parse(init.body)).toEqual({
      request_id: "req-1",
      expected_revision: 0,
      action: "confirm",
      comment: null,
    });
  });

  it("maps review_not_open with its review_open_at detail", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(409, {
          error: { code: "review_not_open", message: "no", details: { review_open_at: "2026-01-02T00:00:00Z" }, request_id: "r" },
        }),
      ),
    );
    const error = await submitReview("sensor-a", "fc-1", request).catch((e) => e);
    expect(error).toBeInstanceOf(ReviewNotOpenError);
    expect((error as ReviewNotOpenError).reviewOpenAt).toBe("2026-01-02T00:00:00Z");
  });

  it("maps revision_conflict with the actual revision", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(409, {
          error: { code: "revision_conflict", message: "no", details: { expected_revision: 0, actual_revision: 1 }, request_id: "r" },
        }),
      ),
    );
    const error = await submitReview("sensor-a", "fc-1", request).catch((e) => e);
    expect(error).toBeInstanceOf(RevisionConflictError);
    expect((error as RevisionConflictError).actualRevision).toBe(1);
  });

  it("maps idempotency_conflict", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse(409, { error: { code: "idempotency_conflict", message: "no", details: {}, request_id: "r" } })),
    );
    await expect(submitReview("sensor-a", "fc-1", request)).rejects.toBeInstanceOf(ReviewIdempotencyConflictError);
  });

  it("maps demo_write_locked", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse(409, { error: { code: "demo_write_locked", message: "no", details: {}, request_id: "r" } })),
    );
    await expect(submitReview("sensor-a", "fc-1", request)).rejects.toBeInstanceOf(DemoWriteLockedError);
  });

  it("maps forecast_not_found on review submission", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse(404, { error: { code: "forecast_not_found", message: "no", details: {}, request_id: "r" } })),
    );
    await expect(submitReview("sensor-a", "fc-x", request)).rejects.toBeInstanceOf(ForecastNotFoundError);
  });

  it("treats a generic 5xx as a plain recoverable error, not a terminal one", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse(503, { error: { code: "storage_unavailable", message: "no disponible", details: {}, request_id: "r" } })),
    );
    const error = await submitReview("sensor-a", "fc-1", request).catch((e) => e);
    expect(error).not.toBeInstanceOf(RevisionConflictError);
    expect(error).not.toBeInstanceOf(DemoWriteLockedError);
    expect((error as Error).message).toBe("no disponible");
  });
});

describe("emitForecasts", () => {
  for (const status of [200, 201]) {
    it(`accepts ${status} while preserving the exact empty body and idempotency header`, async () => {
      const payload = {
        batch_id: "batch-1",
        revision: 1,
        as_of_date: "2026-01-01",
        data_age_days: 0,
        server_today: "2026-01-01",
        slots: [],
        provenance: "real",
        calendar_timezone: "UTC",
      };
      const fetchMock = vi.fn().mockResolvedValue(jsonResponse(status, payload));
      vi.stubGlobal("fetch", fetchMock);

      await expect(emitForecasts("sensor / á", "request-123")).resolves.toBe(payload);
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("/api/v2/sensors/sensor%20%2F%20%C3%A1/forecasts"),
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "Idempotency-Key": "request-123",
          },
          body: "{}",
        },
      );
    });
  }
});

describe("displayProbability", () => {
  it("never renders 0% for a missing probability", () => {
    expect(displayProbability({ ...forecast, display_probability: null })).toBe("Probabilidad no disponible");
  });

  it("renders the published probability as a rounded percentage", () => {
    expect(displayProbability({ ...forecast, display_probability: 0.723 })).toBe("72 %");
  });
});

it("maps the backend invalid_cursor response to a recoverable list restart", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ error: { code: "invalid_cursor", message: "internal details" } }), { status: 422 })));
  await expect(listForecasts("sensor-a", { cursor: "old" })).rejects.toBeInstanceOf(ForecastCursorExpiredError);
});

it("explains an invalid date range without exposing backend terminology", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ error: { code: "invalid_date_range", message: "target_from invalid" } }), { status: 422 })));
  await expect(listForecasts("sensor-a", { targetFrom: "2026-09-10", targetTo: "2026-09-01" })).rejects.toThrow("La fecha inicial debe ser anterior o igual a la fecha final.");
});

describe("alertOutlookSummary", () => {
  function batchWith(slots: ForecastBatch["slots"]): ForecastBatch {
    return {
      batch_id: "b1", revision: 1, as_of_date: "2026-01-05", data_age_days: 0,
      server_today: "2026-01-05", provenance: "real", calendar_timezone: "UTC", slots,
    };
  }

  it("returns null when every horizon is unavailable, never claiming 'no alert'", () => {
    const batch = batchWith([
      { horizon_days: 1, target_date: "2026-01-06", status: "unavailable", reason_code: "model_not_available" },
      { horizon_days: 2, target_date: "2026-01-07", status: "unavailable", reason_code: "model_not_available" },
      { horizon_days: 3, target_date: "2026-01-08", status: "unavailable", reason_code: "model_not_available" },
    ]);
    expect(alertOutlookSummary(batch)).toBeNull();
  });

  it("collects only the target dates the backend already decided alert=true, never recomputing", () => {
    const batch = batchWith([
      { ...forecast, status: "available", horizon_days: 1, target_date: "2026-01-06", alert: true, forecast_id: "fc-1" },
      { ...forecast, status: "available", horizon_days: 2, target_date: "2026-01-07", alert: false, forecast_id: "fc-2" },
      { horizon_days: 3, target_date: "2026-01-08", status: "unavailable", reason_code: "model_not_available" },
    ]);
    const summary = alertOutlookSummary(batch);
    expect(summary?.alert).toBe(true);
    expect(summary?.days).toEqual(["6 de ene de 2026"]);
  });

  it("reports no alert only when at least one horizon is available and none alerted", () => {
    const batch = batchWith([
      { ...forecast, status: "available", horizon_days: 1, target_date: "2026-01-06", alert: false, forecast_id: "fc-1" },
    ]);
    const summary = alertOutlookSummary(batch);
    expect(summary).toEqual({ alert: false, days: [] });
  });
});
