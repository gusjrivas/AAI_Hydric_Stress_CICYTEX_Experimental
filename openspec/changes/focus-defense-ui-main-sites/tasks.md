# Tareas y evidencia

- [x] Retirar ruta, montaje y acceso de navegación a CICYTEX.
- [x] Reducir el recorrido a Pergamino, Melchor Romero y laboratorio.
- [x] Cubrir URL antigua, selector de localidades y ausencia de consultas CICYTEX.
- [x] Adaptar las verificaciones de navegador y el ensayo técnico al alcance actual.
- [x] Actualizar README, guía de presentación y especificación.
- [x] `npm test -- --reporter=dot`: 67 archivos, 563 pruebas aprobadas.
- [x] `npm run build`: compilación TypeScript y bundle de producción correctos.
- [x] Build con `VITE_API_BASE_URL=''` para fixtures: correcto.
- [x] `npm run lint`: sin errores; tres advertencias en archivos no modificados
  (`ProducerTabs.tsx` y `HistoricalReplayPage.tsx`).
- [x] `node --test 'scripts/ui/**/*.test.mjs'`: 30 pruebas aprobadas.
- [x] `node --check` de ambos scripts UI y `git diff --check`: correctos.
- [ ] Ejecutar los recorridos en Chrome: no disponible en este entorno; la
  descarga del navegador falló (archivo ZIP inválido). El job existente
  `browser-journeys` de CI queda preparado para comprobarlos.
- [ ] Revisar la grabación con el backend y paquetes reales del autor.

Estas verificaciones no certifican resultados científicos ni el cierre del
Trabajo Final. No se ejecutaron entrenamientos ni se alteró evidencia archivada.
