import { afterEach, describe, expect, it, vi } from "vitest";

import { PRODUCER_API_BASE_URL } from "../../api/baseUrl";
import { ProducerV2UnavailableError } from "./catalogApi";
import { getSensorReadings, SensorNotFoundError } from "./readingsApi";

afterEach(() => vi.unstubAllGlobals());

function response(status: number, body?: unknown) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: body === undefined ? vi.fn().mockRejectedValue(new SyntaxError("not JSON")) : vi.fn().mockResolvedValue(body),
  };
}

describe("producer readings transport", () => {
  it("encodes the sensor, preserves days and returns input roles unchanged", async () => {
    const payload = {
      sensor_id: "sensor / á",
      calendar_timezone: "UTC" as const,
      server_today: "2026-10-15",
      snapshot_id: null,
      window: { start_date: "2026-10-15", end_date: "2026-10-15", expected_days: 1 },
      status: "ready" as const,
      rows: [],
      missing_dates: [],
      variable_coverage: [],
      units: {},
      last_reading_date: null,
      data_age_days: null,
      provenance: "real" as const,
      input_roles: [],
    };
    const fetchMock = vi.fn().mockResolvedValue(response(200, payload));
    vi.stubGlobal("fetch", fetchMock);

    await expect(getSensorReadings("sensor / á", 31)).resolves.toBe(payload);
    expect(fetchMock).toHaveBeenCalledWith(
      `${PRODUCER_API_BASE_URL}/api/v2/sensors/sensor%20%2F%20%C3%A1/readings?days=31`,
    );
  });

  it("distinguishes a missing sensor from an unavailable v2 facade", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValueOnce(response(404, { error: { code: "not_found" } })).mockResolvedValueOnce(response(404)));

    await expect(getSensorReadings("missing", 7)).rejects.toBeInstanceOf(SensorNotFoundError);
    await expect(getSensorReadings("missing", 7)).rejects.toBeInstanceOf(ProducerV2UnavailableError);
  });

  it("preserves structured details and the stable fallback", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValueOnce(response(503, { error: { message: "lecturas ocupadas" } })).mockResolvedValueOnce(response(500)));

    await expect(getSensorReadings("sensor-a", 7)).rejects.toThrow("lecturas ocupadas");
    await expect(getSensorReadings("sensor-a", 7)).rejects.toThrow("No se pudieron cargar las mediciones. Intentá nuevamente.");
  });
});
