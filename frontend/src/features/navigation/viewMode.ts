import type { RouteId } from "./useHashRoute";

/**
 * Contexto de lectura de una vista. Se deriva sólo de la ruta: no consulta el
 * backend ni cambia estado, de modo que cambiar de vista nunca ejecuta modelos,
 * borra sesiones ni inicia recalibraciones.
 */
export type ViewMode = "operacion" | "replay" | "laboratorio" | "diseno";

export type ViewKey = RouteId | "demo" | "reproduccion-historica";

const MODE_BY_VIEW: Record<ViewKey, ViewMode> = {
  productor: "operacion",
  resumen: "operacion",
  prediccion: "operacion",
  calidad: "operacion",
  linaje: "operacion",
  demo: "laboratorio",
  "laboratorio-sensores": "laboratorio",
  "defensa-pergamino": "replay",
  "defensa-melchor-romero": "replay",
  "defensa-cicytex": "replay",
  "reproduccion-historica": "replay",
  "evidencia-resultados": "diseno",
  evidencia: "diseno",
  arquitectura: "diseno",
};

/** `simulatedSensor`: el sensor activo pertenece al Laboratorio o a la demostración (datos simulados). */
export function modeForView(view: ViewKey, options: { simulatedSensor?: boolean } = {}): ViewMode {
  const mode = MODE_BY_VIEW[view];
  return mode === "operacion" && options.simulatedSensor ? "laboratorio" : mode;
}
