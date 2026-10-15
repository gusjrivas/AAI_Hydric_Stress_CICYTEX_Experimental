import { describe, expectTypeOf, it } from "vitest";

import type { components, operations } from "./api/generated/schema";
import { getQualityReport } from "./features/quality/api";
import type { QualityReport } from "./features/quality/api";
import { getLineage } from "./features/lineage/api";
import type {
  FeedbackReference,
  LineageEntry,
  LineageResponse,
} from "./features/lineage/api";
import { ingestLabReading } from "./features/lab/sensorLabApi";
import type { LabIngestResult } from "./features/lab/sensorLabApi";
import type { LabReadingValues } from "./features/lab/readingGenerator";
import {
  confirmAlert,
  getActivePredictor,
  listFeedback,
  recalibrate,
  rejectAlert,
  runForecast,
} from "./features/forecast/api";
import type {
  ActivePredictor,
  FeedbackListResponse,
  FeedbackRow,
  ForecastRunResponse,
  RecalibrationResponse,
  Verdict,
} from "./features/forecast/api";

type Equal<Left, Right> =
  (<Value>() => Value extends Left ? 1 : 2) extends <Value>() => Value extends Right ? 1 : 2
    ? (<Value>() => Value extends Right ? 1 : 2) extends <Value>() => Value extends Left ? 1 : 2
      ? true
      : false
    : false;
type Assert<Condition extends true> = Condition;

type QualityOperation = operations["get_quality_report_quality__sensor_id__get"];
type QualityResponse = QualityOperation["responses"][200]["content"]["application/json"];
type QualitySensorId = QualityOperation["parameters"]["path"]["sensor_id"];
type LineageOperation = operations["get_lineage_lineage__sensor_id__get"];
type GeneratedLineageResponse =
  LineageOperation["responses"][200]["content"]["application/json"];
type LineageSensorId = LineageOperation["parameters"]["path"]["sensor_id"];
type LabIngestOperation = operations["ingest_reading_sensors__sensor_id__readings_post"];
type GeneratedLabIngestRequest =
  LabIngestOperation["requestBody"]["content"]["application/json"];
type GeneratedLabIngestResponse =
  LabIngestOperation["responses"][200]["content"]["application/json"];
type LabSensorId = LabIngestOperation["parameters"]["path"]["sensor_id"];
type RunForecastOperation = operations["run_forecast_forecast__sensor_id__run_post"];
type ListFeedbackOperation = operations["list_feedback_feedback__sensor_id__get"];
type ConfirmFeedbackOperation =
  operations["confirm_feedback_feedback__sensor_id___fecha__confirm_post"];
type RejectFeedbackOperation =
  operations["reject_feedback_feedback__sensor_id___fecha__reject_post"];
type RecalibrateOperation = operations["recalibrate_recalibrate__sensor_id__post"];
type ActivePredictorOperation =
  operations["get_active_predictor_models__sensor_id__active_get"];
type OperationResponse<Operation extends { responses: { 200: { content: unknown } } }> =
  Operation["responses"][200]["content"] extends { "application/json": infer Response }
    ? Response
    : never;

export type GeneratedQualityFunctionContracts = [
  Assert<Equal<QualityReport, components["schemas"]["QualityReportResponse"]>>,
  Assert<Equal<QualityReport, QualityResponse>>,
  Assert<Equal<Parameters<typeof getQualityReport>[0], QualitySensorId>>,
  Assert<Equal<ReturnType<typeof getQualityReport>, Promise<QualityResponse | null>>>,
];

export type GeneratedLineageFunctionContracts = [
  Assert<Equal<FeedbackReference, components["schemas"]["FeedbackReferenceSchema"]>>,
  Assert<Equal<LineageEntry, components["schemas"]["LineageEntry"]>>,
  Assert<Equal<LineageResponse, components["schemas"]["LineageResponse"]>>,
  Assert<Equal<LineageResponse, GeneratedLineageResponse>>,
  Assert<Equal<Parameters<typeof getLineage>[0], LineageSensorId>>,
  Assert<Equal<ReturnType<typeof getLineage>, Promise<GeneratedLineageResponse>>>,
];

export type GeneratedLabIngestFunctionContracts = [
  Assert<Equal<LabIngestResult, components["schemas"]["SensorReadingResponse"]>>,
  Assert<Equal<LabIngestResult, GeneratedLabIngestResponse>>,
  Assert<Equal<Parameters<typeof ingestLabReading>[0], LabSensorId>>,
  Assert<Equal<Parameters<typeof ingestLabReading>[1], string>>,
  Assert<Equal<Parameters<typeof ingestLabReading>[2], LabReadingValues>>,
  Assert<Equal<ReturnType<typeof ingestLabReading>, Promise<GeneratedLabIngestResponse>>>,
];

export type GeneratedForecastAliases = [
  Assert<Equal<Verdict, components["schemas"]["Verdict"]>>,
  Assert<Equal<ForecastRunResponse, components["schemas"]["ForecastRunResponse"]>>,
  Assert<Equal<FeedbackRow, components["schemas"]["FeedbackRow"]>>,
  Assert<Equal<FeedbackListResponse, components["schemas"]["FeedbackListResponse"]>>,
  Assert<Equal<RecalibrationResponse, components["schemas"]["RecalibrationResponse"]>>,
  Assert<Equal<ActivePredictor, components["schemas"]["ActivePredictorResponse"]>>,
];

