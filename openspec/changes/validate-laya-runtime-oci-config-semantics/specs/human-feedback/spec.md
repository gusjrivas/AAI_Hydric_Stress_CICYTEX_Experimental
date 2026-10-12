## ADDED Requirements

### Requirement: La semántica config sólo se evaluará sobre bytes ligados al descriptor PR20

El sistema MUST aceptar exclusivamente `bytes`, verificar primero el tamaño exacto
10.261 y SHA-256
`bdd27ffe0d14dd637985f09bcdf461e58a64348829a4b3ad3cb7886ff56e20c5` del config
único de la evidencia PR20, y sólo después decodificar y parsear. MUST rechazar en
fail-closed payloads sobre 64 KiB, UTF-8/JSON inválido, claves duplicadas, números
no finitos, tipos inesperados o límites estructurales excedidos.

#### Scenario: El payload exacto se valida después del binding

- **WHEN** el caller entrega evidencia PR20 válida y los bytes config cuyo size/SHA coinciden con su descriptor único
- **THEN** el sistema evalúa el perfil semántico cerrado
- **AND** no vuelve a abrir paths ni recaptura desde el FD o estado actual del filesystem

#### Scenario: Un payload distinto falla antes del parser

- **WHEN** tipo, tamaño o SHA-256 no coincide exactamente con el descriptor config PR20
- **THEN** el sistema rechaza sin decodificar ni parsear el JSON
- **AND** no emite evidencia parcial

### Requirement: El perfil observado del config será cerrado y exacto

El sistema MUST exigir `architecture=amd64`, `os=linux`, created epoch UTC, ausencia
de `Cmd`, las 15 entradas Env exactas y ordenadas, los diez Labels exactos,
`Entrypoint=["laya-serve"]`, `User="65532:65532"`, workdir
`/opt/laya-runtime`, rootfs tipo layers con diez DiffIDs SHA-256 declarados y
ordenados, y history con 21 entradas, diez no vacías. Los timestamps de history
MUST usar UTC de segundo entero y MUST ser calendar-valid.

#### Scenario: El perfil exacto es aceptado

- **WHEN** todos los campos, cardinalidades, órdenes, valores y tipos coinciden con el perfil fijado
- **THEN** el sistema produce un perfil validado inmutable
- **AND** reconoce diez DiffIDs sólo como declaraciones, no como hashes calculados de las layers

#### Scenario: Una desviación detectable es rechazada

- **WHEN** aparece `Cmd`, cambia Env/Labels/Entrypoint/User/workdir, cambia cardinalidad u orden, o un timestamp no existe en el calendario
- **THEN** la validación falla cerrada sin evidencia parcial

#### Scenario: Auto-declaraciones no elevan autoridad

- **WHEN** Labels e history coinciden exactamente
- **THEN** el sistema sólo acredita conformidad con el perfil local
- **AND** no los presenta como prueba independiente de source, revision, licencia, base ancestry o proceso de build

### Requirement: La evidencia previa se reconstruirá canónicamente por contenido

Antes de componer PR21, el sistema MUST revalidar profundamente la evidencia PR20,
sus esquemas y tipos exactos, reconstruir un bundle canónico de cinco artefactos
mediante la API pública, reconstruir desde él la metadata OCI pública y comprobar
equivalencia semántica de contenido, commitments, bindings y claims.

#### Scenario: Un clon de clase exacta content-equivalent se acepta

- **WHEN** un clon conserva las clases exactas de prior, snapshot, manifest, spec, proyección OCI, layout y plan, y usa contenido, commitments, bindings y claims equivalentes
- **THEN** el sistema lo reconstruye mediante las APIs públicas y acepta su equivalencia semántica canónica
- **AND** no afirma qué constructor creó el objeto original

#### Scenario: Un carrier CapturedRuntimeArtifact se canoniza

- **WHEN** un wrapper carrier `CapturedRuntimeArtifact` presenta spec, contenido y bindings canónicos exactos
- **THEN** el sistema reconstruye el artefacto mediante la API pública y compara la equivalencia semántica resultante
- **AND** esta excepción no se extiende a ningún tipo de esquema o evidencia

#### Scenario: Un proxy o subclass de evidencia es rechazado

- **WHEN** prior, snapshot, manifest, spec, proyección OCI, layout o plan es un wrapper, proxy o subclass en lugar de su tipo exacto
- **THEN** la validación falla cerrada aunque sus atributos aparenten el mismo contenido
- **AND** no emite evidencia PR21

#### Scenario: Un grafo forjado es rechazado

- **WHEN** cambia un payload, schema, tipo, rol/path, descriptor, flag o enlace del ancestry
- **THEN** la reconstrucción o comparación falla cerrada
- **AND** no emite evidencia PR21

### Requirement: Sólo se elevará la semántica config

La evidencia PR21 MUST preservar los claims verdaderos PR20 y MUST añadir como único
claim nuevo `oci_config_semantics_verified=true`. MUST mantener falsos
`oci_layer_diff_ids_verified`, `oci_rootfs_verified`, `origin_verified`,
`license_verified`, `base_ancestry_verified`, `rootfs_materialized`,
`runtime_materialized`, `executor_available` e `inference_executed`.

#### Scenario: La evidencia config queda sellada con claims conservadores

- **WHEN** ancestry, binding y perfil config son válidos
- **THEN** el sistema emite evidencia inmutable con `oci_config_semantics_verified=true`
- **AND** no eleva DiffIDs, rootfs, origen, licencia, ancestry ni claims operativos

### Requirement: La superficie pública y el summary serán mínimos

El módulo MUST exponer sólo las dos operaciones públicas de validación y summary,
los dos tipos públicos sellados y las constantes de esquema/caps allowlisted. El
summary canónico MUST exponer esquemas, flags y `runtime_identity_sha256`, y MUST
omitir bytes config, Env, Labels, history, paths y digests privados.

#### Scenario: El summary no filtra el perfil privado

- **WHEN** se serializa una evidencia PR21 válida
- **THEN** dos evidencias de clase exacta y semánticamente equivalentes producen los mismos bytes canónicos
- **AND** no aparecen payload, Env, Labels, history, paths ni digests privados

### Requirement: PR21 conservará la frontera operacional de PR20

El sistema MUST mantener los cinco roles de artefactos sin versionar el blob config
y MUST permanecer sin caller productivo. PR21 MUST NOT acceder ni modificar la raíz
OCI y MUST NOT presentarse como enforcement de permisos o mount read-only, CI
obligatorio, materialización o ejecución.

#### Scenario: La suite ordinaria no fabrica evidencia externa

- **WHEN** se ejecutan los tests sin evidencia OCI externa
- **THEN** sólo se usa construcción sintética para probar el contrato
- **AND** no se afirma captura real, estado filesystem actual ni ejecución del runtime

#### Scenario: El gate real sigue siendo manual

- **WHEN** se ejecuta el gate Linux con evidencia externa
- **THEN** su resultado se registra como evidencia manual opt-in
- **AND** no se interpreta como job obligatorio de CI ni enforcement read-only del host

### Requirement: El cálculo de DiffIDs quedará fuera de PR21

PR21 MUST NOT descomprimir layers ni comparar hashes calculados con
`rootfs.diff_ids`. Esa autoridad MUST permanecer falsa hasta un successor dedicado.

#### Scenario: Los DiffIDs declarados se reservan para PR22

- **WHEN** el config contiene los diez DiffIDs exactos del perfil
- **THEN** PR21 conserva `oci_layer_diff_ids_verified=false` y `oci_rootfs_verified=false`
- **AND** PR22 deberá calcularlos por streaming desde las diez layers descomprimidas
