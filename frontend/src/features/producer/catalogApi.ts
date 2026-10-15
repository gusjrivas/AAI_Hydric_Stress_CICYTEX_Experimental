import { PRODUCER_API_BASE_URL } from "../../api/baseUrl";
import type { components, operations } from "../../api/generated/schema";

export type Sector = components["schemas"]["SectorResponse"];
export type SensorSummary = components["schemas"]["SensorResponse"];
export type SectorListResult = components["schemas"]["SectorListResponse"];
export type SensorListResult = components["schemas"]["SensorListResponse"];

type SectorListOperation = operations["list_sectors_api_v2_sectors_get"];
type SensorListOperation = operations["list_sensors_api_v2_sensors_get"];

/** La fachada v2 no está disponible en este backend (`PRODUCER_V2_ENABLED`
 * desactivado o ruta inexistente): FastAPI responde 404 plano, sin el cuerpo
 * `{error:{code,...}}` del contrato v2. Se distingue de un 404 de recurso
 * desconocido, que sí trae ese cuerpo. */
export class ProducerV2UnavailableError extends Error {
  constructor() {
    super("El catálogo de sectores y sensores todavía no está disponible en este servidor.");
    this.name = "ProducerV2UnavailableError";
  }
}

async function getV2<T>(path: string): Promise<T> {
  const response = await fetch(`${PRODUCER_API_BASE_URL}/api/v2${path}`);
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
  if (response.status === 404 && !errorCode) {
    throw new ProducerV2UnavailableError();
  }
  throw new Error(errorCode?.message ?? "No se pudo consultar el catálogo. Intentá nuevamente.");
}

export async function listSectors(): Promise<
  SectorListOperation["responses"][200]["content"]["application/json"]
> {
  return getV2<SectorListResult>("/sectors");
}

export async function listSensors(
  sectorId?: NonNullable<
    NonNullable<SensorListOperation["parameters"]["query"]>["sector_id"]
  >,
): Promise<SensorListOperation["responses"][200]["content"]["application/json"]> {
  const query = sectorId ? `?sector_id=${encodeURIComponent(sectorId)}` : "";
  return getV2<SensorListResult>(`/sensors${query}`);
}
