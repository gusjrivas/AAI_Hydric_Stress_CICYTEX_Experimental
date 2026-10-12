# Diseño: sesión CICYTEX fuera del transporte

## Fronteras

`ReplaySession` representa sensor, emisión, horizonte, inicio y fecha revelada. El
caso de uso es el único dueño de las transiciones create/get/advance/reset y limita
el avance a `2023-07-25`, preservando el comportamiento actual.

`SessionRepository` es un puerto de aplicación. Este slice provee sólo un adaptador
in-memory sincronizado y una dependencia singleton controlada por FastAPI. El router
traduce el error de sesión ausente al mismo HTTP 404 y continúa siendo dueño del
render de CSV, métricas y feedback.

## Compatibilidad

- create mantiene 201 y un identificador hexadecimal de 32 caracteres;
- get, advance y reset mantienen 200;
- una sesión ausente mantiene 404 con `Sesion inexistente`;
- una selección no archivada mantiene 422;
- antes de advance, y nuevamente después de reset, observaciones, outcomes y
  métricas futuras permanecen ocultos;
- el payload público conserva claves, orden lógico y valores actuales.

## Fuera de alcance

No se agrega persistencia durable, recuperación tras reinicio, TTL, feedback en el
repositorio de sesiones, cambios de concurrencia distribuida ni modificación del
paquete causal. Esas decisiones requieren cambios independientes.

