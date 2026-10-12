## ADDED Requirements

### Requirement: Manifest OCI raw exacto y parser cerrado

El sistema MUST validar sólo bytes UTF-8 JSON acotados del perfil local exacto,
MUST exigir schema/media types, config, diez layers ordenadas y annotations cerradas,
y MUST rechazar claves duplicadas, constantes no finitas, campos extra, profundidad,
strings o payload excesivos. El fixture MUST tener 3.166 bytes y SHA-256
`7e46eb4f9e10b81e550b2587d1b12d50e0e9d746e346077e860e702ce169d9f0`.

#### Scenario: Manifest exacto

- **GIVEN** los bytes exactos del fixture de 3.166 bytes
- **WHEN** se validan schema, media types, config, layers, annotations y compromiso canónico
- **THEN** se obtiene un valor inmutable y factory-sealed
- **AND** `oci_manifest_semantics_verified` puede ser verdadero sólo en la evidencia agregada.

#### Scenario: JSON equivalente pero bytes distintos

- **GIVEN** un manifest semánticamente equivalente con whitespace, orden o serialización diferentes
- **WHEN** se intenta emitir evidencia desde el snapshot
- **THEN** se rechaza por no coincidir el raw exacto
- **AND** no se produce evidencia parcial.

#### Scenario: Payload ambiguo o excesivo

- **GIVEN** input no-bytes, UTF-8/JSON inválido, clave duplicada, no finito, extensión o límite excedido
- **WHEN** se invoca el parser
- **THEN** falla de forma cerrada
- **AND** el error no expone el contenido privado.

### Requirement: Evidencia OCI ligada a un único snapshot íntegro

El combinador MUST aceptar sólo un `LayaRuntimeBundleSnapshot` exacto e íntegro,
MUST extraer de él el único rol `oci_manifest`, MUST volver a comprobar cobertura,
tamaño y SHA-256 de los cinco artefactos, y MUST impedir manifest o identidad
sustitutos provistos por el caller.

#### Scenario: Agregado del mismo snapshot

- **GIVEN** un snapshot PR16 exacto con los cinco blobs capturados
- **WHEN** el manifest raw y su `RuntimeIdentityRef` coinciden
- **THEN** se produce `laya-runtime-oci-evidence-v1`
- **AND** el agregado conserva exactamente el snapshot y runtime identity originales.

#### Scenario: Snapshot mezclado, incompleto o proxy

- **GIVEN** otra identidad, un rol faltante/duplicado, un proxy/subclase o contenido alterado
- **WHEN** se intenta combinar evidencia
- **THEN** se rechaza sin aceptar equivalencia parcial.

### Requirement: Cross-links exactos a los artefactos capturados

El sistema MUST igualar las annotations de uv lock, SBOM, runtime config y checkpoint
manifest con el SHA-256 de esos cuatro blobs del mismo snapshot. MUST exigir además
coherencia exacta de source, revision, version, license y base declarados con el
runtime manifest fijado.

#### Scenario: Enlaces internos coherentes

- **GIVEN** el manifest exacto y los otros cuatro blobs del mismo snapshot
- **WHEN** cada digest annotation coincide con los bytes capturados y el perfil runtime coincide
- **THEN** la semántica local del manifest puede considerarse verificada
- **AND** ningún flag semántico PR17/PR18 se hereda automáticamente.

#### Scenario: Sustitución o digest divergente

- **GIVEN** un annotation digest, source, revision, version, license, base name o base digest distinto
- **WHEN** se valida el agregado
- **THEN** la operación falla de forma cerrada
- **AND** no se acepta una mezcla de snapshots.

### Requirement: Generación reproducible no amplía el claim runtime

La documentación MUST registrar inputs pinneados, generación repetida y validación
externa del layout. MUST tratar esos datos como evidencia de generación del fixture,
no como un claim runtime de PR19.

#### Scenario: Registro de generación completo

- **GIVEN** Laya 0.4.2 commit `68804629e8ccd9d616d48a40e87de9fabbeae069` sin firma, base Python digest `840e180ebcc6e5c8efab209c43f5e40fd2af98cb49db5c7103c90539c56bb30e`, uv 0.12.3 digest `2d890623d310b57771ce840f0da5eed5fc6d657da05ffaa45d82797b53fa3abc` y Debian snapshot `20261010T000000Z`
- **AND** dos generaciones del perfil fijado
- **WHEN** repiten el digest del manifest y umoci acepta ambos layouts
- **THEN** se registra reproducibilidad del artefacto capturado
- **AND** umoci 0.6.0 queda fijado por SHA-256 `b51c267ec394499e42c6fde47f240b7b7dba57ea49df0b5acd304378b82a3b71`
- **AND** el resultado de umoci no se presenta como validación runtime de PR19.

### Requirement: Declaraciones OCI no prueban procedencia ni licencia

Las annotations de source, revision, license y base MUST interpretarse únicamente
como declaraciones coherentes con el perfil local. MUST NOT presentarse como prueba
de origen, autenticidad, firma, licencia efectiva, contenido o ancestry de la base.

#### Scenario: Metadata declarada conforme

- **GIVEN** source, commit, licencia y base exactos en el manifest
- **WHEN** sólo se comprobaron sus valores y enlaces internos
- **THEN** `origin_verified` permanece falso
- **AND** el commit upstream sin firma no se presenta como autenticado.

### Requirement: Flags conservadores sin bytes OCI

La evidencia MUST elevar sólo `artifact_integrity_verified` y
`oci_manifest_semantics_verified`. MUST mantener falsos los flags de lock/SBOM,
config/checkpoint semantics, checkpoint bytes, OCI bytes, origen, materialización,
executor e inferencia.

#### Scenario: Manifest válido sin layout capturado

- **GIVEN** evidencia OCI local válida
- **WHEN** PR19 no capturó `oci-layout`, `index.json`, config ni layer blobs
- **THEN** `oci_bytes_verified` es falso
- **AND** los descriptor digests/sizes no se interpretan como verificación de sus targets.

#### Scenario: Sin operación

- **GIVEN** el manifest semánticamente validado
- **WHEN** no se verificaron checkpoint bytes ni se materializó el runtime
- **THEN** `checkpoint_bytes_verified`, `runtime_materialized`, `executor_available` e `inference_executed` son falsos
- **AND** no cambia readiness ni producción.

### Requirement: Privacidad, pureza y aislamiento

La implementación MUST ocultar manifest, annotations, descriptors, paths, payloads
y digests de artefactos en `repr`, errores y summary; MUST NOT realizar filesystem,
red, subprocess, registry, instalación o ejecución; y MUST permanecer sin caller
productivo.

#### Scenario: Summary privado y determinista

- **GIVEN** evidencia OCI válida
- **WHEN** se serializa el summary canónico
- **THEN** contiene sólo schema, runtime identity y flags
- **AND** no contiene manifest, annotations, config/layers ni digests privados.

#### Scenario: Próximo cierre por bytes

- **GIVEN** que PR19 valida sólo metadata del manifest
- **WHEN** layout, index, config y layers siguen fuera del snapshot
- **THEN** PR20 permanece requerido para cerrar esos bytes
- **AND** ningún módulo productivo importa o invoca el agregado PR19.
