# Proposal: recorrido histórico compartido (Pergamino y Melchor Romero) con veredicto, acciones y trazabilidad (F5/F6)

- HU: HU6 (UI). Capacidad: `alerting-ui`. Fase CRISP-DM: evaluación.
- Impacto científico: ninguno. No cambia modelos, umbrales, backend, endpoints ni protocolos; no cambia el contenido de los datos mostrados.
- Problema: `HistoricalWalkthrough` no mostraba la decisión como veredicto, no jerarquizaba acciones, no explicaba el avance deshabilitado y no exponía la trazabilidad de la predicción mostrada. La tabla de observaciones no filtraba en el cliente las fechas posteriores al reloj.
- Cambio: veredicto legible, acción primaria y secundaria con nota de fin, sección de trazabilidad con los datos que ya trae el payload (y «no disponible» para SHA-256 del dataset, commit, semilla, corridas MLflow, particiones y linaje de recalibración) y filtro cliente de observaciones futuras.
- Alcance: el componente es compartido; el cambio también se ve en Melchor Romero, con su propia fuente y procedencia por props. No se verificó en navegador real (declarado en tasks).
