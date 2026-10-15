import { describe, expectTypeOf, it } from "vitest";

import type { components, operations } from "./api/generated/schema";
import {
  createFeedback,
  getCandidate,
  getFeedback,
  getHistory,
  getPrediction,
  listOrigins,
} from "./features/historical-replay/api";
import {
  advanceCicytexSession,
  createCicytexSession,
  getCicytexCatalog,
  resetCicytexSession,
  submitCicytexFeedback,
} from "./features/defense/cicytexApi";

type Equal<Left, Right> =
  (<Value>() => Value extends Left ? 1 : 2) extends <Value>() => Value extends Right ? 1 : 2
    ? (<Value>() => Value extends Right ? 1 : 2) extends <Value>() => Value extends Left ? 1 : 2
      ? true
      : false
    : false;
type Assert<Condition extends true> = Condition;

type CandidateOperation = operations["get_candidate_replay_candidate_get"];
type OriginsOperation = operations["list_origins_replay_predictions_get"];
type PredictionOperation =
  operations["get_prediction_replay_predictions__timestamp_origen__get"];
type HistoryOperation = operations["get_history_replay_history_get"];
type GetFeedbackOperation =
  operations["get_feedback_replay_predictions__timestamp_origen__feedback_get"];
type CreateFeedbackOperation =
  operations["create_feedback_replay_predictions__timestamp_origen__feedback_post"];
type CatalogOperation = operations["catalog_api_v2_cicytex_replay_catalog_get"];
type CreateSessionOperation = operations["create_session_api_v2_cicytex_replay_sessions_post"];
type CicytexFeedbackOperation =
  operations["create_feedback_api_v2_cicytex_replay_sessions__session_id__feedback_post"];

type HistoricalCandidate = CandidateOperation["responses"][200]["content"]["application/json"];
type HistoricalOrigins = OriginsOperation["responses"][200]["content"]["application/json"];
type HistoricalPrediction = PredictionOperation["responses"][200]["content"]["application/json"];
type HistoricalHistory = HistoryOperation["responses"][200]["content"]["application/json"];
type HistoricalFeedbackList =
  GetFeedbackOperation["responses"][200]["content"]["application/json"];
type HistoricalFeedbackRequest =
  CreateFeedbackOperation["requestBody"]["content"]["application/json"];
type HistoricalFeedbackEntry =
  CreateFeedbackOperation["responses"][201]["content"]["application/json"];
type CicytexCatalog = CatalogOperation["responses"][200]["content"]["application/json"];
type CicytexSession = CreateSessionOperation["responses"][201]["content"]["application/json"];
type CicytexFeedbackRequest =
  CicytexFeedbackOperation["requestBody"]["content"]["application/json"];
type CicytexFeedback =
  CicytexFeedbackOperation["responses"][201]["content"]["application/json"];

export type GeneratedReplayFunctionContracts = [
  Assert<Equal<ReturnType<typeof getCandidate>, Promise<HistoricalCandidate>>>,
  Assert<Equal<ReturnType<typeof listOrigins>, Promise<HistoricalOrigins>>>,
  Assert<Equal<ReturnType<typeof getPrediction>, Promise<HistoricalPrediction>>>,
  Assert<Equal<ReturnType<typeof getHistory>, Promise<HistoricalHistory>>>,
  Assert<Equal<ReturnType<typeof getFeedback>, Promise<HistoricalFeedbackList>>>,
  Assert<Equal<Parameters<typeof createFeedback>[1], HistoricalFeedbackRequest>>,
  Assert<Equal<ReturnType<typeof createFeedback>, Promise<HistoricalFeedbackEntry>>>,
  Assert<Equal<ReturnType<typeof getCicytexCatalog>, Promise<CicytexCatalog>>>,
  Assert<Equal<ReturnType<typeof createCicytexSession>, Promise<CicytexSession>>>,
  Assert<Equal<ReturnType<typeof advanceCicytexSession>, Promise<CicytexSession>>>,
  Assert<Equal<ReturnType<typeof resetCicytexSession>, Promise<CicytexSession>>>,
  Assert<Equal<Parameters<typeof submitCicytexFeedback>[1], CicytexFeedbackRequest>>,
  Assert<Equal<ReturnType<typeof submitCicytexFeedback>, Promise<CicytexFeedback>>>,
];

type Prediction = components["schemas"]["CicytexPredictionResponse"];
type Session = components["schemas"]["CicytexSessionResponse"];
type IsRequired<ObjectType, Key extends keyof ObjectType> = {} extends Pick<ObjectType, Key>
  ? false
  : true;

export type GeneratedReplayRequiredAndNullableContracts = [
  Assert<IsRequired<Prediction, "observed_soil_moisture">>,
  Assert<IsRequired<Prediction, "observed_label">>,
  Assert<IsRequired<Prediction, "outcome">>,
  Assert<IsRequired<Session, "feedback">>,
];

const nullableFields: [
  Prediction["observed_soil_moisture"],
  Prediction["observed_label"],
  Prediction["outcome"],
  Session["feedback"],
] = [null, null, null, null];
void nullableFields;

// @ts-expect-error the nullable label accepts a number or null, never a string.
const invalidNullableLabel: Prediction["observed_label"] = "unknown";
void invalidNullableLabel;

const acceptPrediction = (_prediction: Prediction) => undefined;
acceptPrediction({
  method: "ensemble",
  score: 0.75,
  alert: true,
  target_date: "2023-07-07",
  observed_soil_moisture: null,
  observed_label: null,
  outcome: null,
});

// @ts-expect-error observed_label is explicit and required even before it is revealed.
acceptPrediction({
  method: "ensemble",
  score: 0.75,
  alert: true,
  target_date: "2023-07-07",
  observed_soil_moisture: null,
  outcome: null,
});

describe("generated replay type contracts", () => {
  it("keeps the established runtime exports callable", () => {
    expectTypeOf(getCandidate).toBeFunction();
    expectTypeOf(getCicytexCatalog).toBeFunction();
    expectTypeOf(createFeedback).toBeFunction();
    expectTypeOf(submitCicytexFeedback).toBeFunction();
  });
});
