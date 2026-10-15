import { API_BASE_URL } from "../../api/baseUrl";
import type { components, operations } from "../../api/generated/schema";
import type { LabReadingValues } from "./readingGenerator";

export type LabIngestResult = components["schemas"]["SensorReadingResponse"];

type LabIngestOperation = operations["ingest_reading_sensors__sensor_id__readings_post"];
type LabSensorId = LabIngestOperation["parameters"]["path"]["sensor_id"];
type LabIngestRequest = LabIngestOperation["requestBody"]["content"]["application/json"];
type GeneratedLabIngestResponse =
  LabIngestOperation["responses"][200]["content"]["application/json"];

/** Ingesta una lectura sintética del laboratorio contra el endpoint real
 * de ingesta (`POST /sensors/{sensor_id}/readings`, ADR-0007/0008) --
 * nunca un almacenamiento paralelo propio del laboratorio. `procedencia`
 * queda fija en "sintetico": nunca se declara "real" una lectura
 * generada por este módulo. */
export const ingestLabReading = async (
  sensorId: LabSensorId,
  isoDate: string,
  values: LabReadingValues,
): Promise<GeneratedLabIngestResponse> => {
  const payload = {
    timestamp: `${isoDate}T00:00:00Z`,
    soil_moisture: values.soil_moisture,
    temperature: values.temperature,
    relative_humidity: values.relative_humidity,
    precipitation: values.precipitation,
    solar_radiation: values.solar_radiation,
    wind_speed: values.wind_speed,
    procedencia: "sintetico",
  } satisfies LabIngestRequest;
  const response = await fetch(`${API_BASE_URL}/sensors/${encodeURIComponent(sensorId)}/readings`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail ?? `Error al ingerir una lectura sintética: ${response.status}`);
  }
  return response.json();
};
