## ADDED Requirements

### Requirement: El perfil externo de base SHALL congelarse antes del RED positivo

El sistema MUST definir dentro del módulo un perfil cerrado derivado de captura
independiente: index digest/media type/size, selección Linux/amd64 única, manifest,
config, plataforma, cardinalidades, tuples y caps exactos. Los callers MUST NOT
poder reemplazar esos valores. El perfil MUST contener el index de 9.131 bytes y 14
descriptors, un único manifest Linux/amd64 de 1.752 bytes, un config de 5.295 bytes,
exactamente cuatro layers base y exactamente cuatro DiffIDs base.

#### Scenario: La captura completa habilita el contrato positivo

- **WHEN** index, manifest, config, tuples y caps fueron capturados y documentados por bytes
- **THEN** OpenSpec congela todos los valores exactos antes del primer RED positivo
- **AND** el módulo queda como única autoridad del perfil aceptado

#### Scenario: Un dato todavía desconocido no se infiere

- **WHEN** falta tipo root, plataforma, digest, size, media type, objeto o cardinalidad
- **THEN** el perfil positivo permanece bloqueado
- **AND** ninguna annotation o suposición completa el dato faltante

### Requirement: El plan de ancestry SHALL depender sólo de evidencia PR22 issued

`prepare_laya_runtime_base_ancestry_plan` MUST aceptar sólo evidencia exacta,
issued y profundamente válida de PR22. MUST preservar por identidad el runtime,
config/layout ancestry, descriptors comprimidos, receipts y DiffIDs ordenados. MUST
NOT consumir bytes ni aceptar evidencia PR35 como predecessor.

#### Scenario: Evidencia PR22 exacta produce un plan puro

- **WHEN** la evidencia PR22 issued y todo su ancestry son válidos
- **THEN** se emite un plan inmutable ligado a la misma identidad y tuples ordenados
- **AND** `base_ancestry_verified` permanece falso hasta verificar objetos externos

#### Scenario: Un clon o autoridad lateral falla antes de consumir bytes

- **WHEN** se aporta una instancia fabricada, clonada, derivada, replayed, mezclada o una evidencia PR35 por equivalencia de fields
- **THEN** el sistema rechaza el input antes de iterar cualquier stream
- **AND** no registra ni presta autoridad al objeto del caller

### Requirement: Los objetos externos SHALL verificarse por contenido y grafo exacto

`verify_laya_runtime_base_ancestry_objects` MUST consumir únicamente el tuple de
streams exacto del perfil, con chunks `bytes` estrictos y caps cerrados. MUST
verificar SHA-256/size antes de parsear y MUST reconstruir cada arista
index/manifest/config por digest, size y media type. La selección de plataforma MUST
seguir exactamente la forma capturada, sin fallback a tags o annotations.

#### Scenario: El grafo content-addressed exacto se acepta

- **WHEN** todos los objetos coinciden por bytes y cada descriptor enlaza el único manifest/config congelado
- **THEN** el sistema obtiene el tuple externo de layers y DiffIDs del mismo grafo
- **AND** todavía no sella evidencia hasta validar el prefijo dual

#### Scenario: Mismatch, ambigüedad o perfil alternativo fallan cerrados

- **WHEN** cambia un byte, size, digest, media type, plataforma, orden, cardinalidad o aparece un descriptor alternativo/extra
- **THEN** el sistema revoca la sesión y no produce evidencia parcial
- **AND** deja de consumir iterables posteriores al primer fallo

### Requirement: Parsing y consumo SHALL permanecer estrictos y acotados

El sistema MUST rechazar chunks vacíos/no-bytes, objetos o agregados sobre cap,
JSON con claves duplicadas, fields/tipos extra, números no permitidos, trailing
bytes, profundidad/items/strings excesivos o representación no canónica. Los caps
MUST tener una única fuente de verdad usada por plan, verificador y tests: 16 KiB
por chunk, 64 chunks por objeto, 16 KiB por objeto, 32 KiB agregados, profundidad
JSON 16, 512 nodos, strings de 4 KiB, arrays de 32 items y objetos de 64 keys.

#### Scenario: Cada límite exacto se acepta

- **WHEN** chunks, counts, sizes, profundidad e items coinciden con el límite congelado
- **THEN** el consumo incremental puede completar la validación sin carga ilimitada

#### Scenario: `cap + 1` aborta de forma perezosa

- **WHEN** cualquier dimensión excede su cap por una unidad
- **THEN** el sistema falla antes de consumir datos innecesarios
- **AND** no emite receipt, autoridad ni evidencia reutilizable

### Requirement: La ancestry SHALL exigir prefijo dual comprimido y DiffID

El tuple completo y no vacío de descriptors comprimidos de la base MUST ser el
prefijo exacto del tuple comprimido PR22. El tuple completo de DiffIDs de la base
MUST ser el prefijo exacto del tuple DiffID PR22 con idéntica cardinalidad y
posición. Ambas condiciones MUST cumplirse en la misma sesión.

