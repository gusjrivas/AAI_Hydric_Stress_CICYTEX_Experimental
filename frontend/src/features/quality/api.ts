import { API_BASE_URL } from "../../api/baseUrl";
import type { components, operations } from "../../api/generated/schema";

export type QualityReport = components["schemas"]["QualityReportResponse"];

type QualityOperation = operations["get_quality_report_quality__sensor_id__get"];
type QualitySensorId = QualityOperation["parameters"]["path"]["sensor_id"];
type QualityResponse = QualityOperation["responses"][200]["content"]["application/json"];

/** `null` cuando el sensor todavía no tiene dataset ingerido (404) — un
 * estado vacío legítimo, no un error. Cualquier otra respuesta no-ok
 * lanza una excepción con el detalle del backend.
 */
export const getQualityReport = async (
  sensorId: QualitySensorId,
): Promise<QualityResponse | null> => {
  const response = await fetch(`${API_BASE_URL}/quality/${encodeURIComponent(sensorId)}`);
  if (response.status === 404) {
    return null;
  }
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail ?? `Error al obtener la calidad de datos: ${response.status}`);
  }
  return response.json();
};
