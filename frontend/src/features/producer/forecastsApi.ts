import { PRODUCER_API_BASE_URL } from "../../api/baseUrl";
import type { components, operations } from "../../api/generated/schema";
import { ProducerV2UnavailableError } from "./catalogApi";

type ListForecastsOperation =
  operations["list_forecasts_api_v2_sensors__sensor_id__forecasts_get"];
type GetForecastOperation =
  operations["get_forecast_api_v2_sensors__sensor_id__forecasts__forecast_id__get"];
type CreateReviewOperation =
  operations["create_review_api_v2_sensors__sensor_id__forecasts__forecast_id__reviews_post"];
type CreateForecastsOperation =
  operations["create_forecasts_api_v2_sensors__sensor_id__forecasts_post"];

type ReviewCreate = components["schemas"]["ReviewCreate"];
type EmissionRequest = components["schemas"]["EmissionRequest"];
type IdempotencyKey =
  CreateForecastsOperation["parameters"]["header"]["idempotency-key"];
type Expand<Type> = { [Key in keyof Type]: Type[Key] };

export type EventThreshold = components["schemas"]["EventThreshold"];
export type ModelReference = Pick<
  components["schemas"]["ModelReference"],
  | "model_version"
  | "horizon_days"
  | "contract_version"
  | "trained_through"
  | "calibration_version"
  | "assessment_reference"
>;
export type LatestReview = components["schemas"]["LatestReview"];
export type ForecastReview =
  CreateReviewOperation["responses"][201]["content"]["application/json"];
export type ReviewStatus = ForecastReview["status"];
export type ReviewAction = ReviewCreate["action"];
export type TrainingEligibility = ForecastReview["training_eligibility"];

/** Motivos por los que una revisión no está habilitada. Los tres `target_*`
 * solo los informa el recorrido histórico (observación de la variable
 * objetivo imputada, ausente o de procedencia no verificada). */
export type ReviewBlockedReason = NonNullable<ForecastReview["blocked_reason"]>;

export const TARGET_OBSERVATION_MESSAGES: Partial<Record<ReviewBlockedReason, string>> = {
  target_observation_imputed:
    "No se puede revisar este pronóstico con el dato disponible: el valor del día objetivo fue imputado y no es una observación independiente.",
  target_observation_missing:
    "No se puede revisar este pronóstico: no hay una observación disponible para el día objetivo.",
  target_observation_unverified:
    "No se puede revisar este pronóstico: la procedencia del valor del día objetivo no está verificada.",
};

export function isTargetObservationReason(value: unknown): value is ReviewBlockedReason {
  return typeof value === "string" && value in TARGET_OBSERVATION_MESSAGES;
}

type GeneratedEnsembleVote = components["schemas"]["EnsembleComponentVote"];
type GeneratedEnsemble = components["schemas"]["EnsembleDetail"];
type GeneratedForecast =
  GetForecastOperation["responses"][200]["content"]["application/json"];

export type EnsembleFamily = GeneratedEnsembleVote["family"];
export type AgreementCategory = GeneratedEnsemble["agreement_category"];
export type EnsembleComponentVote = Expand<
  Omit<GeneratedEnsembleVote, "model_reference"> & {
    model_reference: ModelReference;
  }
>;
export type EnsembleDetail = Expand<
  Omit<GeneratedEnsemble, "weights" | "components"> & {
    weights: Record<EnsembleFamily, number>;
    components: EnsembleComponentVote[];
  }
>;
export type Forecast = Expand<
  Omit<GeneratedForecast, "ensemble" | "model_reference"> & {
    ensemble: EnsembleDetail | null;
    model_reference: ModelReference;
  }
>;

const FAMILY_LABELS: Record<EnsembleFamily, string> = {
  logistic_regression: "Regresión logística",
  random_forest: "Random Forest",
  hist_gradient_boosting_classifier: "HistGradientBoosting",
};

export function familyLabel(family: EnsembleFamily): string {
  return FAMILY_LABELS[family];
}

/** El acuerdo es una dimensión distinta de la alerta combinada: cuántos de
 * los 3 modelos individuales coinciden, nunca una confianza ni una encuesta
 * que reemplace `combined_alert`. */
