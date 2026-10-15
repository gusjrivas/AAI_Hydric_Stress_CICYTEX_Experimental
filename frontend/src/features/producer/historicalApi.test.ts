import { afterEach, describe, expect, it, vi } from "vitest";
import { ProducerV2UnavailableError } from "./catalogApi";
import { PRODUCER_API_BASE_URL } from "../../api/baseUrl";
import {
  DemoWriteLockedError,
  ForecastNotFoundError,
  ReviewIdempotencyConflictError,
  ReviewNotOpenError,
  RevisionConflictError,
} from "./forecastsApi";
import {
  BatchNotPreparedError,
  ForecastNotVisibleAtThisHistoricalDateError,
  InvalidRevealWindowError,
  getHistoricalForecastBatch,
  getHistoricalReadings,
  submitHistoricalReview,
} from "./historicalApi";

afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
  vi.resetModules();
});

describe("getHistoricalForecastBatch", () => {
  it("selects by as_of_date and forwards revealed_through as a separate query param, never merging the two dates", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ ok: true }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    await getHistoricalForecastBatch("sensor-a", "2023-06-13", "2023-06-20");
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/historical/2023-06-13/forecasts?revealed_through=2023-06-20"),
    );
  });

  it("encodes the sensor while keeping emission and reveal clocks distinct and read-only", async () => {
    const payload = { batch_id: "b-1" };
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(payload), { status: 200 }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      getHistoricalForecastBatch("sensor / á", "2023-06-13", "2023-06-20"),
    ).resolves.toEqual(payload);
    expect(fetchMock).toHaveBeenCalledWith(
      `${PRODUCER_API_BASE_URL}/api/v2/sensors/sensor%20%2F%20%C3%A1/historical/2023-06-13/forecasts?revealed_through=2023-06-20`,
    );
    expect(fetchMock.mock.calls[0]).toHaveLength(1);
  });

  it("omits revealed_through when not provided", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ ok: true }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    await getHistoricalForecastBatch("sensor-a", "2023-06-13");
    expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining("/historical/2023-06-13/forecasts"));
    expect(fetchMock).not.toHaveBeenCalledWith(expect.stringContaining("revealed_through"));
  });

  it("uses the producer host when producer and general API URLs differ", async () => {
    vi.stubEnv("VITE_API_BASE_URL", "http://127.0.0.1:8299");
    vi.stubEnv("VITE_PRODUCER_API_BASE_URL", "http://127.0.0.1:8199");
    vi.resetModules();
    const { getHistoricalForecastBatch: freshGet } = await import("./historicalApi");
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ batch_id: "b-1" }), { status: 200 }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await freshGet("sensor-a", "2023-06-13");

    expect(new URL(fetchMock.mock.calls[0][0]).origin).toBe("http://127.0.0.1:8199");
  });

  it("distinguishes a date never emitted from a generic error", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ error: { code: "batch_not_prepared", message: "x" } }), { status: 404 }),
      ),
    );
    await expect(getHistoricalForecastBatch("sensor-a", "2023-01-01")).rejects.toBeInstanceOf(BatchNotPreparedError);
  });

  it("surfaces an unavailable producer v2 facade as its own error", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 404 })));
    await expect(getHistoricalForecastBatch("sensor-a", "2023-01-01")).rejects.toBeInstanceOf(ProducerV2UnavailableError);
  });

  it("rejects a reveal window earlier than the emission with a dedicated error", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ error: { code: "invalid_reveal_window", message: "x" } }), { status: 422 }),
      ),
    );
    await expect(getHistoricalForecastBatch("sensor-a", "2023-06-14", "2023-06-13")).rejects.toBeInstanceOf(
      InvalidRevealWindowError,
    );
  });
});

describe("getHistoricalReadings", () => {
  it("reveals through the walked-forward clock, never a client-supplied end date", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ ok: true }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    await getHistoricalReadings("sensor-a", "2023-06-20", 10);
    expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining("/historical/2023-06-20/readings?days=10"));
  });

  it("uses the stable default 30-day window and a GET without request options", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ input_roles: [] }), { status: 200 }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await getHistoricalReadings("sensor / á", "2023-06-20");

    expect(fetchMock).toHaveBeenCalledWith(
      `${PRODUCER_API_BASE_URL}/api/v2/sensors/sensor%20%2F%20%C3%A1/historical/2023-06-20/readings?days=30`,
    );
    expect(fetchMock.mock.calls[0]).toHaveLength(1);
  });

  it("preserves structured errors and the stable non-JSON fallback", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(
          new Response(JSON.stringify({ error: { message: "lecturas históricas ocupadas" } }), {
            status: 503,
          }),
        )
        .mockResolvedValueOnce(
          new Response("not JSON", { status: 500, headers: { "Content-Type": "text/plain" } }),
        ),
    );

    await expect(getHistoricalReadings("sensor-a", "2023-06-20")).rejects.toThrow(
      "lecturas históricas ocupadas",
    );
    await expect(getHistoricalReadings("sensor-a", "2023-06-20")).rejects.toThrow(
      "No se pudieron cargar las mediciones históricas. Intentá nuevamente.",
    );
  });
});

