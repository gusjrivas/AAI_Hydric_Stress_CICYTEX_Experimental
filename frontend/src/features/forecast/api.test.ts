import { afterEach, describe, expect, it, vi } from "vitest";

import { API_BASE_URL } from "../../api/baseUrl";
import {
  confirmAlert,
  getActivePredictor,
  HttpError,
  listFeedback,
  NO_READINGS_MESSAGE,
  recalibrate,
  rejectAlert,
  runForecast,
} from "./api";

afterEach(() => vi.unstubAllGlobals());

const feedback = {
  fecha: "2024-10-31",
  alerta_generada: 1,
  estado_validacion: "rechazada",
  etiqueta_corregida: null,
  observacion: null,
  y_proba: null,
  fecha_objetivo: null,
};

describe("forecast API transport contract", () => {
  it("preserves every URL, method, header, body omission and successful payload identity", async () => {
    const payloads = [
      {
        verdicts: [
          {
            fecha: "2024-10-31",
            alerta: true,
            probabilidad: 0.82,
            fecha_objetivo: null,
          },
        ],
        train_rows: 100,
        test_rows: 20,
        selection_warning: null,
      },
      { rows: [feedback] },
      feedback,
      feedback,
      {
        version: "model-v2",
        n_correcciones: 1,
        fechas_corregidas: ["2024-10-31"],
        recalibration_id: null,
      },
      {
        sensor_id: "sensor /\u00e1",
        origin: null,
        model_id: null,
        version: null,
        trained_through: null,
        calibration_end: null,
        horizon_days: 7,
        contract_version: 1,
        pipeline_version: "v1",
        feature_columns: [],
        lags: [],
        rolling_windows: [],
        applied_feedback_count: 0,
        applied_feedback_dates: [],
      },
    ];
    let responseIndex = 0;
    const fetchMock = vi.fn().mockImplementation(async () => {
      const payload = payloads[responseIndex];
      responseIndex += 1;
      return { ok: true, status: 200, json: async () => payload };
    });
    vi.stubGlobal("fetch", fetchMock);

    const sensorId = "sensor /\u00e1";
    const results = [
      await runForecast(sensorId),
      await listFeedback(sensorId),
      await confirmAlert(sensorId, "2024-10-31"),
      await rejectAlert(sensorId, "2024-10-31", 0, "Sin estr\u00e9s observado"),
      await recalibrate(sensorId),
      await getActivePredictor(sensorId),
    ];

    results.forEach((result, index) => expect(result).toBe(payloads[index]));
    expect(fetchMock.mock.calls).toEqual([
      [`${API_BASE_URL}/forecast/sensor%20%2F%C3%A1/run`, { method: "POST" }],
      [`${API_BASE_URL}/feedback/sensor%20%2F%C3%A1`],
      [
        `${API_BASE_URL}/feedback/sensor%20%2F%C3%A1/2024-10-31/confirm`,
        { method: "POST" },
      ],
      [
        `${API_BASE_URL}/feedback/sensor%20%2F%C3%A1/2024-10-31/reject`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            etiqueta_corregida: 0,
            observacion: "Sin estr\u00e9s observado",
          }),
        },
      ],
      [`${API_BASE_URL}/recalibrate/sensor%20%2F%C3%A1`, { method: "POST" }],
      [`${API_BASE_URL}/models/sensor%20%2F%C3%A1/active`],
    ]);
    expect(Object.keys(JSON.parse(fetchMock.mock.calls[3][1].body))).toEqual([
      "etiqueta_corregida",
      "observacion",
    ]);
  });

  it("exposes stable HttpError identity, status and backend detail", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 409,
        json: async () => ({ detail: "el pron\u00f3stico todav\u00eda no puede recalibrarse" }),
      }),
    );

    const error = await recalibrate("sensor-a").catch((reason: unknown) => reason);

    expect(error).toBeInstanceOf(HttpError);
    expect(error).toMatchObject({
      name: "HttpError",
      status: 409,
      message: "el pron\u00f3stico todav\u00eda no puede recalibrarse",
    });
  });

  it("sanitizes a missing dataset without exposing its internal path", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 404,
        json: async () => ({
          detail: "No existe el dataset 'sensor__sensor-a' en /workspace/data",
        }),
      }),
    );

    const error = await runForecast("sensor-a").catch((reason: unknown) => reason);

    expect(error).toBeInstanceOf(HttpError);
    expect(error).toMatchObject({ name: "HttpError", status: 404, message: NO_READINGS_MESSAGE });
    expect((error as Error).message).not.toMatch(/workspace|sensor__/);
  });

  it("preserves other 404 details instead of treating them as missing datasets", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 404,
        json: async () => ({ detail: "Todav\u00eda no se corri\u00f3 ning\u00fan pron\u00f3stico." }),
      }),
    );

    await expect(listFeedback("sensor-a")).rejects.toThrow(
      "Todav\u00eda no se corri\u00f3 ning\u00fan pron\u00f3stico.",
    );
  });

  it("uses each stable fallback when the error body is not JSON", async () => {
    const cases = [
      [() => runForecast("sensor-a"), "Error al correr el pron\u00f3stico: 503"],
      [() => listFeedback("sensor-a"), "Error al obtener el feedback: 503"],
      [() => confirmAlert("sensor-a", "2024-10-31"), "Error al confirmar la alerta: 503"],
      [
        () => rejectAlert("sensor-a", "2024-10-31", 1, "Estr\u00e9s observado"),
        "Error al rechazar la alerta: 503",
      ],
      [() => recalibrate("sensor-a"), "Error al recalibrar el modelo: 503"],
      [() => getActivePredictor("sensor-a"), "Error al obtener el predictor activo: 503"],
    ] as const;

    for (const [invoke, expectedMessage] of cases) {
      vi.stubGlobal(
        "fetch",
        vi.fn().mockResolvedValue({
          ok: false,
          status: 503,
          json: async () => Promise.reject(new SyntaxError("not JSON")),
        }),
      );
      await expect(invoke()).rejects.toMatchObject({
        name: "HttpError",
        status: 503,
        message: expectedMessage,
      });
    }
  });
});