const AGREEMENT_LABELS: Record<AgreementCategory, string> = {
  alerta_por_unanimidad: "Los 3 modelos coinciden en la alerta",
  posible_alerta_acuerdo_parcial: "2 de 3 modelos indican alerta",
  sin_alerta_por_mayoria_con_discrepancia: "1 de 3 modelos indica alerta",
  sin_alerta_por_unanimidad: "Los 3 modelos coinciden en que no hay alerta",
}

export function agreementLabel(ensemble: EnsembleDetail): string {
  return AGREEMENT_LABELS[ensemble.agreement_category];
}

export function agreementVotesLabel(ensemble: EnsembleDetail): string {
  return `${ensemble.positive_votes} de ${ensemble.components.length} modelos indican alerta`;
}

type ForecastListQuery = NonNullable<ListForecastsOperation["parameters"]["query"]>;
type GeneratedForecastList =
  ListForecastsOperation["responses"][200]["content"]["application/json"];

export type ForecastListFilters = {
  targetFrom?: NonNullable<ForecastListQuery["target_from"]>;
  targetTo?: NonNullable<ForecastListQuery["target_to"]>;
  horizonDays?: NonNullable<ForecastListQuery["horizon_days"]> & Forecast["horizon_days"];
  reviewStatus?: NonNullable<ForecastListQuery["review_status"]> & ReviewStatus;
  limit?: NonNullable<ForecastListQuery["limit"]>;
  cursor?: NonNullable<ForecastListQuery["cursor"]>;
};
export type ForecastListResult = Expand<
  Omit<GeneratedForecastList, "items"> & { items: Forecast[] }
>;

/** Emisión o revisión inexistente para este sensor (404 con cuerpo v2). */
export class ForecastNotFoundError extends Error {
  constructor() {
    super("No se encontró ese pronóstico para este punto de medición.");
    this.name = "ForecastNotFoundError";
  }
}

/** La revisión todavía no está habilitada (apertura UTC no alcanzada). */
export class ReviewNotOpenError extends Error {
  reviewOpenAt: string | null;
  constructor(reviewOpenAt: string | null) {
    super("Todavía no se puede revisar este resultado.");
    this.name = "ReviewNotOpenError";
    this.reviewOpenAt = reviewOpenAt;
  }
}

/** El backend rechazó (409) la revisión histórica porque la observación del
 * día objetivo es imputada, ausente o de procedencia no verificada. */
export class TargetObservationBlockedError extends Error {
  reason: ReviewBlockedReason;
  constructor(reason: ReviewBlockedReason) {
    super(TARGET_OBSERVATION_MESSAGES[reason] ?? "No se puede revisar este pronóstico.");
    this.name = "TargetObservationBlockedError";
    this.reason = reason;
  }
}

/** Otra opinión ya avanzó la revisión: no se sobrescribe. */
export class RevisionConflictError extends Error {
  actualRevision: number | null;
  constructor(actualRevision: number | null) {
    super("Se registró otra opinión mientras completabas este formulario.");
    this.name = "RevisionConflictError";
    this.actualRevision = actualRevision;
  }
}

/** El mismo request_id ya se usó con un contenido distinto: no se reintenta
 * como si fuera el mismo envío. */
export class ReviewIdempotencyConflictError extends Error {
  constructor() {
    super("Este envío no coincide con un intento anterior con el mismo identificador.");
    this.name = "ReviewIdempotencyConflictError";
  }
}

