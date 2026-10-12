# Change: Verificación de integridad de artefactos del runtime Laya

Estado: implementado como captura e integridad de bytes foundation-only; no valida
semántica, origen, materialización ni ejecución.

## Why

El manifest de runtime define cinco artefactos por path, tamaño y SHA-256, pero PR15
no observa sus bytes. Antes de interpretar lock, SBOM, configuración o manifests hace
falta una frontera que capture exactamente el bundle declarado y demuestre, de forma
all-or-nothing, que los bytes capturados corresponden a una única identidad de
runtime. La lectura desde filesystem agrega riesgos de symlinks, archivos especiales,
lecturas sin límite y reemplazos TOCTOU que no pertenecen al verificador portable.

## What Changes

- Añade un verificador puro en memoria que recibe un manifest válido y exactamente
  cinco payloads `bytes`, con cobertura idéntica a sus paths contractuales.
- Rechaza discrepancias de tamaño/SHA-256 y punteros Git LFS con terminación LF o
  CRLF, sin aceptar snapshots parciales.
- Produce `laya-runtime-bundle-snapshot-v1`, frozen/slotted, ligado al mismo
  `RuntimeIdentityRef`; conserva los bytes fuera de `repr` y summary público.
- Añade un adapter Linux que recorre root, directorios y archivos mediante
  descriptores relativos con `O_NOFOLLOW`, exige targets regulares y limita cada
  lectura a `size_bytes + 1`.
- Detecta mutaciones durante la lectura mediante `fstat` antes/después y ejecuta un
  sweep final de fingerprints de paths e inodes antes de invocar el verificador
  puro.
- Falla de forma cerrada en Windows o cuando faltan capacidades seguras, y cierra
  todos los descriptores aun ante fallos de cleanup.
- Mantiene falso todo claim semántico, de origen, materialización, executor o
  inferencia y no incorpora ningún caller productivo.

## Impact

El cambio separa dos fronteras: `human_feedback.runtime_bundle` sólo verifica bytes
ya capturados y no realiza I/O; `human_feedback.adapters.filesystem_runtime_bundle`
es la única frontera de filesystem y sólo ofrece captura segura en Linux con las
capacidades requeridas.

El claim es acotado: los cinco bytes capturados coinciden por tamaño y SHA-256 con un
único manifest, y los paths/inodes observados por el adapter coinciden nuevamente en
el sweep final. Esto reduce carreras detectables, pero no es una snapshot atómica del
filesystem ni garantiza que no exista una mutación fuera de las ventanas observadas.

## Deferred

Quedan para PR17 y slices posteriores:

- parsear y validar semántica de lock, SBOM, config, checkpoint manifest y OCI manifest;
- comprobar consistencia lock/SBOM, referencias cruzadas y políticas de supply;
- verificar origen o autenticidad del repositorio, checkpoint o imagen;
- materializar entorno, checkpoint o imagen OCI;
- implementar executor/inferencia o conectar este snapshot con readiness;
- incorporar un caller productivo, shadow review o habilitación operacional.
