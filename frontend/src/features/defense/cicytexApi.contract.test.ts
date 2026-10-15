import { afterEach, describe, expect, it, vi } from "vitest";

import {
  advanceCicytexSession,
  createCicytexSession,
  getCicytexCatalog,
  resetCicytexSession,
  submitCicytexFeedback,
} from "./cicytexApi";

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("CICYTEX replay transport compatibility", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("preserves paths, methods, headers, bodies and optional omission", async () => {
    const fetchMock = vi.fn().mockImplementation(() => Promise.resolve(jsonResponse({})));
    vi.stubGlobal("fetch", fetchMock);

    await getCicytexCatalog();
    await createCicytexSession("CP1 S/1", "2023-07-06", 3);
    await advanceCicytexSession("session/a b");
    await resetCicytexSession("session/a b");
    await submitCicytexFeedback("session/a b", {
      estado_validacion: "rechazada",
      etiqueta_corregida: null,
      observacion: undefined,
    });

    expect(fetchMock.mock.calls).toEqual([
      ["/api/v2/cicytex/replay/catalog"],
      [
        "/api/v2/cicytex/replay/sessions",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            sensor_id: "CP1 S/1",
            emission_date: "2023-07-06",
            horizon_days: 3,
          }),
        },
      ],
      [
        "/api/v2/cicytex/replay/sessions/session/a b/advance",
        { method: "POST" },
      ],
      [
        "/api/v2/cicytex/replay/sessions/session/a b/reset",
        { method: "POST" },
      ],
      [
        "/api/v2/cicytex/replay/sessions/session/a b/feedback",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            estado_validacion: "rechazada",
            etiqueta_corregida: null,
          }),
        },
      ],
    ]);
  });

  it("preserves Error(response.text), including the HTTP fallback", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response("sesión inexistente", { status: 404 }))
      .mockResolvedValueOnce(new Response("", { status: 503 }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(getCicytexCatalog()).rejects.toThrow("sesión inexistente");
    await expect(getCicytexCatalog()).rejects.toThrow("HTTP 503");
  });
});
