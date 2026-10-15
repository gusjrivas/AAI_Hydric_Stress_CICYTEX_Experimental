import { API_BASE_URL } from "../../api/baseUrl";
import type { components, operations } from "../../api/generated/schema";

export type ReplayDisclaimers = components["schemas"]["ReplayDisclaimers"];
export type ReplayEvidenceCard = components["schemas"]["ReplayEvidenceCard"];
export type ReplayLabelRule = components["schemas"]["ReplayLabelRule"];
export type ReplayCandidateInfo = components["schemas"]["ReplayCandidateInfo"];
export type ReplayOriginsResponse = components["schemas"]["ReplayOriginsResponse"];
export type MedicionOriginal = components["schemas"]["MedicionOriginal"];
export type ReplayPredictionResponse = components["schemas"]["ReplayPredictionResponse"];
export type ReplayHistoryRow = components["schemas"]["ReplayHistoryRow"];
export type ReplayHistoryResponse = components["schemas"]["ReplayHistoryResponse"];
export type EstadoValidacion =
  components["schemas"]["ReplayFeedbackRequest"]["estado_validacion"];
export type ReplayFeedbackEntry = components["schemas"]["ReplayFeedbackEntry"];
export type ReplayFeedbackListResponse = components["schemas"]["ReplayFeedbackListResponse"];

type CandidateOperation = operations["get_candidate_replay_candidate_get"];
type OriginsOperation = operations["list_origins_replay_predictions_get"];
type PredictionOperation =
  operations["get_prediction_replay_predictions__timestamp_origen__get"];
type HistoryOperation = operations["get_history_replay_history_get"];
type GetFeedbackOperation =
  operations["get_feedback_replay_predictions__timestamp_origen__feedback_get"];
type CreateFeedbackOperation =
  operations["create_feedback_replay_predictions__timestamp_origen__feedback_post"];

type CandidateResponse = CandidateOperation["responses"][200]["content"]["application/json"];
type OriginsResponse = OriginsOperation["responses"][200]["content"]["application/json"];
type PredictionResponse = PredictionOperation["responses"][200]["content"]["application/json"];
type HistoryResponse = HistoryOperation["responses"][200]["content"]["application/json"];
type FeedbackListResponse =
  GetFeedbackOperation["responses"][200]["content"]["application/json"];
type FeedbackRequest = CreateFeedbackOperation["requestBody"]["content"]["application/json"];
type FeedbackResponse =
  CreateFeedbackOperation["responses"][201]["content"]["application/json"];

export class ReplayNotFoundError extends Error {}
export class ReplayNotYetRevealedError extends Error {}
export class ReplayApiError extends Error {}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, init);
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const message = body?.detail ?? `Error de la API de reproducción histórica: ${response.status}`;
    if (response.status === 404) throw new ReplayNotFoundError(message);
    if (response.status === 409) throw new ReplayNotYetRevealedError(message);
    throw new ReplayApiError(message);
  }
  return response.json();
}

export function getCandidate(): Promise<CandidateResponse> {
  return requestJson("/replay/candidate");
}

export function listOrigins(): Promise<OriginsResponse> {
  return requestJson("/replay/predictions");
}

export function getPrediction(
  timestampOrigen: PredictionOperation["parameters"]["path"]["timestamp_origen"],
  simulatedDate: PredictionOperation["parameters"]["query"]["simulated_date"],
): Promise<PredictionResponse> {
  const params = new URLSearchParams({ simulated_date: simulatedDate });
  return requestJson(`/replay/predictions/${encodeURIComponent(timestampOrigen)}?${params}`);
}

export function getHistory(
  simulatedDate: HistoryOperation["parameters"]["query"]["simulated_date"],
): Promise<HistoryResponse> {
  const params = new URLSearchParams({ simulated_date: simulatedDate });
  return requestJson(`/replay/history?${params}`);
}

export function getFeedback(
  timestampOrigen: GetFeedbackOperation["parameters"]["path"]["timestamp_origen"],
  simulatedDate: GetFeedbackOperation["parameters"]["query"]["simulated_date"],
): Promise<FeedbackListResponse> {
  const params = new URLSearchParams({ simulated_date: simulatedDate });
  return requestJson(`/replay/predictions/${encodeURIComponent(timestampOrigen)}/feedback?${params}`);
}

export function createFeedback(
  timestampOrigen: CreateFeedbackOperation["parameters"]["path"]["timestamp_origen"],
  body: FeedbackRequest,
): Promise<FeedbackResponse> {
  return requestJson(`/replay/predictions/${encodeURIComponent(timestampOrigen)}/feedback`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}
