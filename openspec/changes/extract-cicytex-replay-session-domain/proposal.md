# Change: Extraer el dominio de sesiones de replay CICYTEX

## Why

El router CICYTEX conserva hoy el modelo mutable, el reloj simulado, el generador
de identificadores, el lock y el diccionario de sesiones. Esa mezcla acopla el
contrato HTTP con estado de aplicación y vuelve difícil probar la transición del
reloj sin levantar FastAPI.

## What Changes

- Introduce un dominio inmutable para la sesión de replay.
- Introduce un caso de uso para crear, consultar, avanzar y reiniciar sesiones.
- Introduce `SessionRepository` y un adaptador in-memory fuera del router.
- Inyecta el caso de uso en FastAPI y elimina `_sessions`, `_lock` y `Session` del
  módulo del router.
- Conserva exactamente rutas, status, payloads, mensajes y ocultamiento del futuro.
- No cambia catálogo, CSV, métricas, feedback, almacenamiento durable, datasets,
  modelos ni resultados científicos.

## Impact

Refactor interno de `historical-replay` y del router CICYTEX. Las corridas de
CICYTEX, Melchor Romero, Pergamino, Laboratorio y Laya permanecen aisladas.
