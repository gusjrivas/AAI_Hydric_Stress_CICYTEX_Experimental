## Context

PR20 fijó controles e inventario de doce blobs OCI. PR21 validó el config y sus
diez DiffIDs. PR22 recapturó el layout desde una raíz Linux descriptor-relative,
revalidó los bytes comprimidos y comprobó por streaming los diez DiffIDs. Su
evidencia mantiene `tar_semantics_verified=false` y `oci_rootfs_verified=false`.

PR32 cierra sólo la frontera TAR. El layout grande permanece fuera de Git, el gate
real continúa manual/serial/opt-in y no existe caller productivo.

## Goals / Non-Goals

### Goals

- Ligar exactamente diez validaciones TAR a la evidencia PR22 y a su identidad.
- Validar incrementalmente un perfil TAR cerrado, seguro y acotado.
- Rechazar ambigüedad de paths efectivos dentro de cada layer.
- Capturar desde una única raíz Linux y sellar evidencia all-or-nothing.
- Elevar exclusivamente `tar_semantics_verified`.

### Non-Goals

- Interpretar `.wh.*`, opaque directories o aplicar overlays OCI.
- Afirmar o materializar un rootfs.
- Extraer archivos o seguir links en filesystem.
- Soportar TAR genérico, sparse files, devices, FIFO o extensiones no fijadas.
- Probar procedencia, licencia, base ancestry, checkpoint o ejecución.

## Decisions

### 1. Núcleo puro y successor identity-bound

`runtime_oci_tar.py` será dueño del plan, parser, receipts y evidencia TAR. La API
pública mínima será:

- `prepare_laya_oci_tar_semantics_plan(layer_evidence)`;
- `verify_laya_oci_tar_semantics_chunks(plan, digest, compressed_chunks, ...)`;
- `canonical_laya_runtime_oci_tar_semantics_summary_bytes(evidence)`.

El plan aceptará sólo `LayaRuntimeOciLayerDiffIdsEvidence` exacta y profundamente
válida. Conservará por identidad la misma runtime identity, layout plan, diez blobs
y diez receipts DiffID en orden. Prepararlo no hará I/O ni consumirá chunks.

Los tipos públicos sellados serán `LayaOciTarSemanticsPlan`,
`LayaOciTarEntry`, `VerifiedLayaOciTarLayer` y
`LayaRuntimeOciTarSemanticsEvidence`. Sus representaciones serán privadas y su
construcción directa, `replace`, subclases y clones inconsistentes fallarán
cerrados. La lista ordenada de entries será inmutable y privada; PR32 no expondrá
un finalizador público.

### 2. Reutilización controlada del streaming PR22

`runtime_oci_layers.py` podrá extraer una primitiva privada que entregue cada
chunk descomprimido a un consumidor acotado. La firma y comportamiento de
`verify_laya_oci_layer_diff_id_chunks` no cambiarán. Sólo `runtime_oci_tar.py`
podrá usar el bridge privado, con un detector AST que bloquee imports, aliases,
`getattr`, `__import__` y consumidores adicionales.

La verificación TAR no confiará en un stream descomprimido arbitrario: el mismo
flujo comprimido deberá volver a satisfacer size/SHA-256, gzip single-member y
DiffID PR22 mientras alimenta al parser. Ningún estado provisional se convertirá
en receipt antes de completar ambas validaciones.

### 3. Máquina TAR incremental

El parser procesará bloques lógicos de 512 bytes sin `join` global ni buffers
proporcionales a tamaños declarados. Antes de usar nombre, typeflag o size deberá:

1. recibir un header completo;
2. reconocer un encoding permitido;
3. validar el campo checksum;
4. comparar el checksum calculado con el declarado;
5. recién entonces interpretar campos y reservar presupuesto.

Cada entrada consumirá exactamente su payload declarado y su padding a múltiplo
de 512. El padding deberá ser cero. El archivo terminará con al menos dos bloques
cero consecutivos; luego sólo se aceptarán bloques cero completos. Header
truncado, payload incompleto, un único bloque terminal o trailing no cero fallarán.

El perfil admitirá entries regulares, directorios, symlinks y hardlinks. PAX
local/global y GNU longname/longlink serán pseudo-entries acotadas que modifican
la entrada efectiva siguiente según una precedencia única documentada y probada.
Overrides contradictorios, metadata pendiente al EOF, UTF-8 inválido, NUL,
records PAX malformados o repetición ambigua de claves sensibles fallarán.
GNU/PAX sparse, devices, FIFO y typeflags desconocidos se rechazarán.

### 4. Paths efectivos únicos y seguros

La normalización será POSIX y lexical, independiente del host. Rechazará paths
absolutos, UNC/drive, backslash, NUL/control, componentes `..`, path efectivo
vacío y exceso de bytes o componentes. Podrá eliminar componentes `.` y slash
final de directorio sin cambiar el destino.

El path efectivo se calcula después de aplicar PAX/GNU. Dos entries reales de la
misma layer no podrán terminar en el mismo path normalizado: la segunda se
rechazará, aunque la colisión provenga de spellings distintos, slash final,
longname o `path` PAX. Esta regla evita depender de last-write-wins ambiguo y es
coherente con el perfil OCI cerrado adoptado para esta imagen.