#### Scenario: El prefijo dual exacto demuestra la relación acotada

- **WHEN** cada descriptor base coincide en digest/size/media type y cada DiffID base coincide en la misma posición PR22
- **THEN** la relación de cadena OCI queda verificada para el perfil congelado
- **AND** las layers Laya posteriores quedan fuera del claim de la base

#### Scenario: Coincidencia parcial o reordenada se rechaza

- **WHEN** sólo coincide compressed o DiffID, el match es una subsecuencia no inicial, hay reorder/duplicado/inserción o difiere la cardinalidad
- **THEN** el sistema falla cerrado
- **AND** no interpreta igualdad de conjunto como ancestry posicional

### Requirement: Las recetas observadas SHALL permanecer fuera de la autoridad positiva

La API positiva MUST NOT consumir bytes de receta ni usarlos para sellar ancestry.
El sistema MUST mantener falsos `runtime_build_recipe_verified`,
`build_process_attested` y `reproducible_build_verified`. La receta oficial Python
observada y el Dockerfile Laya discrepante MUST documentarse como limitación, no
como prueba de ejecución o reproducibilidad.

#### Scenario: Ancestry de contenido válida no prueba el proceso de build

- **WHEN** index, manifest, config y ambos prefijos son exactos
- **THEN** puede elevarse sólo `base_ancestry_verified`
- **AND** receta ejecutada, build attested y reproducibilidad permanecen falsos

#### Scenario: La discrepancia del Dockerfile Laya no se oculta

- **WHEN** el Dockerfile recapturado declara base trixie, usuario 10001 y entrypoint Python incompatibles con el runtime observado
- **THEN** la diferencia queda registrada como evidencia negativa
- **AND** no se adapta el contrato para fabricar una receta positiva

### Requirement: La evidencia SHALL ser issued, all-or-nothing y no replayable

Plan, receipts, autoridad y evidencia MUST ser exact-class e issued por factories
privadas registradas por identidad. La validación MUST NOT prestar tokens. Cada
sesión MUST consumirse una sola vez y MUST rechazar mezcla, clone, pickle/copy,
replay luego de success o reutilización luego de fallo.

#### Scenario: Una sesión completa sella una única evidencia

- **WHEN** los tres objetos, grafo y prefijo dual terminan válidos bajo el mismo plan/sesión
- **THEN** el sistema sella una evidencia inmutable exactamente una vez

#### Scenario: Una falsificación con fields equivalentes no adquiere autoridad

- **WHEN** un caller replica todos los fields mediante construcción insegura o reutiliza receipts de otra sesión
- **THEN** validación y summary rechazan por identidad de issuance
- **AND** no se crea registro de confianza durante la revalidación

### Requirement: PR36 SHALL elevar sólo base ancestry con privacidad mínima

La evidencia MUST heredar claims PR22 y añadir únicamente
`base_ancestry_verified=true`. MUST mantener falsos origen, licencia,
`runtime_build_recipe_verified`, `build_process_attested`,
`reproducible_build_verified`, materialización, executor e inferencia. El summary
MUST exponer sólo schemas, flags,
runtime identity commitment y commitments allowlisted; MUST omitir payloads, paths,
URLs/auth, digests internos, sizes y tuples.

#### Scenario: Evidencia válida eleva el claim conservador

- **WHEN** la sesión completa fue verificada y sellada
- **THEN** `base_ancestry_verified` es verdadero
- **AND** origen, licencia, receta/build/reproducibilidad, rootfs/runtime materialized, executor e inferencia permanecen falsos

#### Scenario: El summary no filtra ni amplía autoridad

- **WHEN** se serializa una evidencia issued válida
- **THEN** los bytes canónicos contienen sólo fields públicos allowlisted
- **AND** no declaran receta ejecutada, build attested, reproducibilidad, firma, builder, disponibilidad de registry, convergencia PR35 ni readiness operacional

### Requirement: La convergencia supply SHALL permanecer diferida a PR37

PR36 MUST NOT combinar evidencia PR35 ni afirmar que source, checkpoint, imagen y
base pertenecen a una única captura convergente. Su módulo MUST permanecer sin I/O,
adapter, caller productivo o dependencia de UI/backend.

#### Scenario: PR35 existe pero no integra el grafo PR36

- **WHEN** PR35 está disponible en la rama base
- **THEN** el plan PR36 sigue aceptando exclusivamente PR22 como predecessor
- **AND** PR37 queda como único slice autorizado para rechazar mix-and-match global

#### Scenario: El gate no cambia resultados científicos

- **WHEN** PR36 se verifica o falla
- **THEN** no cambian datasets, splits, forecasts, probabilidades, feedback ni corridas históricas
- **AND** ningún resultado autoriza automatizar riego o habilitar producción
