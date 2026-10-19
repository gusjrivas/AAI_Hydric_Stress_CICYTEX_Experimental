# Proposal: acciones de revisión con claridad y jerarquía equivalentes (F5)

- HU: HU5/HU6 (UI). Capacidad: `alerting-ui`. Fase CRISP-DM: evaluación.
- Impacto científico: ninguno. No cambia `ReviewRequest`, idempotencia, revisión ni lo que se envía; solo presentación, foco y bloqueo de doble envío.
- Problema: «Confirmar resultado» y «Rechazar resultado» no tenían clase ni descripción común, el foco se perdía al desmontarse o deshabilitarse un control y no había un guard síncrono contra doble envío.
- Cambio: ambos botones con la misma clase, orden fijo, `aria-describedby` común y mínimo táctil de 44 px en pantallas estrechas; sin preselección ni foco inicial; envío bloqueado tras el primer clic con `ref` síncrono; foco a elementos estables (`tabIndex=-1`, `role=status`). El flujo sigue siendo de dos pasos (elegir, luego «Guardar opinión»).
- Límite: el tamaño táctil se verificó leyendo el CSS, no el layout renderizado; no se probó en navegador real.
