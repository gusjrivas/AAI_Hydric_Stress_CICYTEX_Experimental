import { afterEach, describe, expect, it, vi } from "vitest";

import { API_BASE_URL } from "../../api/baseUrl";
import { getQualityReport } from "./api";

afterEach(() => vi.unstubAllGlobals());

describe("quality API transport contract", () => {
  it("uses the configured host, encodes the sensor path and preserves GET", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ sensor_id: "sensor /\u00e1" }),
    });
    vi.stubGlobal("fetch", fetchMock);

    await getQualityReport("sensor /\u00e1");

    expect(fetchMock).toHaveBeenCalledOnce();
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe(`${API_BASE_URL}/quality/sensor%20%2F%C3%A1`);
    expect(init).toBeUndefined();
  });

  it("maps a missing dataset to null without parsing an error payload", async () => {
    const json = vi.fn();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: false, status: 404, json }),
    );

    await expect(getQualityReport("sensor-new")).resolves.toBeNull();
    expect(json).not.toHaveBeenCalled();
  });

  it("preserves a backend detail for non-404 errors", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 503,
        json: async () => ({ detail: "calidad temporalmente no disponible" }),
      }),
    );

    await expect(getQualityReport("sensor-a")).rejects.toThrow(
      "calidad temporalmente no disponible",
    );
  });

  it("uses the stable status fallback when an error body is not JSON", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 500,
        json: async () => Promise.reject(new SyntaxError("not JSON")),
      }),
    );

    await expect(getQualityReport("sensor-a")).rejects.toThrow(
      "Error al obtener la calidad de datos: 500",
    );
  });

  it("returns the successful payload unchanged, including nullable periods", async () => {
    const payload = {
      sensor_id: "sensor-a",
      total_rows: 0,
      period_start: null,
      period_end: null,
      missing_pct: {},
      duplicate_timestamps: [],
      out_of_range: {},
      anomalies_detected: 0,
      anomaly_method: "isolation_forest",
      anomaly_contamination: 0.05,
      anomaly_columns: [],
      is_diagnostic_only: true,
      note: "Sin observaciones suficientes.",
    };
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => payload }),
    );

    await expect(getQualityReport("sensor-a")).resolves.toBe(payload);
  });
});
