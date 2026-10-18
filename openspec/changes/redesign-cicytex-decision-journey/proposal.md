# Proposal: recorrido visual integral de CICYTEX (F5, corte visual)

- HU: HU6 (UI). Capacidad: `alerting-ui`. Fase CRISP-DM: despliegue/evaluación.
- Impacto científico: ninguno. No cambia modelos, umbrales, datos, protocolo ni contratos de la API; no revela observaciones futuras.
- Recorrido representativo elegido: CICYTEX (ya endurecido en #48/#51, con gráfico, tablas, decisión y feedback). Los otros sitios conservan sus protocolos y se tratan después de revisar el resultado.

## Cambios
1. La acción principal "Día siguiente" y la secundaria "Reiniciar" pasan a la tarjeta de decisión.
2. El gráfico tiene escala (mín./máx. y unidad), fechas de inicio y fin, marca del último punto revelado y un resumen textual de la última observación contra el P20.
3. El detalle por método es divulgación progresiva (abierto por defecto).
4. La comparación acumulada sin objetivos revelados muestra una explicación en lugar de una tabla vacía.
5. Alineación de las opciones de feedback y tamaños de texto del gráfico en viewport estrecho.

## Evidencia visual
`docs/design/capturas/cicytex-{antes,despues}-{desktop,narrow}.png`, generadas con `scripts/ui/capture-view.mjs` (Chrome por CDP, sin dependencias) contra el frontend con proxy al backend CICYTEX. El estado "antes" es la emisión recién abierta y el "después" tiene un día avanzado; no son el mismo estado de la sesión.
