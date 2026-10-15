import { API_BASE_URL } from "../../api/baseUrl";
import type { components, operations } from "../../api/generated/schema";

export class HttpError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "HttpError";
    this.status = status;
  }
}

/** Mensaje para un punto sin dataset: nunca se muestra la ruta interna que devuelve el backend. */
export const NO_READINGS_MESSAGE =
  "Este punto de medición todavía no tiene mediciones, por eso no hay nada que consultar o calcular. Cargalas primero desde el Laboratorio o con la demostración.";
const MISSING_DATASET = /no existe el dataset/i;

async function readDetail(response: Response, fallback: string): Promise<never> {
  const body = await response.json().catch(() => null);
  if (response.status === 404 && typeof body?.detail === "string" && MISSING_DATASET.test(body.detail)) {
    throw new HttpError(404, NO_READINGS_MESSAGE);
  }
  throw new HttpError(response.status, body?.detail ?? fallback);
}

export type Verdict = components["schemas"]["Verdict"];
export type ForecastRunResponse = components["schemas"]["ForecastRunResponse"];
export type FeedbackRow = components["schemas"]["FeedbackRow"];
export type FeedbackListResponse = components["schemas"]["FeedbackListResponse"];
export type RecalibrationResponse = components["schemas"]["RecalibrationResponse"];
export type ActivePredictor = components["schemas"]["ActivePredictorResponse"];

type RunForecastOperation = operations["run_forecast_forecast__sensor_id__run_post"];
type ListFeedbackOperation = operations["list_feedback_feedback__sensor_id__get"];
type ConfirmFeedbackOperation =
  operations["confirm_feedback_feedback__sensor_id___fecha__confirm_post"];
type RejectFeedbackOperation =
  operations["reject_feedback_feedback__sensor_id___fecha__reject_post"];
type RecalibrateOperation = operations["recalibrate_recalibrate__sensor_id__post"];
type ActivePredictorOperation =
  operations["get_active_predictor_models__sensor_id__active_get"];

export async function runForecast(
  sensorId: RunForecastOperation["parameters"]["path"]["sensor_id"],
): Promise<RunForecastOperation["responses"][200]["content"]["application/json"]> {
  const response = await fetch(`${API_BASE_URL}/forecast/${encodeURIComponent(sensorId)}/run`, { method: "POST" });
  if (!response.ok) {
    return readDetail(response, `Error al correr el pronóstico: ${response.status}`);
  }
  return response.json();
}

export async function listFeedback(
  sensorId: ListFeedbackOperation["parameters"]["path"]["sensor_id"],
): Promise<ListFeedbackOperation["responses"][200]["content"]["application/json"]> {
  const response = await fetch(`${API_BASE_URL}/feedback/${encodeURIComponent(sensorId)}`);
  if (!response.ok) {
    return readDetail(response, `Error al obtener el feedback: ${response.status}`);
  }
  return response.json();
}

export async function confirmAlert(
  sensorId: ConfirmFeedbackOperation["parameters"]["path"]["sensor_id"],
  fecha: ConfirmFeedbackOperation["parameters"]["path"]["fecha"],
): Promise<ConfirmFeedbackOperation["responses"][200]["content"]["application/json"]> {
  const response = await fetch(`${API_BASE_URL}/feedback/${encodeURIComponent(sensorId)}/${fecha}/confirm`, { method: "POST" });
  if (!response.ok) {
    return readDetail(response, `Error al confirmar la alerta: ${response.status}`);
  }
  return response.json();
}

export async function rejectAlert(
  sensorId: RejectFeedbackOperation["parameters"]["path"]["sensor_id"],
  fecha: RejectFeedbackOperation["parameters"]["path"]["fecha"],
  etiquetaCorregida: RejectFeedbackOperation["requestBody"]["content"]["application/json"]["etiqueta_corregida"],
  observacion: RejectFeedbackOperation["requestBody"]["content"]["application/json"]["observacion"],
): Promise<RejectFeedbackOperation["responses"][200]["content"]["application/json"]> {
  const payload = {
    etiqueta_corregida: etiquetaCorregida,
    observacion,
  } satisfies RejectFeedbackOperation["requestBody"]["content"]["application/json"];
  const response = await fetch(`${API_BASE_URL}/feedback/${encodeURIComponent(sensorId)}/${fecha}/reject`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    return readDetail(response, `Error al rechazar la alerta: ${response.status}`);
  }
  return response.json();
}

export async function recalibrate(
  sensorId: RecalibrateOperation["parameters"]["path"]["sensor_id"],
): Promise<RecalibrateOperation["responses"][200]["content"]["application/json"]> {
  const response = await fetch(`${API_BASE_URL}/recalibrate/${encodeURIComponent(sensorId)}`, { method: "POST" });
  if (!response.ok) {
    return readDetail(response, `Error al recalibrar el modelo: ${response.status}`);
  }
  return response.json();
}

export async function getActivePredictor(
  sensorId: ActivePredictorOperation["parameters"]["path"]["sensor_id"],
): Promise<ActivePredictorOperation["responses"][200]["content"]["application/json"]> {
  const response = await fetch(`${API_BASE_URL}/models/${encodeURIComponent(sensorId)}/active`);
  if (!response.ok) {
    return readDetail(response, `Error al obtener el predictor activo: ${response.status}`);
  }
  return response.json();
}