export type GeneratedForecastFunctionContracts = [
  Assert<
    Equal<
      Parameters<typeof runForecast>[0],
      RunForecastOperation["parameters"]["path"]["sensor_id"]
    >
  >,
  Assert<
    Equal<ReturnType<typeof runForecast>, Promise<OperationResponse<RunForecastOperation>>>
  >,
  Assert<
    Equal<
      Parameters<typeof listFeedback>[0],
      ListFeedbackOperation["parameters"]["path"]["sensor_id"]
    >
  >,
  Assert<
    Equal<ReturnType<typeof listFeedback>, Promise<OperationResponse<ListFeedbackOperation>>>
  >,
  Assert<
    Equal<
      Parameters<typeof confirmAlert>,
      [
        ConfirmFeedbackOperation["parameters"]["path"]["sensor_id"],
        ConfirmFeedbackOperation["parameters"]["path"]["fecha"],
      ]
    >
  >,
  Assert<
    Equal<ReturnType<typeof confirmAlert>, Promise<OperationResponse<ConfirmFeedbackOperation>>>
  >,
  Assert<
    Equal<
      Parameters<typeof rejectAlert>,
      [
        RejectFeedbackOperation["parameters"]["path"]["sensor_id"],
        RejectFeedbackOperation["parameters"]["path"]["fecha"],
        RejectFeedbackOperation["requestBody"]["content"]["application/json"]["etiqueta_corregida"],
        RejectFeedbackOperation["requestBody"]["content"]["application/json"]["observacion"],
      ]
    >
  >,
  Assert<
    Equal<ReturnType<typeof rejectAlert>, Promise<OperationResponse<RejectFeedbackOperation>>>
  >,
  Assert<
    Equal<
      Parameters<typeof recalibrate>[0],
      RecalibrateOperation["parameters"]["path"]["sensor_id"]
    >
  >,
  Assert<
    Equal<ReturnType<typeof recalibrate>, Promise<OperationResponse<RecalibrateOperation>>>
  >,
  Assert<
    Equal<
      Parameters<typeof getActivePredictor>[0],
      ActivePredictorOperation["parameters"]["path"]["sensor_id"]
    >
  >,
  Assert<
    Equal<
      ReturnType<typeof getActivePredictor>,
      Promise<OperationResponse<ActivePredictorOperation>>
    >
  >,
];

const withoutOptionalPeriods: QualityReport = {
  sensor_id: "sensor-a",
  total_rows: 0,
  missing_pct: {},
  duplicate_timestamps: [],
  out_of_range: {},
  anomalies_detected: 0,
  anomaly_method: "isolation_forest",
  anomaly_contamination: 0.05,
  anomaly_columns: [],
  is_diagnostic_only: true,
  note: "Sin observaciones suficientes.",
};

const withNullablePeriods: QualityReport = {
  ...withoutOptionalPeriods,
  period_start: null,
  period_end: null,
};

void withoutOptionalPeriods;
void withNullablePeriods;

const withoutOptionalEvidence: LineageEntry = {
  recalibration_id: "recalibration-1",
  source_model_id: "model-a",
  successor_model_id: "model-b",
  feedback_references: [],
  recalibrated_at: "2026-09-06T10:00:00",
  source_trained_through: "2024-10-30",
  successor_trained_through: "2024-10-31",
  lineage_version: 1,
};

const withNullableEvidence: LineageEntry = {
  ...withoutOptionalEvidence,
  dataset_sha256: null,
  mlflow_model_version: null,
};

void withoutOptionalEvidence;
void withNullableEvidence;

const generatedLabRequest: GeneratedLabIngestRequest = {
  timestamp: "2026-04-30T00:00:00Z",
  soil_moisture: 0.31,
  temperature: 22.5,
  relative_humidity: 61,
  precipitation: 0,
  solar_radiation: 18.4,
  wind_speed: 2.3,
  procedencia: "sintetico",
};

void generatedLabRequest;

const forecastWithNullableTargetAndWarning: ForecastRunResponse = {
  verdicts: [{ fecha: "2026-04-30", alerta: true, probabilidad: 0.82, fecha_objetivo: null }],
  train_rows: 100,
  test_rows: 20,
  selection_warning: null,
};
const forecastWithoutOptionalTargetAndWarning: ForecastRunResponse = {
  verdicts: [{ fecha: "2026-04-30", alerta: false, probabilidad: 0.18 }],
  train_rows: 100,
  test_rows: 20,
};
const feedbackWithNullableOptionalEvidence: FeedbackRow = {
  fecha: "2026-04-30",
  alerta_generada: 1,
  estado_validacion: "rechazada",
  etiqueta_corregida: null,
  observacion: null,
  y_proba: null,
  fecha_objetivo: null,
};
const feedbackWithoutOptionalEvidence: FeedbackRow = {
  fecha: "2026-04-30",
  alerta_generada: 1,
  estado_validacion: "confirmada",
};
const activePredictorWithoutOptionalIdentity: ActivePredictor = {
  sensor_id: "sensor-a",
  horizon_days: 7,
  contract_version: 1,
  pipeline_version: "v1",
  feature_columns: [],
  lags: [],
  rolling_windows: [],
  applied_feedback_count: 0,
  applied_feedback_dates: [],
};

void forecastWithNullableTargetAndWarning;
void forecastWithoutOptionalTargetAndWarning;
void feedbackWithNullableOptionalEvidence;
void feedbackWithoutOptionalEvidence;
void activePredictorWithoutOptionalIdentity;

describe("generated operational quality contracts", () => {
  it("keeps the established quality function callable", () => {
    expectTypeOf(getQualityReport).toBeFunction();
    expectTypeOf(getLineage).toBeFunction();
    expectTypeOf(ingestLabReading).toBeFunction();
    expectTypeOf(runForecast).toBeFunction();
    expectTypeOf(listFeedback).toBeFunction();
    expectTypeOf(confirmAlert).toBeFunction();
    expectTypeOf(rejectAlert).toBeFunction();
    expectTypeOf(recalibrate).toBeFunction();
    expectTypeOf(getActivePredictor).toBeFunction();
  });
});
