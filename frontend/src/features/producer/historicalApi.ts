import { PRODUCER_API_BASE_URL } from "../../api/baseUrl";
import type { components, operations } from "../../api/generated/schema";
import { ProducerV2UnavailableError } from "./catalogApi";
import {
  DemoWriteLockedError,
  ForecastNotFoundError,
  ReviewIdempotencyConflictError,
  ReviewNotOpenError,
  TargetObservationBlockedError,
  isTargetObservationReason,
  RevisionConflictError,
} from "./forecastsApi";
import type { ForecastBatch, ReviewRequest } from "./forecastsApi";

type HistoricalForecastsOperation =
  operations["get_historical_forecasts_api_v2_sensors__sensor_id__historical__as_of_date__forecasts_get"];
type HistoricalReadingsOperation =
  operations["get_historical_readings_api_v2_sensors__sensor_id__historical__as_of_date__readings_get"];
type HistoricalReviewOperation =
  operations["create_historical_review_api_v2_sensors__sensor_id__historical__as_of_date__forecasts__forecast_id__reviews_post"];

type ReviewCreate = components["schemas"]["ReviewCreate"];
type HistoricalForecastsResponse =
  HistoricalForecastsOperation["responses"][200]["content"]["application/json"];
type HistoricalForecastBatch = HistoricalForecastsResponse extends ForecastBatch
  ? ForecastBatch
  : never;
type HistoricalReadingsResponse =
  HistoricalReadingsOperation["responses"][200]["content"]["application/json"];
type HistoricalReviewResponse =
  HistoricalReviewOperation["responses"][201]["content"]["application/json"];

/** Una emisión existe pero corresponde a otra fecha posterior a la
 * navegada: nunca se expone como visible desde una fecha anterior. */
export class ForecastNotVisibleAtThisHistoricalDateError extends Error {
  constructor() {
    super("Esta emisión corresponde a una fecha posterior a la que se está navegando.");
    this.name = "ForecastNotVisibleAtThisHistoricalDateError";
  }
}

/** La fecha de recorrido es anterior a la fecha de emisión seleccionada. */
export class InvalidRevealWindowError extends Error {
  constructor() {
    super("La fecha de recorrido no puede ser anterior a la fecha de emisión.");
    this.name = "InvalidRevealWindowError";
  }
}

/** Ninguna emisión fue preparada para esta fecha histórica. */
export class BatchNotPreparedError extends Error {
  constructor() {
    super("No hay una emisión preparada para esta fecha histórica.");
    this.name = "BatchNotPreparedError";
  }
}

interface ErrorEnvelope {
  code?: string;
  message?: string;
  details?: Record<string, unknown>;
}

async function readErrorEnvelope(response: Response): Promise<ErrorEnvelope | null> {
  let body: unknown = null;
  try {
    body = await response.json();
  } catch {
    return null;
  }
  if (body && typeof body === "object" && "error" in body) {
    return (body as { error?: ErrorEnvelope }).error ?? null;
  }
  return null;
}

function historicalPath(
  sensorId: HistoricalForecastsOperation["parameters"]["path"]["sensor_id"],
  asOfDate: HistoricalForecastsOperation["parameters"]["path"]["as_of_date"],
): string {
  return `${PRODUCER_API_BASE_URL}/api/v2/sensors/${encodeURIComponent(sensorId)}/historical/${asOfDate}`;
}

/** Lectura de solo lectura, nunca dispara inferencia ni emisión: reproduce
 * una emisión ya persistida, seleccionada de forma inequívoca por su fecha
 * de emisión (`asOfDate`), nunca por `target_date`. `revealedThrough`
 * permite avanzar el reloj del recorrido más allá de la emisión (p.ej. para
 * contrastar contra una observación posterior) sin cambiar qué emisión se
 * seleccionó -- afecta únicamente la elegibilidad de revisión calculada por
 * el backend. */
