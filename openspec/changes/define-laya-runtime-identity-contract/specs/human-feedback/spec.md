## ADDED Requirements

### Requirement: Manifest JSON estricto e inmutable

El sistema MUST cargar `laya-runtime-manifest-v1` exclusivamente desde bytes UTF-8
con JSON válido, MUST rechazar claves duplicadas, números no finitos y campos
faltantes o adicionales, y MUST representar manifest, artefactos y referencia como
objetos frozen/slotted que revalidan cualquier construcción o reemplazo.

#### Scenario: Manifest cerrado válido

- **GIVEN** bytes JSON UTF-8 con exactamente los campos contractuales
- **WHEN** se carga el manifest
- **THEN** se obtiene un objeto estructuralmente válido e inmutable
- **AND** no se conservan extensiones desconocidas ni defaults implícitos.

#### Scenario: Payload ambiguo

- **GIVEN** un string en lugar de bytes, UTF-8 o JSON inválido, claves duplicadas, no finitos o un schema abierto
- **WHEN** se intenta cargar el manifest
- **THEN** la operación falla de forma cerrada.

### Requirement: Fuente Laya y entorno exactos

El manifest MUST fijar el release `laya==0.4.2` con fuente exacta
`https://github.com/NandhaKishorM/laya@68804629e8ccd9d616d48a40e87de9fabbeae069`,
proveedor `laya-http`, licencia declarada `Apache-2.0`, Python `3.11.10`, plataforma
`linux/amd64` y una referencia de imagen base por SHA-256 lowercase no nulo.

#### Scenario: Runtime objetivo válido

- **GIVEN** metadata que coincide exactamente con versión, repositorio, commit, entorno y base image contractuales
- **WHEN** se valida el manifest
- **THEN** la identidad declarada del runtime es aceptada.

#### Scenario: Fuente móvil o alternativa

- **GIVEN** otra versión, repo, commit corto/no canónico/nulo, tag móvil, plataforma o imagen por tag
- **WHEN** se valida el manifest
- **THEN** el manifest es rechazado de forma cerrada.

#### Scenario: Checkpoint externo no es source

- **GIVEN** una referencia a `convaiinnovations/laya`
- **WHEN** se presenta como fuente del runtime
- **THEN** el manifest es rechazado
- **AND** cualquier checkpoint de ese origen requiere revisión futura independiente de licencia, procedencia, compatibilidad y bytes.

### Requirement: Cinco roles de artefactos exactos

El manifest MUST contener exactamente una declaración para `dependency_lock`,
`sbom`, `runtime_config`, `checkpoint_manifest` y `oci_manifest`; cada rol MUST usar
su formato y path contractual, SHA-256 lowercase no nulo y tamaño entero positivo.

#### Scenario: Conjunto completo y único

- **GIVEN** una declaración válida por cada uno de los cinco roles
- **WHEN** se carga el manifest
- **THEN** los artefactos se conservan en orden canónico
- **AND** todos sus paths son distintos.

#### Scenario: Rol, formato o contenido declarado inválido

- **GIVEN** un rol faltante, extra o duplicado, un formato incorrecto, digest nulo/no canónico o tamaño no positivo
- **WHEN** se valida el manifest
- **THEN** la operación falla de forma cerrada.

#### Scenario: Path no canónico

- **GIVEN** un path absoluto, Windows, con segmentos especiales, separadores repetidos, espacios, Unicode o duplicado entre roles
- **WHEN** se valida el artefacto
- **THEN** el manifest es rechazado.

### Requirement: Identidad canónica y referencia compatible

El sistema MUST serializar el manifest en JSON canónico con roles ordenados, MUST
calcular `identity_sha256` sobre esos bytes y MUST proyectarlo a la misma clase
`RuntimeIdentityRef` utilizada por el contrato de ejecución PR14.

#### Scenario: Layouts equivalentes

- **GIVEN** manifests semánticamente iguales con distinto orden de claves, indentación u orden de entrada de artefactos
- **WHEN** se canonicalizan
- **THEN** sus bytes canónicos e identidades SHA-256 son iguales.

#### Scenario: Cambio semántico

- **GIVEN** un cambio en metadata o en cualquier rol, path, digest o tamaño
- **WHEN** se calcula la identidad
- **THEN** el digest cambia.

#### Scenario: Referencia compartida con PR14

- **GIVEN** un manifest válido
- **WHEN** se deriva `laya-runtime-identity-v1`
- **THEN** la referencia contiene su `identity_sha256`
- **AND** su tipo es el mismo que consume el contrato de evidencia LOSO
- **AND** el summary golden público de PR14 permanece sin cambios.

### Requirement: Identidad declarada sin verificación ni materialización

El sistema MUST declarar únicamente validez estructural y MUST mantener falsos los
estados de integridad de artefactos, lock, SBOM, consistencia lock/SBOM, bytes de
checkpoint/OCI, materialización, origen, executor e inferencia. El loader MUST NOT
leer filesystem, resolver paths, descargar artefactos, consultar repositorios o
ejecutar modelos.

#### Scenario: Manifest estructural válido

- **GIVEN** un manifest que satisface el schema
- **WHEN** se construye su identidad
- **THEN** `structurally_valid` es verdadero
- **AND** `artifact_integrity_verified`, `lock_verified`, `sbom_verified` y `lock_sbom_consistent` son falsos
- **AND** `checkpoint_bytes_verified`, `oci_bytes_verified`, `runtime_materialized` y `origin_verified` son falsos
- **AND** `executor_available` e `inference_executed` son falsos.

#### Scenario: Digests declarados no prueban bytes

- **GIVEN** paths, tamaños y SHA-256 sintácticamente válidos
- **WHEN** el parser acepta el manifest
- **THEN** no se afirma que los archivos existan o coincidan con lo declarado
- **AND** no se afirma que lock, SBOM, checkpoint o imagen sean consistentes, auténticos o seguros.

### Requirement: Aislamiento de ejecución y operación

El contrato de identidad MUST NOT ser importado ni invocado por adapters, backend,
offline readiness, experiment runners o scripts, y MUST NOT materializar Laya ni
ejecutar inferencia.

#### Scenario: Flujos existentes sin runtime materializado

- **GIVEN** únicamente la identidad declarativa de Laya
- **WHEN** se ejecutan CICYTEX, Pergamino, Melchor Romero y laboratorio mock
- **THEN** conservan sus contratos previos
- **AND** el manifest no activa executor, readiness, shadow review ni producción.
