## 1. TDD y caracterización

- [x] 1.1 Congelar payloads, status y errores HTTP actuales.
- [x] 1.2 Registrar RED de create/get/advance/reset y límite del reloj.
- [x] 1.3 Registrar RED que prohíbe estado de sesiones en el router.
- [x] 1.4 Registrar RED de avance atómico, colisión de ID y validaciones del dominio.
- [x] 1.5 Registrar RED de pureza respecto de transporte, datos y filesystem.
- [x] 1.6 Registrar RED P2 para tipo y orden de `last_observation` sin retroceso del reloj.

## 2. Dominio y aplicación

- [ ] 2.1 Implementar `ReplaySession` inmutable y el caso de uso de sesiones.
- [ ] 2.2 Implementar `SessionRepository` y el adaptador in-memory sincronizado.
- [ ] 2.3 Inyectar el caso de uso y traducir errores sin cambiar HTTP.
- [ ] 2.4 Mantener feedback fuera del repositorio y distinguir su lock del estado de sesión.

## 3. Verificación

- [ ] 3.1 Dejar verdes las pruebas unitarias y HTTP de replay CICYTEX.
- [ ] 3.2 Ejecutar regresiones CICYTEX, Melchor, Pergamino, Laboratorio y Laya.
- [ ] 3.3 Validar formato, lint, OpenSpec y diff-check.
