import { API_BASE_URL } from "../../api/baseUrl";
import type { components, operations } from "../../api/generated/schema";

export type FeedbackReference = components["schemas"]["FeedbackReferenceSchema"];
export type LineageEntry = components["schemas"]["LineageEntry"];
export type LineageResponse = components["schemas"]["LineageResponse"];

type LineageOperation = operations["get_lineage_lineage__sensor_id__get"];
type LineageSensorId = LineageOperation["parameters"]["path"]["sensor_id"];
type GeneratedLineageResponse =
  LineageOperation["responses"][200]["content"]["application/json"];

/** Un linaje corrupto o incompleto (`LineageValidationError` en el
 * backend) responde 409 y se propaga como excepción explícita — nunca
 * se degrada a cadena vacía.
 */
export const getLineage = async (
  sensorId: LineageSensorId,
): Promise<GeneratedLineageResponse> => {
  const response = await fetch(`${API_BASE_URL}/lineage/${encodeURIComponent(sensorId)}`);
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail ?? `Error al obtener el linaje: ${response.status}`);
  }
  return response.json();
};
