# Diseño: identidad canónica foundation-only del runtime Laya

## Contexto y límite de confianza

PR14 necesita una `RuntimeIdentityRef`, pero una referencia sin manifest sólo liga la
evidencia a un digest opaco. Este slice define el contenido declarativo que produce
ese digest. Su frontera es deliberadamente pura: parsea bytes JSON, valida el schema
y calcula identidad. La existencia de paths, la integridad de archivos y la
autenticidad de la fuente quedan fuera de su capacidad.

## Decisiones

### 1. Parser bytes-only y schema cerrado

`load_laya_runtime_manifest_bytes` recibe exclusivamente bytes UTF-8. El parser
rechaza JSON inválido, claves duplicadas y constantes numéricas no finitas. Tanto el
manifest como cada artefacto deben contener exactamente sus campos versionados; no
se ignoran extensiones desconocidas ni se aplican defaults implícitos.

Los objetos `LayaRuntimeManifest`, `RuntimeArtifactSpec` y `RuntimeIdentityRef` son
inmutables y slotted. Construcción directa o `replace` vuelve a validar el estado y
no permite forjar flags ni `identity_sha256`.

### 2. Fuente y entorno exactos

El manifest fija:

- schema `laya-runtime-manifest-v1`;
- runtime `laya-0.4.2-python-3.11.10-linux-amd64`;
- proveedor `laya-http` y engine `laya==0.4.2`;
- fuente exacta
  `https://github.com/NandhaKishorM/laya@68804629e8ccd9d616d48a40e87de9fabbeae069`;
- licencia declarada `Apache-2.0`, Python `3.11.10` y plataforma `linux/amd64`;
- imagen base `docker.io/library/python@sha256:<digest-lowercase-no-nulo>`.

Estos valores expresan la identidad objetivo para el release 0.4.2. El parser no
consulta GitHub, un registro OCI ni metadata de licencia, por lo que no los convierte
en attestations verificadas.

### 3. Cinco roles exactos y paths únicos

Cada manifest contiene exactamente una entrada de los siguientes roles, ordenados
canónicamente:

| Rol | Formato | Path contractual |
| --- | --- | --- |
| `dependency_lock` | `uv-lock-v1` | `locks/uv.lock` |
| `sbom` | `cyclonedx-json-1.6` | `sbom/laya-runtime.cdx.json` |
| `runtime_config` | `json` | `config/runtime.json` |
| `checkpoint_manifest` | `json` | `manifests/checkpoint.json` |
| `oci_manifest` | `oci-image-manifest-v1` | `manifests/oci.json` |

Cada declaración incluye SHA-256 lowercase no nulo y `size_bytes` entero positivo.
Los paths son relativos, POSIX, ASCII y canónicos; se rechazan absolutos, backslashes,
segmentos `.`/`..`, separadores repetidos y paths duplicados entre roles. Validar
estas cadenas no implica que los archivos existan o tengan los bytes declarados.

### 4. Identidad canónica e integración por referencia

El loader reordena artefactos por rol y serializa el manifest como JSON canónico. El
SHA-256 de esos bytes es `identity_sha256`; cambios semánticos en metadata, roles,
digests o tamaños cambian la identidad, mientras el orden de claves, indentación y
orden de entrada de artefactos no la alteran.

`runtime_identity_ref` proyecta el manifest a
`RuntimeIdentityRef(schema_version="laya-runtime-identity-v1", sha256=...)`. PR14
importa esta misma clase, evitando dos tipos nominalmente similares. Esto preserva
el summary golden de PR14 y no hace que el contrato de ejecución lea o materialice el
manifest.

### 5. Separación de repositorio y checkpoint

La única fuente de código aceptada por este manifest es
`NandhaKishorM/laya` en el commit fijado. `convaiinnovations/laya` se trata
exclusivamente como posible procedencia futura de un checkpoint, no como repositorio
source alternativo. Su uso exige otro cambio TDD que revise licencia, origen,
compatibilidad con 0.4.2, contenido y digest antes de incorporarlo.

### 6. Flags fail-closed

El manifest sólo declara `structurally_valid=true`. Permanecen inmutables en falso:

- `artifact_integrity_verified`;
- `lock_verified` y `sbom_verified`;
- `lock_sbom_consistent`;
- `checkpoint_bytes_verified` y `oci_bytes_verified`;
- `runtime_materialized` y `origin_verified`;
- `executor_available` e `inference_executed`.

Ninguna función de este slice cambia esos estados.

### 7. TDD e aislamiento

La cadena TDD comenzó con RED para parser cerrado, fuente exacta, cinco roles,
canonicalización, identidad sensible, compatibilidad de referencia, flags e
aislamiento. GREEN implementó únicamente el contrato puro necesario para satisfacer
esas pruebas y conservó sin cambios el summary público de PR14.

El módulo no es importado por adapters, backend, readiness, experiment runners ni
scripts. Los próximos slices verificarán supply y bytes, materializarán el runtime y,
en un cambio posterior, introducirán el executor e inferencia con nuevos RED previos.

## Consecuencias

- Existe una identidad reproducible y semánticamente sensible del runtime objetivo.
- El contrato distingue declaración de identidad de verificación de integridad y
  procedencia.
- La compatibilidad con PR14 no abre un camino operativo hacia Laya.
- Readiness científico y productivo continúan bloqueados.
