# Proposal: el campo «Recorrido hasta» muestra el reloj efectivo desde el inicio (F5)

- HU: HU6 (UI). Capacidad: `alerting-ui`. Fase CRISP-DM: evaluación. Impacto científico: ninguno (solo lo que muestra el campo; la consulta a la API no cambia).
- Problema: verificación visual renderizada de Pergamino mostró el campo vacío («dd/mm/aaaa») en el estado inicial, aunque el reloj efectivo ya era la fecha de emisión.
- Cambio: el campo muestra el reloj efectivo. Los tests existentes que escribían en el campo vacío usan `fireEvent.change`.
- Evidencia de la verificación: capturas de headless Chrome contra el backend `producer_v2` real, no versionadas (scratchpad de la sesión).
