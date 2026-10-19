/** Mensajes de error para la persona usuaria: capa de presentación, sin cambios de contrato. */
export const NETWORK_ERROR_MESSAGE =
  "No se pudo conectar con el servidor. Verificá que el backend esté en funcionamiento y volvé a intentarlo.";
export const GENERIC_ERROR_MESSAGE = "No se pudo completar la operación.";

/** Textos crudos con que los navegadores reportan un fetch que no llegó al servidor. */
const RAW_NETWORK_FAILURE = /failed to fetch|networkerror when attempting to fetch|load failed|network request failed/i;

/**
 * Traduce los fallos de red del navegador (p. ej. «Failed to fetch») a un mensaje
 * claro en español. Los errores con detalle del servidor se conservan tal cual.
 */
export function userFacingErrorMessage(err: unknown): string {
  if (!(err instanceof Error)) return GENERIC_ERROR_MESSAGE;
  if (err instanceof TypeError && RAW_NETWORK_FAILURE.test(err.message)) return NETWORK_ERROR_MESSAGE;
  return err.message;
}
