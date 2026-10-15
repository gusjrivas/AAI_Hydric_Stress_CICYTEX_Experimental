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

describe("generated operational quality contracts", () => {
  it("keeps the established quality function callable", () => {
    expectTypeOf(getQualityReport).toBeFunction();
    expectTypeOf(getLineage).toBeFunction();
    expectTypeOf(ingestLabReading).toBeFunction();
  });
});
