import { afterEach, describe, expect, it, vi } from "vitest";
import { PRODUCER_API_BASE_URL } from "../../api/baseUrl";
import { getBatchProvenance } from "./provenanceApi";

afterEach(() => vi.unstubAllGlobals());

describe("getBatchProvenance", () => {
  it("issues a read-only GET with the encoded sensor and batch", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ batch_id: "b/1" }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    await expect(getBatchProvenance("sensor / á", "b/1")).resolves.toEqual({ batch_id: "b/1" });
    expect(fetchMock).toHaveBeenCalledWith(
      `${PRODUCER_API_BASE_URL}/api/v2/sensors/sensor%20%2F%20%C3%A1/batches/b%2F1/provenance`,
    );
    expect(fetchMock.mock.calls[0]).toHaveLength(1);
  });

  it("surfaces the backend error message and falls back to a generic one", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ error: { code: "batch_not_found", message: "La emisión no existe para este sensor." } }), { status: 404 }),
    ));
    await expect(getBatchProvenance("s", "b")).rejects.toThrow("La emisión no existe para este sensor.");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("boom", { status: 500 })));
    await expect(getBatchProvenance("s", "b")).rejects.toThrow(/procedencia/i);
  });
});
