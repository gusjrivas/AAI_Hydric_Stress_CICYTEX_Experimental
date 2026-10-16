## ADDED Requirements

### Requirement: El plan TAR estará ligado exactamente a evidencia PR22

El sistema MUST aceptar sólo evidencia PR22 exacta y profundamente válida, y MUST
producir un plan inmutable que preserve por identidad la runtime identity, layout,
diez blobs y diez receipts DiffID en el mismo orden. Preparar el plan MUST NOT abrir
archivos ni consumir chunks.

#### Scenario: Se prepara el plan exacto sin I/O

- **WHEN** la evidencia PR22 y todo su ancestry son válidos
- **THEN** el sistema liga exactamente diez posiciones a la misma identidad y receipts
- **AND** mantiene falso TAR/rootfs hasta verificar los streams

#### Scenario: Un ancestry u orden inválido falla cerrado

- **WHEN** cambia tipo, schema, identidad, binding, orden o cardinalidad
- **THEN** el sistema rechaza antes de abrir o consumir bytes
- **AND** no emite plan parcial utilizable

### Requirement: Cada layer se validará como TAR streaming después de bytes y DiffID

El sistema MUST revalidar size/SHA-256 comprimido, gzip single-member y DiffID PR22
sobre el mismo stream que alimenta el parser TAR. MUST procesar bloques lógicos de
512 bytes incrementalmente y MUST NOT sellar un receipt si cualquiera de las dos
validaciones falla.

#### Scenario: Una layer exacta produce un receipt TAR ligado

- **WHEN** los bytes comprimidos, DiffID y TAR cumplen el plan en la misma posición
- **THEN** el sistema emite un receipt sellado con `tar_semantics_verified=true`
- **AND** conserva falso rootfs y origin

#### Scenario: Un stream falla antes de completar todas las capas

- **WHEN** falla el blob, gzip, DiffID, TAR, orden o presupuesto
- **THEN** el sistema no emite receipt agregado ni evidencia parcial

### Requirement: Headers, payload, padding y terminación serán exactos

El sistema MUST validar el checksum del header antes de confiar en path, typeflag o
size. MUST consumir el payload declarado y padding cero a múltiplo de 512. MUST
exigir al menos dos bloques cero terminales y MUST rechazar trailing no cero,
headers o payloads truncados y numeric fields fuera del perfil.

#### Scenario: Un TAR mínimo exacto termina limpiamente

- **WHEN** todos los headers tienen checksum válido, payload/padding exactos y dos bloques cero finales
- **THEN** el parser termina sin retener payload completo en memoria

#### Scenario: Checksum o padding inválido falla antes de afirmar semántica

- **WHEN** el checksum no coincide, un campo no es válido o el padding contiene bytes no cero
- **THEN** el sistema falla cerrado sin receipt TAR

### Requirement: PAX y GNU estarán soportados bajo un perfil cerrado

El sistema MUST soportar PAX local/global y GNU longname/longlink con UTF-8,
precedencia, scope y límites explícitos. MUST rechazar records malformados,
metadata pendiente, overrides contradictorios, claves sensibles ambiguas, sparse,
devices, FIFO y typeflags no autorizados.

#### Scenario: Un override válido determina la entrada efectiva

- **WHEN** PAX o GNU proporciona un path o link válido dentro de sus límites
- **THEN** el parser aplica una única precedencia determinista a la siguiente entrada

#### Scenario: Una extensión ambigua o no soportada falla cerrada

- **WHEN** aparece sparse, un typeflag no permitido o metadata contradictoria
- **THEN** el sistema rechaza la layer sin fallback permisivo

### Requirement: El root marker tendrá un único perfil estructural

El sistema MAY aceptar `./` como root marker sólo bajo el perfil exacto de los
escenarios siguientes. MUST rechazar el nombre raw `.` y todo override PAX/GNU a
`.` o `./`. El marker MUST permanecer fuera del manifest y MUST NOT elevar claims
de rootfs.

#### Scenario: El root marker exacto se acepta sin crear una entry

- **WHEN** uno o más headers usan exactamente `./`, typeflag `5`, size `0`, link raw vacío y ninguna metadata PAX/GNU local/global/pendiente
- **THEN** cada marker cuenta para header/cardinalidad y bytes TAR, pero no para payload, manifest ni paths duplicados
- **AND** su repetición no eleva `oci_rootfs_verified` ni ningún claim de composición

#### Scenario: Un root marker ambiguo se rechaza

- **WHEN** el nombre raw es `.`, `./` tiene otro typeflag, size o link, existe metadata local/global/pendiente, o PAX/GNU intenta override a `.` o `./`
- **THEN** el sistema falla cerrado sin receipt TAR
- **AND** no normaliza el caso ambiguo como una entry ordinaria

### Requirement: Los paths efectivos serán seguros y únicos por layer

El sistema MUST calcular el path efectivo de cada entry después de PAX/GNU mediante
normalización POSIX lexical independiente del host. MUST rechazar entry paths
absolutos, UNC/drive, backslash, NUL/control, componentes `..` y paths vacíos. MUST
rechazar una segunda entry real cuyo path efectivo normalizado ya haya aparecido
en la misma layer.

