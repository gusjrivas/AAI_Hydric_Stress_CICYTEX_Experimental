# Proposal: laboratorio de sensores — defectos de lectura y verificación a 360 px (F5)

- HU: HU6 (UI). Capacidad: `alerting-ui`. Fase CRISP-DM: evaluación. Impacto científico: ninguno; solo presentación. Los datos y la revisión siguen declarados sintéticos y el reloj ficticio.
- Problemas observados en render real (#57): la nota «Cómo revisar» ocupaba media pantalla a 1366 px; el panel de trazabilidad repetía «no disponible en este recorrido» cinco veces; a 1366 px el motivo de bloqueo de fila caía en una pista de 6 px y se partía palabra por palabra.
- Cambio: ancho útil para la nota; una sola declaración que nombra los cinco artefactos no disponibles; el motivo de bloqueo ocupa el ancho de la tarjeta. Script reproducible `scripts/ui/capture-lab.mjs` y seis capturas en `docs/design/capturas/lab-*.png`.
- Pendientes declarados (fuera de los archivos del laboratorio): selects de filtro de 36 px y `summary` de 21 px frente al umbral de 44 px; enlace «Ir al Laboratorio» de 20 px en el estado de error; mensaje crudo «Failed to fetch» en inglés; el estado con el backend realmente apagado no se probó (solo POST bloqueados).