export async function getHistoricalForecastBatch(
  sensorId: HistoricalForecastsOperation["parameters"]["path"]["sensor_id"],
  asOfDate: HistoricalForecastsOperation["parameters"]["path"]["as_of_date"],
  revealedThrough?: NonNullable<
    NonNullable<HistoricalForecastsOperation["parameters"]["query"]>["revealed_through"]
  >,
): Promise<HistoricalForecastBatch> {
  const query = revealedThrough ? `?revealed_through=${revealedThrough}` : "";
  const response = await fetch(`${historicalPath(sensorId, asOfDate)}/forecasts${query}`);
  if (response.ok) return response.json();

  const error = await readErrorEnvelope(response);
  if (response.status === 404) {
    if (error?.code === "batch_not_prepared") throw new BatchNotPreparedError();
    throw new ProducerV2UnavailableError();
  }
  if (error?.code === "invalid_reveal_window") throw new InvalidRevealWindowError();
  throw new Error(error?.message ?? "No se pudo consultar esta emisión histórica. Intentá nuevamente.");
}

/** Observaciones reveladas exactamente hasta `revealedThrough`: nunca una
 * fila posterior. Nunca dispara inferencia. */
export async function getHistoricalReadings(
  sensorId: HistoricalReadingsOperation["parameters"]["path"]["sensor_id"],
  revealedThrough: HistoricalReadingsOperation["parameters"]["path"]["as_of_date"],
  days: NonNullable<
    NonNullable<HistoricalReadingsOperation["parameters"]["query"]>["days"]
  > = 30,
): Promise<HistoricalReadingsResponse> {
  const response = await fetch(`${historicalPath(sensorId, revealedThrough)}/readings?days=${days}`);
  if (response.ok) return response.json();

  const error = await readErrorEnvelope(response);
  if (response.status === 404) throw new ProducerV2UnavailableError();
  throw new Error(error?.message ?? "No se pudieron cargar las mediciones históricas. Intentá nuevamente.");
}

/** Revisión histórica, gateada por el reloj simulado del recorrido
 * (`revealedThrough`), nunca por el reloj real. */
export async function submitHistoricalReview(
  sensorId: HistoricalReviewOperation["parameters"]["path"]["sensor_id"],
  revealedThrough: HistoricalReviewOperation["parameters"]["path"]["as_of_date"],
  forecastId: HistoricalReviewOperation["parameters"]["path"]["forecast_id"],
  request: ReviewRequest,
): Promise<HistoricalReviewResponse> {
  const payload = {
    request_id: request.requestId,
    expected_revision: request.expectedRevision,
    action: request.action,
    comment: request.comment,
  } satisfies ReviewCreate;
  const response = await fetch(`${historicalPath(sensorId, revealedThrough)}/forecasts/${encodeURIComponent(forecastId)}/reviews`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (response.ok) return response.json();

  const error = await readErrorEnvelope(response);
  if (response.status === 404) {
    if (error?.code === "forecast_not_found") throw new ForecastNotFoundError();
    if (error?.code === "forecast_not_visible_at_this_historical_date") throw new ForecastNotVisibleAtThisHistoricalDateError();
    throw new ProducerV2UnavailableError();
  }
  if (response.status === 409) {
    if (error?.code === "review_not_open") {
      const reviewOpenAt = typeof error.details?.review_open_at === "string" ? error.details.review_open_at : null;
      throw new ReviewNotOpenError(reviewOpenAt);
    }
    if (isTargetObservationReason(error?.code)) throw new TargetObservationBlockedError(error.code);
    if (error?.code === "revision_conflict") {
      const actualRevision = typeof error.details?.actual_revision === "number" ? error.details.actual_revision : null;
      throw new RevisionConflictError(actualRevision);
    }
    if (error?.code === "idempotency_conflict") throw new ReviewIdempotencyConflictError();
    if (error?.code === "demo_write_locked") throw new DemoWriteLockedError();
  }
  throw new Error(error?.message ?? "No se pudo guardar la revisión histórica. Intentá nuevamente.");
}
