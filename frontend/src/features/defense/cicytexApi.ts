import type { components, operations } from "../../api/generated/schema";

const API = import.meta.env.VITE_API_BASE_URL ?? "";

export type CicytexCatalog = components["schemas"]["CicytexCatalogResponse"];
export type ReplayPrediction = components["schemas"]["CicytexPredictionResponse"];
export type ReplayMetric = components["schemas"]["CicytexMetricResponse"];
export type ReplayFeedback = components["schemas"]["CicytexFeedbackResponse"];
export type CicytexSession = components["schemas"]["CicytexSessionResponse"];
export type CicytexProvenance = components["schemas"]["CicytexProvenanceResponse"];

type CatalogOperation = operations["catalog_api_v2_cicytex_replay_catalog_get"];
type CreateSessionOperation = operations["create_session_api_v2_cicytex_replay_sessions_post"];
type AdvanceSessionOperation =
  operations["advance_api_v2_cicytex_replay_sessions__session_id__advance_post"];
type ResetSessionOperation =
  operations["reset_api_v2_cicytex_replay_sessions__session_id__reset_post"];
type CreateFeedbackOperation =
  operations["create_feedback_api_v2_cicytex_replay_sessions__session_id__feedback_post"];

type CatalogResponse = CatalogOperation["responses"][200]["content"]["application/json"];
type SessionRequest = CreateSessionOperation["requestBody"]["content"]["application/json"];
type CreatedSessionResponse =
  CreateSessionOperation["responses"][201]["content"]["application/json"];
type AdvancedSessionResponse =
  AdvanceSessionOperation["responses"][200]["content"]["application/json"];
type ResetSessionResponse =
  ResetSessionOperation["responses"][200]["content"]["application/json"];
type FeedbackRequest = CreateFeedbackOperation["requestBody"]["content"]["application/json"];
type FeedbackResponse =
  CreateFeedbackOperation["responses"][201]["content"]["application/json"];

async function json<T>(pending: Promise<Response>): Promise<T> {
  const response = await pending;
  if (!response.ok) throw new Error((await response.text()) || `HTTP ${response.status}`);
  return response.json();
}

export const getCicytexProvenance = (): Promise<CicytexProvenance> =>
  json(fetch(`${API}/api/v2/cicytex/replay/provenance`));

export const getCicytexCatalog = (): Promise<CatalogResponse> =>
  json(fetch(`${API}/api/v2/cicytex/replay/catalog`));

export const createCicytexSession = (
  sensor_id: SessionRequest["sensor_id"],
  emission_date: SessionRequest["emission_date"],
  horizon_days: SessionRequest["horizon_days"],
): Promise<CreatedSessionResponse> =>
  json(
    fetch(`${API}/api/v2/cicytex/replay/sessions`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sensor_id, emission_date, horizon_days }),
    }),
  );

export const advanceCicytexSession = (
  id: AdvanceSessionOperation["parameters"]["path"]["session_id"],
): Promise<AdvancedSessionResponse> =>
  json(
    fetch(`${API}/api/v2/cicytex/replay/sessions/${id}/advance`, {
      method: "POST",
    }),
  );

export const resetCicytexSession = (
  id: ResetSessionOperation["parameters"]["path"]["session_id"],
): Promise<ResetSessionResponse> =>
  json(
    fetch(`${API}/api/v2/cicytex/replay/sessions/${id}/reset`, {
      method: "POST",
    }),
  );

export const submitCicytexFeedback = (
  id: CreateFeedbackOperation["parameters"]["path"]["session_id"],
  input: FeedbackRequest,
): Promise<FeedbackResponse> =>
  json(
    fetch(`${API}/api/v2/cicytex/replay/sessions/${id}/feedback`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    }),
  );
