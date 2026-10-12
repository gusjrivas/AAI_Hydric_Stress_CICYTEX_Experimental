# Diseño: evidencia local exacta del manifest OCI

## Contexto y frontera de confianza

La entrada es un `LayaRuntimeBundleSnapshot` PR16 que ya contiene exactamente cinco
artefactos capturados. PR19 interpreta sólo `oci_manifest`; no abre un OCI layout ni
obtiene config o layers. El parser es puro y no usa filesystem, red, subprocess,
registry, container engine, installer ni runtime de modelos.

El agregado conserva el snapshot exacto. No compone automáticamente las evidencias
semánticas PR17/PR18: sus flags permanecen falsos aunque el manifest enlace los
digests de esos artefactos.

## Decisiones

### 1. Fixture raw exacto y perfil cerrado

El fixture `tests/fixtures/laya/runtime_oci/oci-manifest.json` tiene 3.166 bytes y
SHA-256
`7e46eb4f9e10b81e550b2587d1b12d50e0e9d746e346077e860e702ce169d9f0`.
El combinador exige esos bytes exactos, no sólo equivalencia JSON.

El parser acepta únicamente bytes UTF-8 JSON, cap de 64 KiB, profundidad y strings
acotados, sin claves duplicadas ni constantes no finitas. Exige un objeto raíz con
campos exactos, `schemaVersion=2`, media type OCI de image manifest, descriptor de
config exacto, diez descriptors de layers gzip en orden exacto y el conjunto cerrado
de diez annotations. Los modelos son frozen/slotted/factory-sealed y el compromiso
semántico canónico también debe coincidir.

Esto es un parser del perfil local conocido, no compatibilidad genérica con todo
manifest OCI válido.

### 2. Generación repetida registrada por separado

El manifest fue obtenido construyendo el perfil real con:

- Laya `0.4.2` desde `NandhaKishorM/laya` commit
  `68804629e8ccd9d616d48a40e87de9fabbeae069`, que está sin firma;
- base `docker.io/library/python:3.11.10-slim-bookworm` fijada por digest
  `sha256:840e180ebcc6e5c8efab209c43f5e40fd2af98cb49db5c7103c90539c56bb30e`;
- uv 0.12.3 fijado por digest
  `sha256:2d890623d310b57771ce840f0da5eed5fc6d657da05ffaa45d82797b53fa3abc`;
- Debian snapshot `20261010T000000Z`;
- timestamps normalizados y dos generaciones cuyo manifest repitió el SHA-256
  `7e46eb4f9e10b81e550b2587d1b12d50e0e9d746e346077e860e702ce169d9f0`.

Durante esa generación umoci 0.6.0, binario SHA-256
`b51c267ec394499e42c6fde47f240b7b7dba57ea49df0b5acd304378b82a3b71`,
aceptó ambos layouts. Es evidencia de generación externa y repetibilidad bajo el
perfil fijado; no forma parte del validador, no se repite al emitir evidencia PR19
y no demuestra un claim runtime.

### 3. Evidencia ligada al mismo snapshot

El agregado vuelve a comprobar cardinalidad y cobertura exactas de los cinco
artefactos, además de tamaño/SHA-256 de cada contenido. Sólo toma el manifest del
rol `oci_manifest` del snapshot; el caller no puede suministrar un sustituto.

Las annotations de uv lock, SBOM, runtime config y checkpoint manifest deben igualar
el SHA-256 de los cuatro blobs realmente capturados. Source/revision/version/license
y base name/digest deben ser coherentes con el runtime manifest y su
`RuntimeIdentityRef`. Cualquier mezcla de snapshot, identidad, proxy, duplicado,
omisión o raw manifest semánticamente equivalente pero distinto falla sin evidencia
parcial.

### 4. Declaración coherente no es origen probado

Las annotations:

- `org.opencontainers.image.source`;
- `org.opencontainers.image.revision`;
- `org.opencontainers.image.version`;
- `org.opencontainers.image.licenses`;
- `org.opencontainers.image.base.name`;
- `org.opencontainers.image.base.digest`;

se validan como metadata declarada y coherente con el perfil. No prueban que los
bytes provengan de ese source/commit, que el commit esté firmado, que Apache-2.0 sea
la licencia efectiva de todos los contenidos, ni que las layers desciendan de la
base declarada. El commit upstream permanece unsigned y `origin_verified=false`.

### 5. Flags conservadores e independencia de capas

El objeto eleva sólo:

- `artifact_integrity_verified=true`: el snapshot conserva integridad exacta PR16;
- `oci_manifest_semantics_verified=true`: el manifest raw exacto satisface este
  perfil local y sus cross-links internos.

Permanecen falsos `lock_verified`, `sbom_verified`, `lock_sbom_consistent`,
`runtime_config_semantics_verified`, `checkpoint_manifest_semantics_verified`,
`checkpoint_bytes_verified`, `oci_bytes_verified`, `origin_verified`,
`runtime_materialized`, `executor_available` e `inference_executed`.

En particular, `oci_bytes_verified=false` porque el snapshot no contiene
`oci-layout`, `index.json`, config ni layer blobs. Los digests/sizes del manifest son
referencias declaradas, no verificación de sus targets.

### 6. Privacidad y aislamiento

`repr` y errores usan mensajes genéricos. El summary canónico contiene sólo schema,
`RuntimeIdentityRef` y flags; no publica el manifest, annotations, descriptors,
paths, digests/sizes de config/layers ni digests de los otros cuatro artefactos. El
módulo permanece sin imports/usos desde módulos productivos; validar metadata no
altera readiness ni habilita operación.

### 7. TDD implementado

La cadena versionada fue:

1. RED `f592412` y hardening RED `0ea8770` para el perfil cerrado, raw fixture,
   límites, privacidad y mutaciones.
2. GREEN `2023afe` para el parser semántico aislado.
3. Guardas de checkout byte-stable `815e22d` y corrección `b836951` para conservar
   exactamente los bytes LF del fixture.
4. RED `b3ea9dd` para el agregado desde el mismo snapshot y cross-links raw.
5. Hardening RED `8638594`, `77c5ba8` y `45f31a5` para sellado, mutaciones y
   aislamiento sin bypasses.
6. GREEN `fbc4dce` para evidencia agregada, summary canónico y flags conservadores.

Las suites focalizadas quedan verdes. La auditoría independiente final del board y
el merge gate permanecen pendientes hasta que se registren explícitamente.

## Consecuencias

- El quinto blob deja de ser opaco y queda enlazado a un único snapshot íntegro.
- Los claims se mantienen por debajo de lo que permitiría inferir sólo un manifest.
- PR20 puede añadir captura/verificación de layout/index/config/layers sin cambiar
  retroactivamente el significado de PR19.

## Rollback

El módulo no tiene caller productivo ni estado externo. Revertir PR19 elimina el
parser, fixture, tests y este change sin migraciones, descarga, cleanup de runtime ni
cambios en resultados científicos. Los contratos PR14-PR18 permanecen intactos.
