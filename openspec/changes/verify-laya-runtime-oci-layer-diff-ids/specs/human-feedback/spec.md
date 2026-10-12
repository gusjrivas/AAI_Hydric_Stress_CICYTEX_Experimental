## ADDED Requirements

### Requirement: El plan DiffID estará ligado exactamente a PR21

El sistema MUST aceptar sólo evidencia PR21 exacta y válida, y MUST producir un plan
inmutable que preserve la misma runtime identity, layout/evidence PR20, diez blobs
`layer-00`…`layer-09`, diez receipts comprimidos y diez DiffIDs declarados en el
mismo orden. Preparar el plan MUST NOT leer ni descomprimir archivos.

#### Scenario: Se prepara el plan exacto sin I/O

- **WHEN** la evidencia PR21 y todo su ancestry son válidos
- **THEN** el sistema liga exactamente diez posiciones blob/receipt/DiffID a la misma identidad
- **AND** mantiene falsos DiffID, rootfs y origin hasta capturar los streams

#### Scenario: Un ancestry o cardinalidad inválidos fallan cerrados

- **WHEN** cambia tipo, schema, identidad, binding, rol, orden o cardinalidad
- **THEN** el sistema rechaza antes de abrir o consumir bytes
- **AND** no emite plan parcial utilizable

### Requirement: Cada DiffID se verificará después del blob comprimido exacto

El sistema MUST autorizar un digest único del plan, MUST revalidar size/SHA-256 de
los bytes comprimidos mediante el contrato PR20 y MUST calcular incrementalmente
`sha256` del único member gzip descomprimido. El resultado MUST coincidir con el
DiffID declarado en la misma posición.

#### Scenario: Una layer exacta produce un receipt ligado por posición

- **WHEN** el stream comprimido coincide con su descriptor y su contenido descomprimido coincide con el DiffID declarado de esa posición
- **THEN** el sistema emite un receipt sellado con `compressed_blob_bytes_verified=true` y `layer_diff_id_verified=true`
- **AND** conserva falsos TAR, rootfs y origin

#### Scenario: El blob o DiffID no coincide

- **WHEN** cambia tamaño/SHA comprimido o el SHA-256 descomprimido no coincide con el DiffID declarado
- **THEN** el sistema falla cerrado
- **AND** no emite receipt parcial

### Requirement: La descompresión será single-member y acotada

El sistema MUST aceptar únicamente chunks `bytes` exactos, no vacíos, de hasta
1 MiB y como máximo 1.024 por layer. MUST limitar cada salida incremental a 1 MiB,
cada layer a 2 GiB descomprimidos y el agregado a 3 GiB. MUST rechazar stream
truncado, CRC/ISIZE inválido, trailing data, segundo member o falta de progreso.

#### Scenario: El único member gzip termina limpiamente

- **WHEN** un stream autorizado contiene exactamente un member gzip válido sin bytes posteriores
- **THEN** el sistema consume y hashea el contenido incrementalmente dentro de los caps

#### Scenario: Multi-member o expansión excesiva se rechazan

- **WHEN** aparece un segundo member, trailing data, chunk/cantidad fuera de límite, una layer supera 2 GiB o el agregado supera 3 GiB
- **THEN** el sistema falla cerrado sin evidencia agregada
- **AND** no afirma compatibilidad gzip multi-member genérica

### Requirement: La captura secure-FD cubrirá las diez layers all-or-nothing

El adaptador Linux MUST fallar antes de abrir si falta capacidad segura o la
evidencia PR21 es inválida. MUST operar descriptor-relative desde una única raíz,
revalidar las doce blobs comprimidas, verificar luego las diez layers por posición,
comparar fingerprints entre pasadas, ejecutar el sweep final y cerrar todos los FDs
owned antes de sellar.

#### Scenario: La captura completa produce autoridad

- **WHEN** inventario, 12 revalidaciones blob, 10 verificaciones DiffID, fingerprints y sweep final son válidos
- **THEN** el adaptador cierra todos los descriptores exactamente una vez
- **AND** sólo entonces sella diez receipts ordenados y evidencia same-root

#### Scenario: Cualquier fallo impide evidencia parcial

- **WHEN** falla open/read/scandir/fstat/close, cambia un path/inode/blob, falta o sobra inventario, o falla gzip/digest/cap
- **THEN** el adaptador cierra los FDs owned y no sella autoridad ni evidencia

### Requirement: Sólo se elevará la verificación DiffID

La evidencia PR22 MUST heredar los claims verdaderos PR20/PR21 y MUST añadir como
único claim nuevo `oci_layer_diff_ids_verified=true`. MUST mantener falsos
`tar_semantics_verified`, `oci_rootfs_verified`, `origin_verified`,
`license_verified`, `base_ancestry_verified`, materialización, executor e inferencia.

#### Scenario: Diez receipts válidos cierran el claim DiffID

- **WHEN** existen exactamente diez receipts sellados, ordenados y ligados al mismo plan/identity/captura
- **THEN** el sistema emite evidencia inmutable con `oci_layer_diff_ids_verified=true`
- **AND** no eleva TAR, whiteouts/rootfs, provenance/licencia/base ni claims operativos

### Requirement: PR22 preservará roles, privacidad y frontera operacional

El sistema MUST conservar los cinco roles y la runtime identity existentes, MUST
mantener las layers fuera de Git y MUST permanecer sin caller productivo. El summary
MUST exponer sólo schemas, flags y `runtime_identity_sha256`; MUST omitir raíz,
paths, digests comprimidos, DiffIDs, tamaños y contenidos.

#### Scenario: El summary no filtra evidencia privada

- **WHEN** se serializa evidencia PR22 válida
- **THEN** se producen bytes canónicos deterministas con schemas, claims y commitment de identidad
- **AND** no aparecen paths, digests, DiffIDs, tamaños ni payloads privados

#### Scenario: El gate externo no amplía autoridad operacional

- **WHEN** se ejecuta el gate real serial sobre Linux
- **THEN** su resultado se registra como evidencia manual opt-in
- **AND** no se presenta como CI obligatorio, snapshot filesystem absoluto, TAR/rootfs válido, materialización o ejecución
