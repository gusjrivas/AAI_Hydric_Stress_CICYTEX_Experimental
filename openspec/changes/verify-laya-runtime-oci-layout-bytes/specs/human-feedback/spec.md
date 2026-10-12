## ADDED Requirements

### Requirement: El layout OCI es una capa externa sin ampliar los cinco roles

El sistema MUST conservar exactamente los cinco roles de artefactos fijados y MUST
tratar layout/index/config/layers como evidencia externa que cierra referencias del
rol `oci_manifest`. MUST NOT añadir la imagen completa al bundle ni al repositorio.

#### Scenario: Roles estables con evidencia externa

- **GIVEN** un `LayaRuntimeOciEvidence` PR19 exacto
- **WHEN** se prepara la verificación del layout externo
- **THEN** los roles siguen siendo dependency lock, SBOM, runtime config, checkpoint manifest y OCI manifest
- **AND** layout, index, config y layers no se convierten en roles adicionales.

### Requirement: Plan cerrado de catorce archivos exactos

El sistema MUST exigir `oci-layout` e `index.json` por bytes exactos, MUST ligar el
único descriptor linux/amd64 del index al manifest PR19 y MUST derivar un grafo
ordenado de manifest, config y diez layers gzip con paths, media types, sizes y
SHA-256 exactos.

#### Scenario: Controles y grafo conformes

- **GIVEN** `oci-layout` de 30 bytes/SHA `18f0797eab35a4597c1e9624aa4f15fd91f6254e5538c1e0d193b2a95dd4acc6`
- **AND** `index.json` de 423 bytes/SHA `3d28b2fd93177f35031d802b830e2807253ea19838fb0386b14688a49dd75b39`
- **WHEN** el index enlaza el manifest PR19 y el grafo deriva config más diez layers
- **THEN** el plan contiene 2 controles, 12 blobs y 14 archivos lógicos
- **AND** exige exactamente 612.570.257 bytes de blobs y 612.570.710 bytes totales.

#### Scenario: Control equivalente o descriptor divergente

- **GIVEN** JSON semánticamente equivalente con bytes distintos, otra plataforma o descriptor/path/media type/order/cardinalidad diferente
- **WHEN** se prepara el plan
- **THEN** falla de forma cerrada sin autorizar lectura de blobs.

### Requirement: Cada blob se verifica por stream acotado sin claim global

El sistema MUST autorizar sólo los doce digests del plan, MUST aceptar únicamente
chunks `bytes` no vacíos de hasta 1 MiB, MUST limitar cada blob a 1.024 chunks y
MUST comprobar size/SHA-256 incrementalmente. Un receipt individual MUST NOT poder
sellar evidencia global.

#### Scenario: Blob exacto

- **GIVEN** un digest autorizado y sus bytes completos en chunks válidos
- **WHEN** size y SHA-256 coinciden
- **THEN** se emite un receipt inmutable ligado al mismo plan y blob
- **AND** aún no se eleva `oci_bytes_verified`.

#### Scenario: Stream hostil o incompleto

- **GIVEN** digest desconocido, chunk ambiguo/vacío/excesivo, más de 1.024 chunks, LFS pointer, truncado, agregado, alterado o generador fallido
- **WHEN** se verifica el stream
- **THEN** se rechaza sin consumir más allá de los límites
- **AND** el error no expone bytes, digest o contexto privado.

### Requirement: Captura Linux descriptor-relative desde una única raíz

El adaptador MUST requerir capacidades seguras Linux, MUST validar una raíz absoluta,
no-root y canónica de como máximo 128 componentes, y MUST capturar controles,
inventario y doce blobs sólo mediante descriptores relativos a esa misma raíz.

#### Scenario: Raíz y contenido exactos

- **GIVEN** una raíz canónica cuyo inventario contiene sólo controles, `blobs/sha256` y los doce archivos regulares single-link
- **WHEN** cada archivo se abre con no-follow, se lee y se revalida por descriptor/path
- **THEN** controles, inventario y receipts quedan ligados a la misma raíz.

#### Scenario: Plataforma o raíz no segura

- **GIVEN** Windows, capacidades dir-fd/flags ausentes, `/`, path relativo/no canónico, más de 128 componentes, symlink, hardlink o entrada extra/faltante
- **WHEN** se intenta capturar
- **THEN** falla de forma cerrada antes de sellar evidencia
- **AND** una raíz sobre el cap falla antes de cualquier `open`.

### Requirement: Sweep final y cleanup preceden el sellado

El sistema MUST conservar fingerprints de raíz, directorios, controles y blobs,
MUST reabrir/revalidar todos los paths y el inventario después de doce receipts, y
MUST cerrar cada descriptor exactamente una vez antes de crear autoridad/evidencia.

