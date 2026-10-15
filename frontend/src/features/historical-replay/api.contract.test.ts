import { afterEach, describe, expect, it, vi } from "vitest";

import {
  ReplayApiError,
  ReplayNotFoundError,
  ReplayNotYetRevealedError,
  createFeedback,
  getCandidate,
  getFeedback,
  getHistory,
  getPrediction,
  listOrigins,
} from "./api";

const API = "http://localhost:8000";

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("historical replay transport compatibility", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("preserves every path, method, encoded parameter, header and optional omission", async () => {
    const fetchMock = vi.fn().mockImplementation(() => Promise.resolve(jsonResponse({})));
    vi.stubGlobal("fetch", fetchMock);

    await getCandidate();
    await listOrigins();
    await getPrediction("2024-10-19/a b", "2024-10-22");
    await getHistory("2024-10-22");
    await getFeedback("2024-10-19/a b", "2024-10-22");
    await createFeedback("2024-10-19/a b", {
      simulated_date: "2024-10-22",
      estado_validacion: "confirmada",
      etiqueta_corregida: null,
      observacion: undefined,
    });

    expect(fetchMock.mock.calls).toEqual([
      [`${API}/replay/candidate`, undefined],
      [`${API}/replay/predictions`, undefined],
      [
        `${API}/replay/predictions/2024-10-19%2Fa%20b?simulated_date=2024-10-22`,
        undefined,
      ],
      [`${API}/replay/history?simulated_date=2024-10-22`, undefined],
      [
        `${API}/replay/predictions/2024-10-19%2Fa%20b/feedback?simulated_date=2024-10-22`,
        undefined,
      ],
      [
        `${API}/replay/predictions/2024-10-19%2Fa%20b/feedback`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            simulated_date: "2024-10-22",
            estado_validacion: "confirmada",
            etiqueta_corregida: null,
          }),
        },
      ],
    ]);
  });

  it.each([
    [404, ReplayNotFoundError, "predicción inexistente"],
    [409, ReplayNotYetRevealedError, "objetivo todavía oculto"],
    [503, ReplayApiError, "almacenamiento no disponible"],
  ])("preserves the %s error class and JSON detail", async (status, ErrorClass, detail) => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ detail }, status)));

    const error = await getCandidate().catch((reason: unknown) => reason);
    expect(error).toEqual(expect.any(ErrorClass));
    expect(error).toMatchObject({ message: detail });
  });

  it("preserves the generic status message when an error body is not JSON", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response("private non-json body", { status: 500 })),
    );

    const error = await getCandidate().catch((reason: unknown) => reason);
    expect(error).toEqual(expect.any(ReplayApiError));
    expect(error).toMatchObject({
      message: "Error de la API de reproducción histórica: 500",
    });
  });
});
