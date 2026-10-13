## Why

Las sesiones del replay CICYTEX viven hoy en memoria de un proceso. Un reinicio
pierde el reloj revelado y varios workers pueden aplicar transiciones divergentes.

## What Changes

- Persistir sesiones en SQLite con un esquema v1 cerrado y validado.
- Mantener create/get/advance/reset/feedback y sus payloads HTTP sin cambios.
- Serializar transiciones y `with_session` entre procesos sin perder updates.
- Fallar cerrado y con 503 sanitizado ante almacenamiento inválido o ocupado.

## Impact

El cambio queda limitado al adaptador de `SessionRepository` y al wiring de
dependencias. Router, feedback, datasets, catálogo y corridas científicas no
adquieren dependencias de SQLite.