#### Scenario: Captura estable completa

- **GIVEN** doce receipts del mismo plan y fingerprints sin cambios
- **WHEN** el sweep final y todos los closes terminan correctamente
- **THEN** la autoridad privada puede sellar evidencia OCI layout.

#### Scenario: Mutación o falla tardía

- **GIVEN** reemplazo/rename/cambio de inventario, `fstat` divergente o error de close antes/durante/después del sweep
- **WHEN** se finaliza la captura
- **THEN** todos los descriptors propios se cierran una sola vez
- **AND** no se emite evidencia, aunque los doce hashes ya hubieran coincidido.

### Requirement: Flags de bytes verdaderos y claims no demostrados falsos

La evidencia MUST marcar verdaderos sólo integridad del artefacto, semántica PR19
del manifest, controles, inventario, same-root y bytes de manifest/config/layers.
MUST mantener falsos semántica de config/diffIDs/rootfs y todos los claims externos
u operativos.

#### Scenario: Layout exacto capturado

- **GIVEN** una captura same-root estable de los 14 archivos exactos
- **WHEN** se sella `laya-runtime-oci-layout-evidence-v1`
- **THEN** `oci_layout_controls_bytes_verified`, `oci_blob_inventory_verified`, `oci_same_root_capture_verified`, los tres flags de blob y `oci_bytes_verified` son verdaderos
- **AND** `artifact_integrity_verified` y `oci_manifest_semantics_verified` permanecen verdaderos.

#### Scenario: Bytes no implican semántica u operación

- **GIVEN** config y diez layers con size/SHA-256 correctos
- **WHEN** no se interpretaron config, diffIDs, tar entries ni rootfs
- **THEN** `oci_config_semantics_verified`, `oci_layer_diff_ids_verified` y `oci_rootfs_verified` son falsos
- **AND** lock/SBOM/config/checkpoint semantics, checkpoint bytes, origen, licencia, ancestry, ambos flags de materialización, executor e inferencia son falsos.

### Requirement: Gate externo serial preserva la raíz canónica

El operador SHOULD proveer mediante `LAYA_RUNTIME_OCI_LAYOUT_ROOT` una fuente
externa absoluta/canónica y SHOULD custodiarla con permisos o mount read-only. El
gate MUST tratarla como input read-only, MUST NOT modificarla, MUST verificar que su
fingerprint se preserve y MUST ejecutar la captura/adversariales serialmente y sin
xdist sobre un clon temporal distinto. PR20 MUST NOT afirmar enforcement de los
permisos/mount de la fuente ni que el gate sea obligatorio en CI.

#### Scenario: Gate Linux opt-in

- **GIVEN** una fuente externa declarada por el operador y capacidades Linux disponibles
- **WHEN** se ejecutan serialmente ambos módulos de tests con la variable definida
- **THEN** el clon descartable absoluto/no-root/canónico recibe toda mutación adversarial y la fuente conserva su fingerprint
- **AND** la corrida real registra `224 passed, 1 skipped`, incluido el hardening posterior del cap de traversal y únicamente el test de fail-closed Windows
- **AND** ese resultado es evidencia manual de release, no evidencia de CI obligatorio.

#### Scenario: Suite ordinaria sin imagen externa

- **GIVEN** un checkout que sólo contiene `oci-layout` e `index.json`
- **WHEN** la variable opt-in no está definida
- **THEN** la suite no afirma haber verificado los 612 MB externos
- **AND** no existe por ello un claim ni job CI obligatorio.

### Requirement: Evidencia privada y sin caller productivo

El sistema MUST mantener plan, receipts, autoridad y evidencia inmutables y sellados;
MUST ocultar raíz, paths, sizes, inventario, bytes y digests privados de
controles/blobs en summary, `repr` y errores; MUST conservar
`runtime_identity_sha256` como commitment público; y MUST mantener el adaptador sin
caller productivo.

#### Scenario: Summary conservador

- **GIVEN** evidencia layout válida
- **WHEN** se serializa el summary canónico
- **THEN** contiene schemas/profile, flags y runtime identity con su commitment público `runtime_identity_sha256`
- **AND** no contiene paths, bytes, sizes ni digests privados de controles/blobs.

#### Scenario: Sin integración operativa

- **GIVEN** que la verificación de bytes es positiva
- **WHEN** backend, runners, readiness y scripts productivos permanecen aislados
- **THEN** no se materializa rootfs/runtime ni se habilita executor
- **AND** no se carga checkpoint ni se ejecuta inferencia.