#### Scenario: Dos spellings colisionan en el mismo path efectivo

- **WHEN** dos entries resuelven al mismo path por componentes `.`, slash final o override PAX/GNU
- **THEN** la segunda entry se rechaza como duplicada
- **AND** el sistema no aplica una regla implícita de last-write-wins

#### Scenario: Un target de link se conserva como metadata opaca

- **WHEN** un symlink o hardlink tiene un target POSIX absoluto o con componentes `..`
- **THEN** PR32 acepta y conserva el target byte-exacto bajo caps, encoding válido y ausencia de NUL/control
- **AND** no lo resuelve, sigue ni aplica contra filesystem

#### Scenario: Un target de link viola el contrato de metadata

- **WHEN** el target excede su cap o contiene encoding inválido, NUL o caracteres de control
- **THEN** el sistema rechaza la layer sin exponer el target

#### Scenario: Un nombre whiteout sólo recibe validación de path

- **WHEN** una entry segura tiene un nombre `.wh.*`
- **THEN** participa en la unicidad como cualquier otro path
- **AND** PR32 no la interpreta ni aplica como whiteout

### Requirement: La resolución de links permanecerá diferida

El sistema MUST mantener falsos todos los claims de rootfs y MUST NOT decidir en
PR32 si un target de symlink/hardlink queda dentro de la raíz, existe, queda
dangling, forma ciclos o es válido después de overlays. Esas propiedades MUST
permanecer bloqueadas hasta la composición controlada de PR33.

#### Scenario: Un receipt TAR contiene targets aún no resueltos

- **WHEN** la estructura TAR y la metadata de links cumplen PR32
- **THEN** el receipt puede afirmar semántica TAR estructural
- **AND** mantiene `oci_rootfs_verified=false` sin inferir seguridad de resolución

### Requirement: El parser resistirá bombas de metadata y cardinalidad

El sistema MUST aplicar caps positivos exactos a chunks, output, entries, path/link,
PAX/GNU, payload y bytes TAR agregados. MUST rechazar budgets inválidos antes de
consumir el generador y MUST fallar antes de leer payload cuando un header válido
declara un tamaño fuera del presupuesto.

#### Scenario: Una bomba de entries de tamaño cero alcanza el límite

- **WHEN** la cantidad de headers excede el máximo aunque sus payloads sean vacíos
- **THEN** el sistema falla cerrado sin crecimiento no acotado del manifest

#### Scenario: Un tamaño declarado excede el presupuesto

- **WHEN** un header válido declara payload mayor que el límite restante
- **THEN** el sistema rechaza antes de consumir ese payload

### Requirement: La captura secure-FD será same-root y all-or-nothing

El adaptador Linux MUST fallar antes de abrir si la evidencia PR22 es inválida o
faltan capacidades seguras. MUST recapturar controles e inventario, rehashéar las
doce blobs, verificar las diez layers, comparar fingerprints, ejecutar el sweep
final y cerrar todos los FDs owned antes de sellar.

#### Scenario: La captura completa produce evidencia TAR

- **WHEN** 12 revalidaciones blob, 10 verificaciones DiffID+TAR, inventario, fingerprints y sweep son válidos
- **THEN** el adaptador cierra todos los descriptores exactamente una vez
- **AND** sólo entonces sella diez receipts ordenados y evidencia same-root

#### Scenario: Un fallo temporal impide autoridad parcial

- **WHEN** falla open/read/fstat/scandir/close o cambia un path, inode, blob o inventario
- **THEN** el adaptador limpia los FDs y no sella autoridad ni evidencia

### Requirement: Sólo se elevará la semántica TAR

La evidencia PR32 MUST heredar los claims verdaderos PR22 y MUST añadir como único
claim nuevo `tar_semantics_verified=true`. MUST mantener falsos
`oci_rootfs_verified`, `rootfs_materialized`, origen, licencia, base ancestry,
checkpoint, runtime materialized, executor e inferencia.

#### Scenario: Diez receipts TAR cierran únicamente el claim TAR

- **WHEN** existen exactamente diez receipts válidos, ordenados y ligados a la misma captura
- **THEN** el sistema emite evidencia inmutable con `tar_semantics_verified=true`
- **AND** aceptar root markers `./` no eleva whiteouts/rootfs, provenance ni claims operativos

### Requirement: PR32 preservará privacidad y frontera operacional

El sistema MUST conservar los cinco roles y la runtime identity, mantener blobs
fuera de Git y permanecer sin caller productivo. El summary MUST exponer sólo
schemas, flags y `runtime_identity_sha256`, y MUST omitir raíz, paths, links,
digests, DiffIDs, sizes, counts, metadata y payloads.

#### Scenario: El summary no filtra evidencia privada

- **WHEN** se serializa evidencia PR32 válida
- **THEN** se producen bytes canónicos deterministas con schemas, claims y commitment de identidad
- **AND** no aparecen valores privados del TAR ni del filesystem

#### Scenario: El gate externo no amplía autoridad operacional

- **WHEN** se ejecuta el gate real serial y opt-in sobre Linux
- **THEN** su resultado se registra como evidencia manual de semántica TAR
- **AND** no se presenta como CI obligatorio, rootfs válido, materialización o ejecución
