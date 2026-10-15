import { afterEach, describe, expect, it, vi } from "vitest";

import { API_BASE_URL } from "../../api/baseUrl";
import { getLineage } from "./api";

afterEach(() => vi.unstubAllGlobals());

describe("lineage API transport contract", () => {
  it("uses the configured host, encodes the sensor path and preserves GET", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ sensor_id: "sensor /\u00e1", chain: [] }),
    });
    vi.stubGlobal("fetch", fetchMock);

    await getLineage("sensor /\u00e1");

    expect(fetchMock).toHaveBeenCalledOnce();
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe(`${API_BASE_URL}/lineage/sensor%20%2F%C3%A1`);
    expect(init).toBeUndefined();
  });

  it("propagates a 409 integrity detail instead of inventing an empty chain", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 409,
        json: async () => ({ detail: "linaje corrupto o incompleto" }),
      }),
    );

    await expect(getLineage("sensor-a")).rejects.toThrow("linaje corrupto o incompleto");
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

    await expect(getLineage("sensor-a")).rejects.toThrow("Error al obtener el linaje: 500");
  });

  it("returns optional and nullable lineage evidence unchanged", async () => {
    const payload = {
      sensor_id: "sensor-a",
      chain: [
        {
          recalibration_id: "recalibration-1",
          source_model_id: "model-a",
          successor_model_id: "model-b",
          feedback_references: [],
          recalibrated_at: "2026-09-06T10:00:00",
          source_trained_through: "2024-10-30",
          successor_trained_through: "2024-10-31",
          lineage_version: 1,
          dataset_sha256: null,
        },
        {
          recalibration_id: "recalibration-2",
          source_model_id: "model-b",
          successor_model_id: "model-c",
          feedback_references: [],
          recalibrated_at: "2026-09-07T10:00:00",
          source_trained_through: "2024-10-31",
          successor_trained_through: "2024-11-01",
          lineage_version: 2,
        },
      ],
    };
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => payload }),
    );

    await expect(getLineage("sensor-a")).resolves.toBe(payload);
  });
});
