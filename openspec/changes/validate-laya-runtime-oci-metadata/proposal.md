# Change: Validación exacta de metadata OCI del runtime Laya

Estado: implementado como evidencia local del manifest OCI capturado; no acredita
los bytes del layout, origen, licencia, materialización ni ejecución.

## Why

PR18 cerró el perfil local de lock/SBOM, pero el quinto artefacto del bundle seguía
siendo un blob OCI opaco. PR19 interpreta ese manifest con un parser cerrado, lo
liga a los otros cuatro artefactos del mismo snapshot y hace explícita una frontera
conservadora: validar metadata y referencias no equivale a poseer ni verificar la
imagen que esas referencias describen.

## What Changes

- Fija el fixture `oci-manifest.json` en 3.166 bytes y SHA-256
  `7e46eb4f9e10b81e550b2587d1b12d50e0e9d746e346077e860e702ce169d9f0`.
- Valida de forma pura, acotada y fail-closed un perfil exacto de OCI image manifest:
  schema/media types, config, diez layers ordenadas y annotations cerradas.
- Produce `laya-runtime-oci-evidence-v1` únicamente desde el manifest raw exacto de
  un `LayaRuntimeBundleSnapshot` íntegro y exige que sus cuatro digest annotations
  coincidan con los bytes capturados en ese mismo snapshot.
- Comprueba coherencia interna con Laya 0.4.2, commit
  `68804629e8ccd9d616d48a40e87de9fabbeae069`, Python 3.11.10 y la base declarada.
- Eleva sólo `artifact_integrity_verified` y
  `oci_manifest_semantics_verified`; conserva falsos los claims de bytes OCI,
  origen, materialización, executor e inferencia.
- Emite un summary determinista mínimo que no publica manifest, annotations,
  descriptors, paths ni digests de artefactos, y mantiene el módulo sin caller
  productivo.

## Evidencia de generación, no claim runtime

El manifest proviene de una generación real y repetida del perfil con:

- Laya 0.4.2 en el commit exacto anterior, que permanece sin firma;
- base `python:3.11.10-slim-bookworm` fijada por digest
  `840e180ebcc6e5c8efab209c43f5e40fd2af98cb49db5c7103c90539c56bb30e`;
- uv 0.12.3 fijado por digest
  `2d890623d310b57771ce840f0da5eed5fc6d657da05ffaa45d82797b53fa3abc`;
- repositorios Debian snapshot `20261010T000000Z`;
- dos generaciones con el mismo digest del manifest, y layouts aceptados durante
  la generación por umoci 0.6.0, binario SHA-256
  `b51c267ec394499e42c6fde47f240b7b7dba57ea49df0b5acd304378b82a3b71`.

Ese control externo describe cómo se obtuvo el fixture. PR19 no ejecuta umoci ni
convierte su PASS en una garantía runtime: el artefacto capturado es sólo el
manifest de 3.166 bytes.

## Impact y límites

`oci_manifest_semantics_verified=true` significa únicamente que los bytes exactos
del manifest coinciden con el perfil local cerrado y que sus enlaces internos son
coherentes con el mismo snapshot. Las annotations de source, revision, license y
base son declaraciones coherentes; no prueban procedencia, autenticidad, firma,
licencia efectiva ni ancestry de la base.

PR19 no captura ni verifica `oci-layout`, `index.json`, config ni layer blobs. Por
eso `oci_bytes_verified=false`. Tampoco verifica bytes del checkpoint, materializa
el runtime, instala artefactos, habilita executor ni ejecuta inferencia. PR20 deberá
cerrar el layout/index/config/layers por bytes antes de elevar esos claims.

## Deferred

- capturar y verificar por bytes el layout, index, config y todas las layers (PR20);
- verificar procedencia, firma, licencia efectiva o ancestry de base/Laya;
- verificar bytes del checkpoint y compatibilidad real modelo-runtime;
- materializar, instalar, habilitar executor o ejecutar inferencia;
- conectar la evidencia a un caller productivo o readiness operativo;
- completar la auditoría independiente final y el merge gate.
