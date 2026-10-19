import { PRODUCER_API_BASE_URL } from "../../api/baseUrl";
import type { components, operations } from "../../api/generated/schema";

type ProvenanceOperation =
  operations["get_batch_provenance_api_v2_sensors__sensor_id__batches__batch_id__provenance_get"];

export type BatchProvenance =
  ProvenanceOperation["responses"][200]["content"]["application/json"];
export type CodeIdentity = components["schemas"]["CodeIdentity"];

/** Procedencia de solo lectura de una emisión (lista blanca de identidad).
 * Nunca dispara emisión ni inferencia. */
export async function getBatchProvenance(
  sensorId: ProvenanceOperation["parameters"]["path"]["sensor_id"],
  batchId: ProvenanceOperation["parameters"]["path"]["batch_id"],
): Promise<BatchProvenance> {
  const response = await fetch(
    `${PRODUCER_API_BASE_URL}/api/v2/sensors/${encodeURIComponent(sensorId)}/batches/${encodeURIComponent(batchId)}/provenance`,
  );
  if (response.ok) return response.json();
  let message: string | undefined;
  try {
    const body: unknown = await response.json();
    if (body && typeof body === "object" && "error" in body) {
      const error = (body as { error?: { message?: unknown } }).error;
      if (typeof error?.message === "string") message = error.message;
    }
  } catch {
    // cuerpo no JSON: se usa el mensaje genérico
  }
  throw new Error(message ?? "No se pudo consultar la procedencia de la emisión. Intentá nuevamente.");
}
