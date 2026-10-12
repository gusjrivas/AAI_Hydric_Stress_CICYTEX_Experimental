## 1. TDD y caracterización

- [x] 1.1 Congelar payloads, status y errores HTTP actuales.
- [x] 1.2 Registrar RED de create/get/advance/reset y límite del reloj.
- [x] 1.3 Registrar RED que prohíbe estado de sesiones en el router.
- [x] 1.4 Registrar RED de avance atómico, colisión de ID y validaciones del dominio.
- [x] 1.5 Registrar RED de pureza respecto de transporte, datos y filesystem.
- [x] 1.6 Registrar RED P2 para tipo y orden de `last_observation` sin retroceso del reloj.
- [x] 1.7 Registrar RED para reset concurrente con feedback y límite inyectado de avance.

## 2. Dominio y aplicación

- [x] 2.1 Implementar `ReplaySession` inmutable y el caso de uso de sesiones.
- [x] 2.2 Implementar `SessionRepository` y el adaptador in-memory sincronizado.
- [x] 2.3 Inyectar el caso de uso y traducir errores sin cambiar HTTP.
- [x] 2.4 Mantener feedback fuera del repositorio y distinguir su lock del estado de sesión.
- [ ] 2.5 Revalidar atómicamente el reloj antes de persistir feedback.
- [ ] 2.6 Derivar `can_advance` del mismo límite inyectado que usa `advance`.

## 3. Verificación

- [x] 3.1 Dejar verdes las pruebas unitarias y HTTP de replay CICYTEX.
- [x] 3.2 Ejecutar regresiones CICYTEX, Melchor, Pergamino, Laboratorio y Laya.
- [x] 3.3 Validar formato, lint, OpenSpec y diff-check.
