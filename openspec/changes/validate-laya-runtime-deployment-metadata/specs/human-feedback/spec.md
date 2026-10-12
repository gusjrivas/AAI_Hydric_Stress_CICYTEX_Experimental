## ADDED Requirements

### Requirement: Parsing JSON cerrado, acotado y fail-closed

El sistema MUST aceptar runtime config y checkpoint manifest sólo como bytes UTF-8
JSON con objetos de schema exacto, MUST rechazar claves duplicadas, constantes no
finitas, recursión inválida y campos faltantes/adicionales, y MUST aplicar límites de
16 KiB y 64 KiB respectivamente antes de parsear.

#### Scenario: Metadata válida y acotada

- **GIVEN** blobs bytes UTF-8 dentro de sus límites y con schemas exactos
- **WHEN** se parsean como runtime config y checkpoint manifest
- **THEN** se obtienen objetos inmutables y canónicos del perfil local.

#### Scenario: Payload ambiguo o excesivo

- **GIVEN** input no-bytes, UTF-8/JSON inválido, clave duplicada, no finito, recursión excesiva o payload sobre el cap
- **WHEN** se intenta parsear
- **THEN** la operación falla de forma cerrada
- **AND** no se construye evidencia parcial.

#### Scenario: Cardinalidad previa del checkpoint

- **GIVEN** un checkpoint manifest cuyo array `files` no contiene exactamente cinco elementos
- **WHEN** se valida
- **THEN** falla antes de invocar el parser de cualquiera de sus elementos.

### Requirement: Perfil local exacto del runtime config

El runtime config MUST usar `laya-runtime-config-v1`, entrypoint `laya-serve`, la
identidad de runtime fijada por PR15, el environment CPU/offline exacto y la identidad
de modelo declarada `convaiinnovations/laya` en revisión
`55cf4c4ebb4ebe31b2550e8bdf3bd21b99753851`, subfolder/name `multilingual`.

#### Scenario: Config conforme al perfil

- **GIVEN** un config con runtime, modelo, environment y digest de checkpoint exactos
- **WHEN** se valida localmente
- **THEN** `runtime_config_semantics_verified` puede ser verdadero
- **AND** ese flag significa sólo conformidad sintáctico-semántica con el perfil local.

#### Scenario: Extensión o identidad diferente

- **GIVEN** otro entrypoint, runtime, modelo, environment, secret, URL o campo adicional
- **WHEN** se valida el config
- **THEN** se rechaza sin exponer el valor privado en el error.

### Requirement: Checkpoint manifest de cinco declaraciones exactas

El checkpoint manifest MUST usar `laya-checkpoint-manifest-v1`, repetir exactamente
repository/revision/subfolder del perfil y declarar una vez cada uno de los cinco
roles contractuales con path, SHA-256 y tamaño exactos.

#### Scenario: Cinco roles en orden arbitrario

- **GIVEN** las cinco declaraciones exactas sin duplicados
- **WHEN** se valida el checkpoint manifest
- **THEN** se normalizan al orden contractual
- **AND** `checkpoint_manifest_semantics_verified` puede ser verdadero sólo con el significado local acotado.

#### Scenario: Declaración desviada

- **GIVEN** un rol faltante/adicional/duplicado o un path, digest, tamaño o identidad diferente
- **WHEN** se valida
- **THEN** el manifest se rechaza de forma cerrada.

### Requirement: Evidencia ligada a un único snapshot

El combinador MUST extraer config y checkpoint manifest sólo de un
`LayaRuntimeBundleSnapshot` íntegro, MUST ligar config con manifest de runtime, modelo
con checkpoint y digest del config con los bytes capturados del checkpoint manifest,
y MUST impedir sustitutos provistos por el caller.

#### Scenario: Enlaces internos coherentes

- **GIVEN** un snapshot PR16 y dos documentos locales conformes
- **WHEN** identidades y digest interno coinciden
- **THEN** se produce `laya-runtime-deployment-evidence-v1`
- **AND** conserva exactamente el `RuntimeIdentityRef` del snapshot.

#### Scenario: Mezcla de metadata

- **GIVEN** config, checkpoint o runtime provenientes de identidades diferentes
- **WHEN** un enlace interno no coincide
- **THEN** la evidencia combinada se rechaza.

### Requirement: Semántica local no equivale a evidencia externa

Los flags `runtime_config_semantics_verified` y
`checkpoint_manifest_semantics_verified` MUST significar exclusivamente conformidad
con schemas/perfil local y enlaces internos. MUST NOT interpretarse como prueba de
licencia, procedencia/origen, autenticidad, compatibilidad de ejecución, bytes del
checkpoint, OCI, lock/SBOM, materialización ni inferencia.

#### Scenario: Metadata local conforme

- **GIVEN** evidencia combinada válida
- **WHEN** ambos flags semánticos son verdaderos
- **THEN** `lock_verified`, `sbom_verified`, `lock_sbom_consistent` y `checkpoint_bytes_verified` son falsos
- **AND** `oci_bytes_verified`, `oci_manifest_semantics_verified` y `origin_verified` son falsos
- **AND** `runtime_materialized`, `executor_available` e `inference_executed` son falsos.

#### Scenario: Compatibilidad no demostrada

- **GIVEN** metadata que enumera versiones y archivos compatibles según el perfil
- **WHEN** no se cargaron esos bytes ni se ejecutaron pruebas de compatibilidad
- **THEN** no se afirma que el checkpoint funcione con Laya, Python, plataforma o imagen declarados.

### Requirement: Checkpoint externo sólo como identidad no operativa

El sistema MAY aceptar `convaiinnovations/laya` únicamente como identidad declarada
en metadata local no operativa. MUST mantener pendiente la revisión de licencia,
procedencia/origen, autenticidad, compatibilidad y bytes, y MUST bloquear su uso,
materialización y ejecución.

#### Scenario: Reconciliación con la fuente PR15

- **GIVEN** que PR15 fija `NandhaKishorM/laya` como source del engine
- **WHEN** PR17 valida `convaiinnovations/laya` como repository del checkpoint
- **THEN** no reemplaza ni amplía la fuente del runtime
- **AND** sólo confirma que esa identidad coincide con el perfil local declarado.

#### Scenario: Revisión externa pendiente

- **GIVEN** metadata local válida del checkpoint
- **WHEN** no existen revisión de licencia/procedencia/compatibilidad ni verificación de bytes
- **THEN** origen, bytes, materialización, executor e inferencia permanecen falsos
- **AND** el checkpoint no se usa ni descarga.

### Requirement: Privacidad, pureza y aislamiento

La implementación MUST ocultar blobs, metadata de modelo, environment, paths y
digests de checkpoint en `repr`, summary y errores; MUST NOT realizar filesystem,
red, procesos o carga de modelo; y MUST permanecer sin callers operativos.

#### Scenario: Summary público conservador

- **GIVEN** evidencia válida con metadata privada
- **WHEN** se serializa el summary
- **THEN** contiene sólo schema, runtime identity y flags
- **AND** no contiene repository, revision, subfolder, environment, paths, digests ni blobs.

#### Scenario: Flujos existentes aislados

- **GIVEN** metadata de despliegue validada localmente
- **WHEN** se ejecutan backend, readiness, runners y scripts existentes
- **THEN** no importan ni invocan este módulo
- **AND** no se materializa runtime ni se ejecuta inferencia.
