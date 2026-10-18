# Proposal: aislar el borrador de feedback del recorrido CICYTEX (F5)

- HU: HU5/HU6 (UI). Capacidad: `alerting-ui`. Fase CRISP-DM: evaluación.
- Impacto científico: ninguno. No cambia modelos, umbrales, persistencia histórica ni reglas de feedback.
- Problema: la elección y el comentario del borrador vivían a nivel de página; al cambiar sonda, fecha, horizonte o abrir/reiniciar una sesión se conservaban y podían registrarse sobre otra sesión.
- Cambio: el borrador se liga al id de sesión y se descarta al cambiar la selección, abrir otra sesión o reiniciar.