describe("submitHistoricalReview", () => {
  it("posts to the historical route gated by the walked-forward clock", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ status: "confirmed" }), { status: 201 }));
    vi.stubGlobal("fetch", fetchMock);
    const result = await submitHistoricalReview("sensor / á", "2023-06-20", "fc / ñ", {
      requestId: "req-1",
      expectedRevision: 0,
      action: "confirm",
      comment: null,
    });
    expect(result).toEqual({ status: "confirmed" });
    expect(fetchMock).toHaveBeenCalledWith(
      `${PRODUCER_API_BASE_URL}/api/v2/sensors/sensor%20%2F%20%C3%A1/historical/2023-06-20/forecasts/fc%20%2F%20%C3%B1/reviews`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          request_id: "req-1",
          expected_revision: 0,
          action: "confirm",
          comment: null,
        }),
      },
    );
  });

  it("refuses to review a later emission's forecast from an earlier historical date with a dedicated error", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({ error: { code: "forecast_not_visible_at_this_historical_date", message: "x" } }),
          { status: 404 },
        ),
      ),
    );
    await expect(
      submitHistoricalReview("sensor-a", "2023-06-13", "fc-later", {
        requestId: "req-1",
        expectedRevision: 0,
        action: "confirm",
        comment: null,
      }),
    ).rejects.toBeInstanceOf(ForecastNotVisibleAtThisHistoricalDateError);
  });
});

describe("submitHistoricalReview: motivos de observación objetivo", () => {
  it.each(["target_observation_imputed", "target_observation_missing", "target_observation_unverified"])(
    "maps the 409 %s to TargetObservationBlockedError",
    async (code) => {
      vi.spyOn(globalThis, "fetch").mockResolvedValue(
        new Response(JSON.stringify({ error: { code, message: "x", details: {}, request_id: "r" } }), { status: 409 }),
      );
      await expect(
        submitHistoricalReview("melchor-romero-demo", "2024-10-27", "fc-1", {
          requestId: "r1",
          expectedRevision: 0,
          action: "confirm",
          comment: null,
        }),
      ).rejects.toMatchObject({ name: "TargetObservationBlockedError", reason: code });
    },
  );
});

describe("submitHistoricalReview: established error details", () => {
  const request = {
    requestId: "r1",
    expectedRevision: 0,
    action: "confirm" as const,
    comment: null,
  };

  it("preserves review opening and actual revision details", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(
          new Response(
            JSON.stringify({ error: { code: "review_not_open", details: { review_open_at: "2026-01-02T00:00:00Z" } } }),
            { status: 409 },
          ),
        )
        .mockResolvedValueOnce(
          new Response(
            JSON.stringify({ error: { code: "revision_conflict", details: { actual_revision: 4 } } }),
            { status: 409 },
          ),
        ),
    );

    const opening = await submitHistoricalReview("s", "2026-01-02", "f", request).catch((error) => error);
    expect(opening).toBeInstanceOf(ReviewNotOpenError);
    expect((opening as ReviewNotOpenError).reviewOpenAt).toBe("2026-01-02T00:00:00Z");
    const revision = await submitHistoricalReview("s", "2026-01-02", "f", request).catch((error) => error);
    expect(revision).toBeInstanceOf(RevisionConflictError);
    expect((revision as RevisionConflictError).actualRevision).toBe(4);
  });

  it.each([
    [404, "forecast_not_found", ForecastNotFoundError],
    [409, "idempotency_conflict", ReviewIdempotencyConflictError],
    [409, "demo_write_locked", DemoWriteLockedError],
  ])("maps %s %s without changing its public error", async (status, code, ErrorType) => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ error: { code, details: {} } }), { status }),
      ),
    );
    await expect(
      submitHistoricalReview("s", "2026-01-02", "f", request),
    ).rejects.toBeInstanceOf(ErrorType);
  });

  it("keeps the private fallback when an error response is not JSON", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response("not JSON", { status: 500, headers: { "Content-Type": "text/plain" } }),
      ),
    );
    await expect(
      submitHistoricalReview("s", "2026-01-02", "f", request),
    ).rejects.toThrow("No se pudo guardar la revisión histórica. Intentá nuevamente.");
  });
});
