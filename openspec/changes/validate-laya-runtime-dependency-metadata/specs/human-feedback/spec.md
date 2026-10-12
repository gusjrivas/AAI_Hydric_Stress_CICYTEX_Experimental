## ADDED Requirements

### Requirement: Perfil uv.lock exacto y auditable

El sistema MUST validar un perfil local exacto generado con uv 0.12.3 para CPython
3.11.10, Linux x86_64 CPU, cutoff `2026-10-10T09:19:05Z`, Laya commit
`68804629e8ccd9d616d48a40e87de9fabbeae069` sin firma, extra `serve`, Torch
`2.14.0+cpu` y constraint `setuptools==84.0.0`. MUST NOT presentarlo como parser o
compatibilidad genérica de uv.

#### Scenario: Lock exacto

- **GIVEN** `uv.lock` de 37.599 bytes y SHA-256 `e968771680b9c6e683163230ebd98b43541325ccb36d6959d1f9ed5565bd5526`
- **WHEN** estructura, perfil, inventario, fuentes, distribuciones y aristas coinciden exactamente
- **THEN** `lock_verified` puede ser verdadero
- **AND** significa sólo conformidad local con este perfil.

#### Scenario: Perfil distinto o ambiguo

- **GIVEN** otro Python, marker, cutoff, commit, extra, Torch, constraint, paquete, fuente, hash o arista
- **WHEN** se valida el lock
- **THEN** se rechaza de forma cerrada aunque pudiera ser válido para otro uso de uv.

### Requirement: Excepción Torch sin size cerrada y no operativa

El sistema MAY aceptar ausencia de `size` únicamente para el wheel Torch con URL
`https://download-r2.pytorch.org/whl/cpu/torch-2.14.0%2Bcpu-cp311-cp311-manylinux_2_28_x86_64.whl`
y SHA-256 `673dbf5c9bbadfffab7a386b6dd7a0c219f1408a328b7b4e86d0ae551cdafa42`.
MUST rechazar cualquier generalización y MUST NOT descargar el artefacto.

#### Scenario: Excepción exacta

- **GIVEN** package `torch`, kind wheel, URL y hash exactos sin campo size
- **WHEN** se valida la distribución
- **THEN** la omisión puede aceptarse dentro del perfil
- **AND** no implica que sus bytes hayan sido obtenidos o verificados.

#### Scenario: Otra omisión de size

- **GIVEN** otro paquete, URL, hash o kind sin size
- **WHEN** se valida
- **THEN** el lock es rechazado
- **AND** no existe cap de descarga porque el validador nunca descarga.

### Requirement: SBOM CycloneDX exacto, determinista y schema-validado

El sistema MUST validar un SBOM determinista generado con cdxgen 13.3.0, CycloneDX
1.6, `$schema` oficial, lifecycle pre-build y propiedad del digest del lock. El
artefacto MUST tener 65.198 bytes y SHA-256
`f2fde1a342990e3b5b4d74d4930bf37f6d2229768b509a27f34edffc009a03b2`,
y MUST registrar PASS externo de CycloneDX CLI oficial 0.33.1 contra schema 1.6.

#### Scenario: SBOM exacto

- **GIVEN** el fixture con header/schema/tool/propiedades exactos, 45 identidades y 70 aristas
- **WHEN** el parser local cerrado y la validación externa de schema pasan
- **THEN** `sbom_verified` puede ser verdadero
- **AND** significa conformidad con este perfil y schema, no veracidad universal del contenido.

#### Scenario: Header, schema o herramienta diferentes

- **GIVEN** otro `$schema`, specVersion, tool/version, lifecycle o propiedad del lock
- **WHEN** se valida el SBOM
- **THEN** se rechaza aunque sea un documento CycloneDX válido bajo otro perfil.

### Requirement: Consistencia exacta relativa lock-SBOM

El combinador MUST usar únicamente lock y SBOM capturados en un mismo snapshot
íntegro, MUST igualar el digest del lock con la propiedad SBOM y MUST exigir igualdad
exacta de 45 identidades/fuentes y 70 aristas activadas.

#### Scenario: Evidencia consistente

- **GIVEN** lock y SBOM exactos del mismo perfil
- **WHEN** digest, inventario, fuentes y grafo activado coinciden
- **THEN** `lock_sbom_consistent` puede ser verdadero
- **AND** la evidencia conserva el `RuntimeIdentityRef` del snapshot.

#### Scenario: Divergencia interna

- **GIVEN** un digest, package/source, PURL/BOM-ref o arista diferente
- **WHEN** se combinan lock y SBOM
- **THEN** la evidencia se rechaza sin producir consistencia parcial.

### Requirement: PURL y BOM-ref preservan identidad exacta

El SBOM MUST mantener PURL y `bom-ref` canónicos para cada identidad. Para Torch
`2.14.0+cpu`, MUST conservar `%2Bcpu` en PURL y `+cpu` en `bom-ref`, y el grafo MUST
referenciar `bom-ref` sin confundir ambas representaciones.

#### Scenario: Identidad Torch CPU

- **GIVEN** el componente Torch del perfil
- **WHEN** se normaliza el SBOM
- **THEN** PURL y `bom-ref` permanecen distintos y canónicos
- **AND** las aristas usan la referencia contractual correcta.

### Requirement: Flags positivos con alcance local estricto

`lock_verified`, `sbom_verified` y `lock_sbom_consistent` MUST afirmar sólo
conformidad exacta con este perfil local y consistencia relativa. MUST NOT afirmar
compatibilidad genérica uv/CycloneDX, instalación/build bitwise, origen,
autenticidad, firma, licencia, CVE/seguridad, bytes de distribuciones, checkpoint,
OCI, materialización, executor ni inferencia.

#### Scenario: Evidencia de dependencias válida

- **GIVEN** lock y SBOM exactos y consistentes
- **WHEN** los tres flags locales son verdaderos
- **THEN** config/checkpoint semantics, checkpoint/OCI bytes y OCI semantics permanecen falsos en este objeto
- **AND** origen, materialización, executor e inferencia permanecen falsos.

#### Scenario: Commit unsigned y artefactos no descargados

- **GIVEN** el commit fijado y hashes/URLs de distribuciones
- **WHEN** no existen verificación de firma/origen ni descarga de sus bytes
- **THEN** no se afirma autenticidad, procedencia ni integridad del artefacto remoto
- **AND** no se afirma licencia, ausencia de CVE o seguridad.

### Requirement: Privacidad, pureza y aislamiento

La implementación MUST ocultar payloads, paquetes, URLs y digests en `repr`, errores
y summary; MUST NOT realizar red, filesystem, subprocess, instalación o build; y
MUST permanecer sin caller operativo.

#### Scenario: Summary conservador

- **GIVEN** evidencia lock/SBOM válida
- **WHEN** se serializa el summary público
- **THEN** contiene sólo schema, runtime identity y flags
- **AND** no contiene bytes, paquetes, URLs, grafo ni digests privados.

#### Scenario: Reconciliación sin operación

- **GIVEN** que PR18 resuelve localmente los pendientes lock/SBOM de PR16 y PR17
- **WHEN** OCI, origen y artefactos remotos siguen sin verificarse
- **THEN** PR17 task OCI permanece pendiente
- **AND** no se habilita materialización, executor, inferencia, readiness ni producción.
