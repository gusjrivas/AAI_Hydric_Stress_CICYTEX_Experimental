import { PRODUCER_API_BASE_URL } from "../../api/baseUrl";
import type { components, operations } from "../../api/generated/schema";
import { ProducerV2UnavailableError } from "./catalogApi";

export type ReadingVariable =
  | "soil_moisture"
  | "relative_humidity"
  | "solar_radiation"
  | "temperature"
  | "precipitation"
  | "wind_speed"
  | "et0";

export const READING_VARIABLES: ReadingVariable[] = [
  "soil_moisture",
  "temperature",
  "precipitation",
  "relative_humidity",
  "solar_radiation",
  "wind_speed",
  "et0",
];

export type ReadingRow = components["schemas"]["ReadingRow"];
export type VariableCoverage = components["schemas"]["VariableCoverage"];
export type ReadingsResult = components["schemas"]["ReadingsResponse"];

type ReadingsOperation = operations["get_readings_api_v2_sensors__sensor_id__readings_get"];

/** Un sensor desconocido (404 con cuerpo de error v2). */
export class SensorNotFoundError extends Error {
  constructor(sensorId: string) {
    super(`No se encontró el punto de medición «${sensorId}».`);
    this.name = "SensorNotFoundError";
  }
}

export async function getSensorReadings(
  sensorId: ReadingsOperation["parameters"]["path"]["sensor_id"],
  days: NonNullable<NonNullable<ReadingsOperation["parameters"]["query"]>["days"]>,
): Promise<ReadingsOperation["responses"][200]["content"]["application/json"]> {
  const response = await fetch(
    `${PRODUCER_API_BASE_URL}/api/v2/sensors/${encodeURIComponent(sensorId)}/readings?days=${days}`,
  );
  if (response.ok) return response.json();

  let body: unknown = null;
  try {
    body = await response.json();
  } catch {
    body = null;
  }
  const errorCode =
    body && typeof body === "object" && "error" in body
      ? (body as { error?: { code?: string; message?: string } }).error
      : null;

  if (response.status === 404) {
    if (errorCode) throw new SensorNotFoundError(sensorId);
    throw new ProducerV2UnavailableError();
  }
  throw new Error(errorCode?.message ?? "No se pudieron cargar las mediciones. Intentá nuevamente.");
}

export function displayDate(value: string): string {
  return new Intl.DateTimeFormat("es-AR", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" })
    .format(new Date(`${value}T00:00:00Z`));
}

// Etiqueta prevista para datos de reanálisis externo (ERA5-Land + NASA
// POWER, Hito 2 del ensamble): nunca "Fuente real" (no es un sensor físico
// propio) ni "Simulado" (no es sintético) -- una tercera categoría propia.
const EXTERNAL_REANALYSIS_LABEL = "Datos externos de ERA5-Land y NASA POWER";

const PROVENANCE_LABELS: Record<ReadingsResult["provenance"], string> = {
  real: "Datos registrados de la fuente",
  synthetic: "Datos simulados · Solo para demostración",
  external_reanalysis: EXTERNAL_REANALYSIS_LABEL,
  mixed: "Fuentes reales y simuladas combinadas",
  unknown: "Procedencia no identificada",
};

export function provenanceLabel(provenance: ReadingsResult["provenance"]): string {
  return PROVENANCE_LABELS[provenance];
}

const ORIGIN_LABELS: Record<ReadingRow["origin"], string> = {
  real: "Fuente real",
  synthetic: "Simulado",
  external_reanalysis: EXTERNAL_REANALYSIS_LABEL,
  unknown: "No identificado",
};

export function originLabel(origin: ReadingRow["origin"]): string {
  return ORIGIN_LABELS[origin];
}

// El backend expone unidades como códigos estables en inglés (contrato v2,
// api-contract.md), no pensados para mostrarse tal cual a un productor sin
// conocimientos técnicos (bug detectado al verificar contra el backend v2
// real: se veían literalmente "degC"/"mm/day"). Traducción de presentación
// only; si aparece una unidad nueva no mapeada, se muestra el código crudo
// del backend antes que ocultar la unidad.
const UNIT_DISPLAY_LABELS: Record<string, string> = {
  "degC": "°C",
  "mm/day": "mm",
  "MJ/m2/day": "MJ/m²/día",
  "m/s": "m/s",
  "%": "%",
};

function displayUnit(unit: string | undefined): string {
  if (!unit) return "";
  return UNIT_DISPLAY_LABELS[unit] ?? unit;
}

export function formatReadingValue(variable: ReadingVariable, value: number | null, unit: string | undefined): string {
  if (value === null) return "Sin medición";
  if (variable === "soil_moisture") return `${(value * 100).toFixed(1)} %`;
  const suffix = displayUnit(unit);
  return suffix ? `${value.toFixed(1)} ${suffix}` : value.toFixed(1);
}
