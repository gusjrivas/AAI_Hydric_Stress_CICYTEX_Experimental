import { afterEach, describe, expect, it, vi } from "vitest";

import { PRODUCER_API_BASE_URL } from "../../api/baseUrl";
import { listSectors, listSensors, ProducerV2UnavailableError } from "./catalogApi";

afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
  vi.resetModules();
});

function response(status: number, body?: unknown) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: body === undefined ? vi.fn().mockRejectedValue(new SyntaxError("not JSON")) : vi.fn().mockResolvedValue(body),
  };
}

describe("producer catalog transport", () => {
  it("keeps GET paths, cursor payloads and sector encoding unchanged", async () => {
    const sectors = { items: [], next_cursor: "sector-cursor" };
    const sensors = { items: [], next_cursor: null };
    const fetchMock = vi.fn().mockResolvedValueOnce(response(200, sectors)).mockResolvedValueOnce(response(200, sensors));
    vi.stubGlobal("fetch", fetchMock);

    await expect(listSectors()).resolves.toBe(sectors);
    await expect(listSensors("north / á")).resolves.toBe(sensors);
    expect(fetchMock.mock.calls).toEqual([
      [`${PRODUCER_API_BASE_URL}/api/v2/sectors`],
      [`${PRODUCER_API_BASE_URL}/api/v2/sensors?sector_id=north%20%2F%20%C3%A1`],
    ]);
  });

  it("omits the optional sector query instead of serializing it", async () => {
    const fetchMock = vi.fn().mockResolvedValue(response(200, { items: [], next_cursor: null }));
    vi.stubGlobal("fetch", fetchMock);

    await listSensors();

    expect(fetchMock).toHaveBeenCalledWith(`${PRODUCER_API_BASE_URL}/api/v2/sensors`);
  });

  it("preserves bodyless 404 and structured error behavior", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValueOnce(response(404)).mockResolvedValueOnce(response(409, { error: { message: "cursor inválido" } })));

    await expect(listSectors()).rejects.toBeInstanceOf(ProducerV2UnavailableError);
    await expect(listSensors()).rejects.toThrow("cursor inválido");
  });

  it("uses the producer host when both API base URLs differ", async () => {
    vi.stubEnv("VITE_API_BASE_URL", "http://127.0.0.1:8299");
    vi.stubEnv("VITE_PRODUCER_API_BASE_URL", "http://127.0.0.1:8199");
    vi.resetModules();
    const { listSectors: freshListSectors } = await import("./catalogApi");
    const fetchMock = vi.fn().mockResolvedValue(response(200, { items: [], next_cursor: null }));
    vi.stubGlobal("fetch", fetchMock);

    await freshListSectors();

    expect(new URL(fetchMock.mock.calls[0][0]).origin).toBe("http://127.0.0.1:8199");
  });
});
