# Proposal: verificación en navegador real del recorrido CICYTEX (F7)

- HU: HU6 (UI). Capacidad: `alerting-ui`. Fase CRISP-DM: evaluación.
- Impacto científico: ninguno. No cambia modelos, umbrales, protocolos ni resultados históricos.
- Problema: la resiliencia del recorrido sólo estaba probada con pruebas de componente; faltaba evidencia en un navegador real (desconexión, recuperación, recarga, permisos por estado, foco por teclado).
- Cambio: script reproducible sin dependencias nuevas (`scripts/ui/verify-journeys.mjs`, Chrome por CDP), configuración de vite con proxy para verificación y documento `docs/design/f7-verificacion-navegador.md` con resultados, capturas y límites. Se declara que la sesión no se rehidrata al recargar.