Los targets de symlink y hardlink se tratarán como strings POSIX opacos. PR32
validará únicamente encoding, cap de bytes y ausencia de NUL/control; aceptará
targets absolutos y componentes `..` porque existen en el layout real y todavía no
se interpretan ni aplican. Los targets se conservarán privados y byte-exactos tras
el override PAX/GNU. Resolución root-bound, existencia, dangling, ciclos y efectos
entre layers pertenecen exclusivamente a PR33.

Los nombres `.wh.*` se validarán como paths ordinarios y también participarán en
la unicidad, pero no se clasificarán ni aplicarán como whiteouts todavía.

### 5. Límites y resistencia a bombas

Los caps serán constantes públicas, enteros positivos exactos y con tests de
frontera. Como mínimo cubrirán chunks comprimidos heredados, output incremental,
entries por layer, bytes de path/link, cantidad y bytes PAX/GNU, tamaño de una
entry, payload agregado y bytes TAR agregados. `bool`, floats, negativos, cero y
valores sobre el máximo serán inválidos antes de consumir el generador.

El parser fallará antes de leer payload cuando un header válido declare un tamaño
fuera de presupuesto. Entries de tamaño cero también consumirán presupuesto de
cardinalidad. El estado residente quedará acotado por header, metadata y manifest
de entries, nunca por el contenido completo de archivos.

### 6. Captura Linux same-root y cierre temporal

`filesystem_oci_layout.py` añadirá
`capture_and_verify_laya_oci_tar_semantics(layer_evidence, layout_root)`. No se
sellará a partir de evidencia PR22 histórica sin recapturar bytes. El adaptador:

1. hará preflight completo antes de abrir;
2. abrirá la raíz y componentes descriptor-relative con las defensas existentes;
3. recapturará controles e inventario exactos;
4. rehashéará las doce blobs;
5. verificará DiffID+TAR de las diez layers por posición;
6. comparará fingerprints y paths después de cada lectura;
7. ejecutará el sweep final;
8. cerrará todos los FDs owned exactamente una vez;
9. sellará autoridad y evidencia sólo después del cierre exitoso.

Cualquier fallo de open/read/fstat/scandir/close, fingerprint, gzip, DiffID, TAR,
orden, cardinalidad o cap producirá cero evidencia. Se afirma estabilidad observada
por fingerprints y sweep, no snapshot filesystem absoluto ni mount read-only.

### 7. Claims, privacidad y compatibilidad

La evidencia heredará los claims verdaderos PR22 y añadirá únicamente
`tar_semantics_verified=true`. Permanecerán falsos `oci_rootfs_verified`,
`rootfs_materialized`, origen, licencia, base ancestry, checkpoint,
`runtime_materialized`, `executor_available` e `inference_executed`.

El summary canónico incluirá sólo schemas, flags y
`runtime_identity_sha256`. Omitirá raíz, paths, link targets, digests, DiffIDs,
sizes, counts, typeflags, PAX/GNU y payloads. `repr`, excepciones y traceback
tampoco filtrarán esos valores.

Los cinco roles (`dependency_lock`, `sbom`, `runtime_config`,
`checkpoint_manifest`, `oci_manifest`) y la runtime identity no cambiarán. Las
layers seguirán fuera de Git. Backend, scripts, runners y readiness no importarán
el nuevo módulo ni invocarán el adaptador.

### 8. TDD y gates

El trabajo se dividirá en RED/GREEN pequeños y auditables:

1. plan, tipos sellados, ancestry, API y aislamiento;
2. parser base para header/checksum/payload/padding/EOF;
3. PAX/GNU, paths, links, duplicados y bombas;
4. captura same-root, autoridad, cleanup y claims;
5. documentación y auditoría final.

Cada RED contendrá sólo tests/fixtures/configuración de test. Cada GREEN contendrá
sólo la implementación mínima correspondiente. Los tests RED permanecerán
byte-idénticos durante su GREEN, salvo corrección explícita mediante un nuevo ciclo
RED/GREEN.

El gate real será Linux, serial, opt-in, sobre copia disposable o mount read-only
del layout externo. No será presentado como CI obligatorio. También deberán pasar
suite Laya completa, regresiones multisitio/mock, Black, Ruff, diff-check y OpenSpec
strict.

## Risks / Trade-offs

- Un parser propio amplía superficie de seguridad; el perfil cerrado y la matriz
  adversarial reducen, pero no eliminan, ese riesgo.
- Rechazar duplicados efectivos es más estricto que TAR genérico; evita una
  semántica last-write-wins antes de la composición controlada de PR33.
- Aceptar targets absolutos o con `..` es deliberado porque PR32 los trata como
  metadata opaca; cualquier afirmación de seguridad de resolución queda bloqueada
  hasta PR33.
- Recapturar todas las blobs aumenta I/O, pero evita desligar la semántica TAR de
  los bytes same-root que la sustentan.
- Rechazar sparse/devices/FIFO puede descubrir incompatibilidad con la imagen real;
  cualquier ampliación requerirá un RED específico y no podrá hacerse por fallback.
