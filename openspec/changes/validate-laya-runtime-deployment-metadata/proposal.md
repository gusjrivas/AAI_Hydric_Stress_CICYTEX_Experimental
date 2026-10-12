# Change: Validación local de metadata de despliegue Laya

Estado: implementado como conformidad sintáctico-semántica de metadata capturada;
no acredita licencia, procedencia, compatibilidad, bytes externos ni ejecución.

## Why

PR16 demuestra que cinco blobs capturados coinciden con un manifest de runtime, pero
no interpreta `runtime_config` ni `checkpoint_manifest`. Antes de verificar supply o
materializar Laya hace falta una frontera pura que rechace JSON ambiguo, fije un
perfil local exacto y compruebe que ambos documentos se enlazan entre sí y con el
bundle sellado.

El término `semantics_verified` sería peligroso si se leyera como evidencia externa.
En este cambio significa exclusivamente que la metadata satisface el schema y perfil
local declarados y que sus enlaces internos son coherentes. No convierte una
declaración en prueba de que el repositorio, revisión, licencia, archivos o entorno
sean auténticos, compatibles o ejecutables.

## What Changes

- Define `laya-runtime-config-v1`, `laya-checkpoint-manifest-v1` y evidencia combinada
  `laya-runtime-deployment-evidence-v1`.
- Parsea sólo bytes UTF-8 JSON con schemas cerrados, claves únicas, números finitos y
  límites previos de 16 KiB para config y 64 KiB para checkpoint manifest.
- Limita el array de checkpoint a cardinalidad exactamente cinco antes de parsear
  elementos y fija roles, paths, SHA-256 y tamaños declarados del perfil local.
- Fija entrypoint, runtime, ambiente offline y la identidad declarada del modelo
  `convaiinnovations/laya` en una revisión y subfolder concretos.
- Combina exclusivamente bytes del snapshot PR16 y valida enlaces internos:
  identidad runtime config↔manifest, modelo config↔checkpoint y digest config↔bytes
  capturados del checkpoint manifest.
- Produce objetos sealed/frozen/slotted y un summary público que excluye metadata
  privada, environment, paths y digests de checkpoint.
- Mantiene falsos todos los claims no demostrados: lock/SBOM, bytes de checkpoint,
  OCI, origen, materialización, executor e inferencia.

## Impact

El módulo es puro y no realiza filesystem, red, subprocess, Docker ni carga de
modelo. No se conecta con adapters, backend, readiness, runners o scripts. PR14 y
los summaries de PR16 permanecen sin cambios.

`convaiinnovations/laya` se admite únicamente como identidad declarada dentro de
metadata no operativa. Esto reconcilia PR15: no sustituye a
`NandhaKishorM/laya@68804629e8ccd9d616d48a40e87de9fabbeae069` como source del
runtime y no supera la revisión todavía pendiente de licencia, procedencia/origen,
compatibilidad y bytes del checkpoint. Mientras esa revisión no exista, uso,
materialización e inferencia continúan bloqueados.

## Deferred

Quedan expresamente fuera de PR17:

- validar licencia, procedencia, origen o autenticidad de `convaiinnovations/laya`;
- probar compatibilidad real entre checkpoint, Laya 0.4.2, Python y plataforma;
- descargar o verificar bytes de los cinco archivos de checkpoint declarados;
- interpretar/verificar lock, SBOM u OCI y su consistencia;
- materializar filesystem, entorno, checkpoint o imagen;
- crear executor, ejecutar inferencia o habilitar readiness/shadow/producción.
