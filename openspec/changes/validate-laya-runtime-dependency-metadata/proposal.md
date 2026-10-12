# Change: Validación exacta de lock y SBOM del runtime Laya

Estado: implementado como evidencia local de un perfil de dependencias concreto;
no acredita instalación, origen, firma, licencia, seguridad ni ejecución.

## Why

PR16 verificó bytes y PR17 interpretó config/checkpoint manifest, pero lock y SBOM
seguían opacos. Para que la cadena sea auditable hace falta congelar cómo se generó
el perfil, validar exhaustivamente sus dos artefactos y demostrar que inventario,
fuentes y aristas activadas coinciden, sin promover esas comprobaciones locales a
garantías universales de uv, CycloneDX o del runtime materializado.

## What Changes

- Incorpora un `uv.lock` determinista generado con uv 0.12.3 para CPython 3.11.10,
  Linux x86_64 CPU, cutoff `2026-10-10T09:19:05Z`, Laya commit exacto sin firma,
  extra `serve`, Torch `2.14.0+cpu` y constraint `setuptools==84.0.0`.
- Fija los bytes del lock en 37.599 y SHA-256
  `e968771680b9c6e683163230ebd98b43541325ccb36d6959d1f9ed5565bd5526`.
- Incorpora un SBOM determinista CycloneDX 1.6 generado con cdxgen 13.3.0, 65.198
  bytes y SHA-256
  `f2fde1a342990e3b5b4d74d4930bf37f6d2229768b509a27f34edffc009a03b2`.
- Exige `$schema` oficial 1.6, propiedad del digest del lock, tool/version/lifecycle
  exactos, 45 identidades y 70 aristas activadas.
- Registra validación externa PASS del mismo SBOM con CycloneDX CLI oficial 0.33.1
  contra schema 1.6; el parser local sigue usando un perfil cerrado más estricto.
- Combina lock y SBOM sólo desde un snapshot íntegro y eleva exclusivamente
  `lock_verified`, `sbom_verified` y `lock_sbom_consistent`.
- Mantiene todos los demás claims falsos y el módulo sin caller operativo.

## Impact

`lock_verified=true` significa que el TOML coincide con este perfil uv exacto.
`sbom_verified=true` significa que el JSON coincide con este perfil CycloneDX exacto
y que el artefacto fue validado externamente contra el schema oficial indicado.
`lock_sbom_consistent=true` significa sólo igualdad exacta relativa de las 45
identidades/fuentes y 70 aristas activadas, además del digest del lock enlazado.

No se afirma compatibilidad genérica con otros locks uv o SBOM CycloneDX, ni que una
instalación/build sea bitwise reproducible. Tampoco se verifican origen,
autenticidad, firma —el commit Laya fijado es unsigned—, licencias, CVE, seguridad,
bytes de wheels seleccionados, checkpoint, OCI, materialización, executor o
inferencia.

La excepción de `size` ausente se limita a un único wheel Torch exacto por URL y
SHA-256. Nunca autoriza descargarlo ni generaliza la excepción a otro artefacto.

## Reconciliación con slices previos

Este cambio satisface conceptualmente PR16 tasks 4.1/4.2 y PR17 task 4.1 para el
perfil local de lock/SBOM. PR17 task 4.2 sobre OCI permanece pendiente; este change
no la cierra ni modifica los otros OpenSpec changes.

## Deferred

- verificar firma, autenticidad o procedencia de commit, índices y distribuciones;
- revisar licencias, CVE, malware, políticas o seguridad de dependencias;
- descargar y verificar bytes de wheels/sdists, incluido Torch;
- demostrar resolución genérica, instalación o build bitwise reproducible;
- validar checkpoint/OCI, materializar el runtime o ejecutar inferencia;
- cerrar la auditoría independiente de board y cualquier gate operativo.