/** Reserva permanente del espacio demo- (decisiones de dependencias v2). */
export class DemoWriteLockedError extends Error {
  constructor() {
    super("Este punto de medición pertenece a la demostración y no admite revisiones acá.");
    this.name = "DemoWriteLockedError";
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

export class ForecastCursorExpiredError extends Error {
  constructor() { super("La lista cambió. Volvé a cargarla para seguir viendo resultados."); this.name = "ForecastCursorExpiredError"; }
}

function forecastsPath(
  sensorId: ListForecastsOperation["parameters"]["path"]["sensor_id"],
): string {
  return `${PRODUCER_API_BASE_URL}/api/v2/sensors/${encodeURIComponent(sensorId)}/forecasts`;
}

export async function listForecasts(
  sensorId: ListForecastsOperation["parameters"]["path"]["sensor_id"],
  filters: ForecastListFilters = {},
): Promise<ForecastListResult> {
  const query = new URLSearchParams();
  if (filters.targetFrom) query.set("target_from", filters.targetFrom);
  if (filters.targetTo) query.set("target_to", filters.targetTo);
  if (filters.horizonDays) query.set("horizon_days", String(filters.horizonDays));
  if (filters.reviewStatus) query.set("review_status", filters.reviewStatus);
  if (filters.limit) query.set("limit", String(filters.limit));
  if (filters.cursor) query.set("cursor", filters.cursor);
  const qs = query.toString();
  const response = await fetch(`${forecastsPath(sensorId)}${qs ? `?${qs}` : ""}`);
  if (response.ok) return response.json();

  const error = await readErrorEnvelope(response);
  if (response.status === 404 && !error) throw new ProducerV2UnavailableError();
  if (error?.code === "invalid_cursor") throw new ForecastCursorExpiredError();
  if (error?.code === "invalid_date_range") throw new Error("La fecha inicial debe ser anterior o igual a la fecha final.");
  throw new Error("No se pudieron consultar los pronósticos. Intentá nuevamente.");
}

export async function getForecast(
  sensorId: GetForecastOperation["parameters"]["path"]["sensor_id"],
  forecastId: GetForecastOperation["parameters"]["path"]["forecast_id"],
): Promise<Forecast> {
  const response = await fetch(`${forecastsPath(sensorId)}/${encodeURIComponent(forecastId)}`);
  if (response.ok) return response.json();

  const error = await readErrorEnvelope(response);
  if (response.status === 404) {
    if (error?.code === "forecast_not_found") throw new ForecastNotFoundError();
    throw new ProducerV2UnavailableError();
  }
  throw new Error(error?.message ?? "No se pudo consultar este pronóstico. Intentá nuevamente.");
}

export type ReviewRequest = {
  requestId: ReviewCreate["request_id"];
  expectedRevision: ReviewCreate["expected_revision"];
  action: ReviewCreate["action"];
  comment: Exclude<ReviewCreate["comment"], undefined>;
};

export async function submitReview(
  sensorId: CreateReviewOperation["parameters"]["path"]["sensor_id"],
  forecastId: CreateReviewOperation["parameters"]["path"]["forecast_id"],
  request: ReviewRequest,
): Promise<ForecastReview> {
  const payload = {
    request_id: request.requestId,
    expected_revision: request.expectedRevision,
    action: request.action,
    comment: request.comment,
  } satisfies ReviewCreate;
  const response = await fetch(`${forecastsPath(sensorId)}/${encodeURIComponent(forecastId)}/reviews`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (response.ok) return response.json();

  const error = await readErrorEnvelope(response);
  if (response.status === 404) {
    if (error?.code === "forecast_not_found") throw new ForecastNotFoundError();
    throw new ProducerV2UnavailableError();
  }
  if (response.status === 409) {
    if (error?.code === "review_not_open") {
      const reviewOpenAt = typeof error.details?.review_open_at === "string" ? error.details.review_open_at : null;
      throw new ReviewNotOpenError(reviewOpenAt);
    }
    if (error?.code === "revision_conflict") {
      const actualRevision =
        typeof error.details?.actual_revision === "number" ? error.details.actual_revision : null;
      throw new RevisionConflictError(actualRevision);
    }
    if (error?.code === "idempotency_conflict") throw new ReviewIdempotencyConflictError();
    if (error?.code === "demo_write_locked") throw new DemoWriteLockedError();
  }
  throw new Error(error?.message ?? "No se pudo guardar la revisión. Intentá nuevamente.");
}

export function newRequestId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `req-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export function displayForecastDate(value: string): string {
  return new Intl.DateTimeFormat("es-AR", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" }).format(
    new Date(`${value}T00:00:00Z`),
  );
}

export function displayIssuedAt(value: string): string {
  return new Intl.DateTimeFormat("es-AR", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "UTC",
  }).format(new Date(value));
}

const REVIEW_STATUS_LABELS: Record<ReviewStatus, string> = {
  pending: "Pendiente de revisar",
  confirmed: "Confirmado por vos",
  rejected: "Rechazado por vos",
};

export function reviewStatusLabel(status: ReviewStatus): string {
  return REVIEW_STATUS_LABELS[status];
}

/** El contrato prohíbe mostrar `score` como porcentaje: es una puntuación
 * interna del clasificador, no una probabilidad apta para publicarse.
 * `display_probability` es lo único que puede mostrarse como porcentaje, y
 * solo cuando el backend lo publica (gate de calibración aprobado). */
export function displayProbability(forecast: Forecast): string {
  if (forecast.display_probability === null) return "Probabilidad no disponible";
  return `${Math.round(forecast.display_probability * 100)} %`;
}

type GeneratedAvailableSlot = components["schemas"]["AvailableForecastSlot"];
type GeneratedUnavailableSlot = components["schemas"]["UnavailableForecastSlot"];
type GeneratedForecastBatch =
  CreateForecastsOperation["responses"][200 | 201]["content"]["application/json"];

export type ForecastSlot =
  | (Forecast & Pick<GeneratedAvailableSlot, "status">)
  | Pick<
      GeneratedUnavailableSlot,
      "horizon_days" | "target_date" | "status" | "reason_code"
    >;
export type ForecastBatch = Expand<
  Pick<
    GeneratedForecastBatch,
    | "batch_id"
    | "revision"
    | "as_of_date"
    | "data_age_days"
    | "server_today"
    | "provenance"
    | "calendar_timezone"
  > & { slots: ForecastSlot[] }
>;
export async function emitForecasts(
  sensorId: CreateForecastsOperation["parameters"]["path"]["sensor_id"],
  requestId: IdempotencyKey,
): Promise<ForecastBatch> {
  const emissionRequest = {} satisfies EmissionRequest;
  const idempotencyKey: IdempotencyKey = requestId;
  const response = await fetch(forecastsPath(sensorId), {
    method: "POST",
    headers: { "Content-Type": "application/json", "Idempotency-Key": idempotencyKey },
    body: JSON.stringify(emissionRequest),
  });
  if (response.ok) return response.json();
  const error = await readErrorEnvelope(response);
  const messages: Record<string, string> = {
    issued_snapshot_conflict: "Las mediciones de ese día cambiaron. Conservamos el pronóstico anterior; hace falta revisar los datos.",
    demo_write_locked: "Este punto pertenece a la demostración anterior y no permite generar pronósticos aquí.",
    future_readings: "Hay mediciones con fechas futuras. Revisá sus fechas antes de continuar.",
    invalid_calendar: "Hay fechas de medición inconsistentes. Es necesario revisarlas.",
    sensor_not_found: "Este punto de medición ya no está disponible.",
  };
  if (response.status === 404 && !error) throw new ProducerV2UnavailableError();
  throw new Error(messages[error?.code ?? ""] ?? "No pudimos recuperar el resultado. Reintentá para consultar el mismo pedido.");
}

export interface AlertOutlookSummary {
  alert: boolean;
  /** Fechas con alerta, ya formateadas ("lunes 28" style), en orden. Vacío
   * cuando `alert` es false. */
  days: string[];
}

/** Resumen de la parte superior de "Mi cultivo": nunca recalcula
 * `combined_alert`, solo agrupa los `alert: true` ya decididos por el
 * backend en cada horizonte disponible. `null` cuando no hay ningún
 * horizonte disponible (para mostrar el aviso de información insuficiente
 * en su lugar, nunca "sin alerta"). */
export function alertOutlookSummary(batch: ForecastBatch): AlertOutlookSummary | null {
  const available = batch.slots.filter((slot) => slot.status === "available") as (Forecast & { status: "available" })[];
  if (available.length === 0) return null;
  const alerted = available.filter((slot) => slot.alert);
  return {
    alert: alerted.length > 0,
    days: alerted.map((slot) => displayForecastDate(slot.target_date)),
  };
}
