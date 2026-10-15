import { afterEach, describe, expect, it, vi } from "vitest";

import { API_BASE_URL } from "../../api/baseUrl";
import { ingestLabReading } from "./sensorLabApi";

afterEach(() => vi.unstubAllGlobals());

const reading = {
  soil_moisture: 0.31,
  temperature: 22.5,
  relative_humidity: 61,
  precipitation: 0,
  solar_radiation: 18.4,
  wind_speed: 2.3,
};

describe("sensor laboratory ingest API transport contract", () => {
  it("encodes the sensor path and sends the exact synthetic reading body", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ timestamp: "2026-04-30T00:00:00Z", filas_totales: 1 }),
    });
    vi.stubGlobal("fetch", fetchMock);

    await ingestLabReading("sensor /\u00e1", "2026-04-30", reading);

    expect(fetchMock).toHaveBeenCalledOnce();
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe(`${API_BASE_URL}/sensors/sensor%20%2F%C3%A1/readings`);
    expect(init).toEqual({
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        timestamp: "2026-04-30T00:00:00Z",
        soil_moisture: 0.31,
        temperature: 22.5,
        relative_humidity: 61,
        precipitation: 0,
        solar_radiation: 18.4,
        wind_speed: 2.3,
        procedencia: "sintetico",
      }),
    });
    const body = JSON.parse(init.body);
    expect(body).not.toHaveProperty("et0");
    expect(Object.keys(body)).toHaveLength(8);
  });

  it("preserves an explicit backend detail", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 422,
        json: async () => ({ detail: "lectura sint\u00e9tica inv\u00e1lida" }),
      }),
    );

    await expect(ingestLabReading("lab-a", "2026-04-30", reading)).rejects.toThrow(
      "lectura sint\u00e9tica inv\u00e1lida",
    );
  });

  it("uses the stable status fallback when an error body is not JSON", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 503,
        json: async () => Promise.reject(new SyntaxError("not JSON")),
      }),
    );

    await expect(ingestLabReading("lab-a", "2026-04-30", reading)).rejects.toThrow(
      "Error al ingerir una lectura sint\u00e9tica: 503",
    );
  });

  it("returns the successful payload unchanged", async () => {
    const payload = { timestamp: "2026-04-30T00:00:00Z", filas_totales: 121 };
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => payload }),
    );

    await expect(ingestLabReading("lab-a", "2026-04-30", reading)).resolves.toBe(payload);
  });
});
