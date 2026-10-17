import { useEffect, useState } from "react";

export const ROUTES = [
  "resumen",
  "defensa-pergamino",
  "defensa-melchor-romero",
  "defensa-cicytex",
  "laboratorio-sensores",
  "evidencia-resultados",
  "productor",
  "prediccion",
  "calidad",
  "linaje",
  "evidencia",
  "arquitectura",
] as const;
export type RouteId = (typeof ROUTES)[number];

/** Quien abre la app sin ruta es, en primer lugar, un productor: ve «Mi cultivo». */
export const DEFAULT_ROUTE: RouteId = "productor";

export const DESTINATION_LABELS: Record<RouteId, string> = {
  resumen: "Resumen",
  "defensa-pergamino": "Recorrido histórico · Pergamino",
  "defensa-melchor-romero": "Recorrido histórico · Melchor Romero",
  "defensa-cicytex": "Recorrido histórico · CICYTEX",
  "laboratorio-sensores": "Laboratorio · Sensores de prueba",
  "evidencia-resultados": "Evidencia · Resultados y metodología",
  productor: "Mi cultivo",
  prediccion: "Historial y observaciones",
  calidad: "Datos disponibles",
  linaje: "Ajustar próximos pronósticos",
  evidencia: "Acerca de esta herramienta",
  arquitectura: "Arquitectura del sistema",
};

/**
 * Las cinco secciones estables de la navegación principal (Seguimiento histórico, Mi cultivo, Laboratorio, Evidencia y
 * Herramientas técnicas). Cada ruta
 * pertenece a exactamente una: el rediseño reorganiza la entrada, no elimina
 * ni renombra ninguna capacidad ni ningún ancla (`#resumen`, `#calidad`, etc.).
 */
export type NavGroup = "seguimiento" | "cultivo" | "laboratorio" | "evidencia" | "arquitectura" | "herramientas";

export const ROUTE_GROUP: Record<RouteId, NavGroup> = {
  resumen: "herramientas",
  "defensa-pergamino": "seguimiento",
  "defensa-melchor-romero": "seguimiento",
  "defensa-cicytex": "seguimiento",
  "laboratorio-sensores": "laboratorio",
  "evidencia-resultados": "evidencia",
  productor: "cultivo",
  prediccion: "herramientas",
  calidad: "herramientas",
  linaje: "herramientas",
  evidencia: "herramientas",
  arquitectura: "arquitectura",
};

export const TOOL_ROUTES: readonly RouteId[] = ROUTES.filter((id) => ROUTE_GROUP[id] === "herramientas");

/**
 * Pestañas de «Herramientas técnicas». «Resumen» e «Historial y observaciones»
 * se presentan como una sola entrada («Resumen e historial») con un
 * selector interno; `#prediccion` sigue siendo un ancla válida.
 */
export const TOOL_NAV_ROUTES: readonly RouteId[] = ["resumen", "calidad", "linaje", "evidencia"];
export const TOOL_NAV_LABELS: Partial<Record<RouteId, string>> = { resumen: "Resumen e historial" };
export const SUMMARY_PAIR: readonly RouteId[] = ["resumen", "prediccion"];

function parseRoute(hash: string): RouteId {
  const id = hash.replace(/^#/, "");
  // `#demo` y `#reproduccion-historica` son vistas de Herramientas técnicas fuera del ruteo principal.
  if (id === "demo" || id === "reproduccion-historica") return "resumen";
  return (ROUTES as readonly string[]).includes(id) ? (id as RouteId) : DEFAULT_ROUTE;
}

/**
 * Ruteo por hash entre los destinos (task 2.1 de
 * improve-alerting-ui-decision-workflow). Deliberadamente no se suma un
 * router de terceros: son vistas locales y el navegador ya resuelve
 * Atrás/Adelante sobre cambios de `location.hash`.
 */
export function useHashRoute(): RouteId {
  const [route, setRoute] = useState<RouteId>(() => parseRoute(window.location.hash));

  useEffect(() => {
    function onHashChange() {
      setRoute(parseRoute(window.location.hash));
    }
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, []);

  return route;
}
