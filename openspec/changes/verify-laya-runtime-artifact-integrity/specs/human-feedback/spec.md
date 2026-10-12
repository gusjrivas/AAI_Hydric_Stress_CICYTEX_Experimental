## ADDED Requirements

### Requirement: Bundle portable exacto y all-or-nothing

El sistema MUST verificar en memoria exactamente los cinco payloads `bytes` cuyos
paths declara un único `LayaRuntimeManifest`, MUST comprobar para cada uno tamaño y
SHA-256, y MUST NOT producir un snapshot parcial ante cualquier discrepancia.

#### Scenario: Cinco payloads válidos

- **GIVEN** un manifest válido y un payload bytes por cada path contractual
- **WHEN** todos los tamaños y SHA-256 coinciden
- **THEN** se produce `laya-runtime-bundle-snapshot-v1`
- **AND** contiene exactamente cinco artefactos en orden canónico
- **AND** se liga al `RuntimeIdentityRef` del mismo manifest.

#### Scenario: Cobertura o contenido inconsistente

- **GIVEN** un payload faltante/adicional, un valor no-bytes o una discrepancia de tamaño/SHA-256
- **WHEN** se intenta verificar el bundle
- **THEN** la operación falla por completo
- **AND** no existe snapshot parcial ni se filtra contenido privado.

#### Scenario: Construcción directa no confiable

- **GIVEN** un artefacto o snapshot construido/reemplazado fuera del factory verificador
- **WHEN** intenta autoafirmar integridad o cambiar manifest, contenido, orden o identidad
- **THEN** la construcción falla de forma cerrada.

### Requirement: Bytes exactos y punteros Git LFS rechazados

El verificador MUST tratar los payloads como bytes opacos, MUST NOT normalizar line
endings y MUST rechazar un puntero Git LFS v1 tanto con LF como con CRLF.

#### Scenario: Puntero LFS efectivo

- **GIVEN** bytes que comienzan con la cabecera Git LFS v1 y continúan con LF o CRLF
- **WHEN** su tamaño/digest declarado coincide incluso con el puntero
- **THEN** el payload es rechazado porque no contiene el artefacto materializado.

#### Scenario: LF y CRLF son bytes diferentes

- **GIVEN** dos contenidos que sólo difieren en line endings
- **WHEN** se verifican contra un manifest
- **THEN** no se normalizan
- **AND** sólo el contenido cuyo tamaño y SHA-256 exactos coinciden puede aceptarse.

### Requirement: Captura Linux descriptor-relative y fail-closed

El adapter filesystem MUST usar traversal descriptor-relative con protección
anti-symlink para raíz, ancestros, directorios y targets, MUST aceptar sólo archivos
regulares, y MUST fallar antes de abrir en Windows o cuando falten las capacidades
Linux requeridas.

#### Scenario: Captura Linux segura

- **GIVEN** una raíz absoluta canónica y cinco archivos regulares declarados
- **WHEN** el host ofrece `dir_fd`, `O_DIRECTORY`, `O_NOFOLLOW`, `O_CLOEXEC` y `O_NONBLOCK`
- **THEN** cada componente se abre relativamente a un descriptor confiable
- **AND** los cinco bytes se entregan juntos al verificador portable.

#### Scenario: Symlink o target no regular

- **GIVEN** un symlink en cualquier ancestro/componente o un target directory, FIFO, socket u otro no regular
- **WHEN** se intenta capturar
- **THEN** la operación falla sin bloquear
- **AND** el verificador portable no recibe una captura parcial.

#### Scenario: Capability no disponible

- **GIVEN** Windows o un host sin las primitivas descriptor-relative requeridas
- **WHEN** se solicita la captura
- **THEN** se emite `SecureRuntimeCaptureUnavailableError` antes del primer open
- **AND** no se usa un fallback menos seguro.

### Requirement: Lectura acotada y cleanup total

El adapter MUST rechazar antes del primer open un bundle declarado mayor a 256 MiB,
MUST leer cada archivo como máximo hasta `size_bytes + 1` y MUST cerrar todos los
descriptores poseídos en éxito y error.

#### Scenario: Crecimiento o truncamiento

- **GIVEN** un archivo que crece, se trunca o entrega una lectura incompleta
- **WHEN** se captura
- **THEN** no se leen más de `size_bytes + 1` bytes para ese archivo
- **AND** la operación falla antes de verificar el bundle.

#### Scenario: Fallo de apertura, lectura o close

- **GIVEN** una excepción en cualquier fase, incluido cleanup
- **WHEN** se abandona la captura
- **THEN** se intenta cerrar una vez cada descriptor poseído
- **AND** no quedan descriptors del runtime filtrados
- **AND** no se produce un snapshot.

### Requirement: Detección TOCTOU acotada sin claim de atomicidad

El adapter MUST comparar `fstat` antes/después de cada lectura y MUST volver a
recorrer descriptor-relativamente paths e inodes de los cinco artefactos en un sweep
final antes de verificar. MUST NOT describir esa defensa como snapshot atómica del
filesystem.

#### Scenario: Mutación durante la lectura

- **GIVEN** un archivo que cambia contenido o metadata después del `fstat` inicial
- **WHEN** el `fstat` final produce otro fingerprint
- **THEN** la captura se rechaza
- **AND** el verificador portable no es invocado.

#### Scenario: Reemplazo después de capturar

- **GIVEN** un archivo o directorio intermedio reemplazado después de su captura
- **WHEN** el sweep final observa otro path, inode o fingerprint
- **THEN** el bundle se rechaza antes de verificar.

#### Scenario: Límite de la garantía

- **GIVEN** una captura aceptada
- **WHEN** se describe su evidencia
- **THEN** se afirma sólo que bytes capturados coinciden con tamaño/SHA del manifest y paths/inodes coinciden en el sweep final
- **AND** no se afirma atomicidad filesystem absoluta ni ausencia de mutaciones fuera de las ventanas observadas.

### Requirement: Privacidad y claims exclusivamente de integridad

El snapshot MUST ocultar bytes, paths y digests individuales en `repr`, summary y
errores. `artifact_integrity_verified=true` MUST significar sólo coincidencia de los
cinco bytes con el manifest; todos los claims semánticos y operacionales MUST
permanecer falsos.

#### Scenario: Summary público seguro

- **GIVEN** un snapshot válido con contenido privado
- **WHEN** se serializa su summary o se renderiza su representación
- **THEN** contiene sólo schema, referencia de runtime, conteo y flags
- **AND** no contiene bytes, root, paths ni digests individuales de artefactos.

#### Scenario: Sin validación semántica

- **GIVEN** cinco bytes que coinciden con el manifest
- **WHEN** todavía no se parsearon lock, SBOM, config, checkpoint manifest u OCI manifest
- **THEN** sus flags semánticos y `lock_sbom_consistent` son falsos
- **AND** no se afirma autenticidad, seguridad ni corrección de esos contenidos.

#### Scenario: Sin caller productivo

- **GIVEN** un bundle íntegro
- **WHEN** PR16 no tiene caller desde backend, readiness, runners o scripts
- **THEN** `runtime_materialized`, `origin_verified`, `executor_available` e `inference_executed` son falsos
- **AND** no se habilita evidencia científica, shadow review ni producción.
