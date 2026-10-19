# Proposal: recuperar la sesión CICYTEX al recargar y feedback sin respuesta preseleccionada (F5)

- HU: HU5/HU6 (UI). Capacidad: `alerting-ui`. Fase CRISP-DM: evaluación.
- Impacto científico: ninguno. No cambia backend, modelos, umbrales ni protocolos; el `estado_validacion` enviado no cambia.
- Problema: al recargar se perdía la sesión abierta aunque el servidor la conserva (`GET /sessions/{id}`), y el feedback arrancaba con «Sí, coincide» preseleccionada, lo que induce una respuesta.
- Cambio: registro mínimo en `sessionStorage` {site, session_id, sensor, horizon, emission}, validado contra la sesión del servidor y el catálogo antes de restaurar; solo GET, nunca POST; el borrador de feedback no se persiste. Si no es recuperable se explica y se ofrece «Iniciar otra emisión». Feedback sin elección inicial y envío deshabilitado hasta elegir.
- Límite declarado: el backend no define vencimiento de sesiones; «vencida» se observa como 404 igual que «inexistente». Si se recarga tras cambiar la selección sin abrir otra sesión, se restaura la última sesión abierta.
