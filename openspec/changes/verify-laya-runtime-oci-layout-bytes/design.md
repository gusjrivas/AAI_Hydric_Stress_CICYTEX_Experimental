# Diseño: captura atómica descriptor-relative del layout OCI

## Contexto y frontera de confianza

PR20 consume un `LayaRuntimeOciEvidence` PR19 exacto y factory-sealed. La imagen
completa es evidencia externa local: no se agrega a Git, no se descarga durante la
validación y no se incorpora como sexto rol del bundle. Los cinco roles fijados por
PR15/PR16 permanecen idénticos; el layout sólo cierra por bytes las referencias del
rol `oci_manifest`.

La implementación se divide en un core puro y un adaptador filesystem Linux. El core
prepara el grafo, verifica streams y sella valores; sólo el adaptador posee la
autoridad privada para afirmar captura same-root y producir evidencia final.

## Decisiones

### 1. Plan cerrado derivado de PR19

Los controles exactos son:

- `oci-layout`: 30 bytes, SHA-256
  `18f0797eab35a4597c1e9624aa4f15fd91f6254e5538c1e0d193b2a95dd4acc6`,
  `imageLayoutVersion=1.0.0`;
- `index.json`: 423 bytes, SHA-256
  `3d28b2fd93177f35031d802b830e2807253ea19838fb0386b14688a49dd75b39`,
  un único descriptor linux/amd64 hacia el manifest PR19.

El plan ordenado contiene doce blobs bajo `blobs/sha256/<digest>`:

| Rol | SHA-256 | Bytes |
| --- | --- | ---: |
| manifest | `7e46eb4f9e10b81e550b2587d1b12d50e0e9d746e346077e860e702ce169d9f0` | 3.166 |
| config | `bdd27ffe0d14dd637985f09bcdf461e58a64348829a4b3ad3cb7886ff56e20c5` | 10.261 |
| layer-00 | `bc0965b23a04fe7f2d9fb20f597008fcf89891de1c705ffc1c80483a1f098e4f` | 28.231.580 |
| layer-01 | `c58b365c3bcb57c930511e3fef962d15491ef2daba1e111fb5a6b41dbdecfc6b` | 3.317.301 |
| layer-02 | `3bc3f72291794502343f023ab10455e459897b13a73f38b6b56cf266dccb7ec5` | 16.202.769 |
| layer-03 | `42dacf6a4601de71542906f1be2bca5a78b8f430479b260a7097b9870498af69` | 251 |
| layer-04 | `418d9aeceb23d76e9191b40d18f9c73816dc849ef0e1111a42343b73c8ccc51c` | 21.573.096 |
| layer-05 | `ce65de5ef47521f33f7eb5bb76b05d5ff9c5a562e110b077449ff3af802803df` | 31.693.638 |
| layer-06 | `eb0f362469da4169812e6a645b36eca3678d6aaf06acb0297850b2c525692398` | 11.510 |
| layer-07 | `4f4fb700ef54461cfa02571ae0db9a0dc1e0cdb5577484a6d75e68dc38e8acc1` | 32 |
| layer-08 | `890fbe6d21f33111795ef040fe123b712444c40bc1f4e93a940a8baf9a93d339` | 511.506.914 |
| layer-09 | `f3d008f925e78af5c67f1e8b54aead83de30df814e105ff93e12f02c0d515c14` | 19.739 |

Son 14 archivos lógicos, 12 blobs, 612.570.257 bytes de blobs y 612.570.710
bytes totales. Los media types, orden, paths, cardinalidad, tamaños y digests son
exactos. Los dos controles son JSON estricto, canónico por bytes y acotado antes de
parsear; el index debe enlazar el mismo manifest ya capturado por PR19.

### 2. Verificación incremental sin autoridad global

Cada blob autorizado se consume como iterable inequívoco de chunks `bytes` exactos.
Cada chunk tiene cap de 1 MiB, existen como máximo 1.024 chunks y se corta en
size+1. Se rechazan chunks vacíos, tipo ambiguo, stream truncado/agregado/alterado,
digest desconocido, error del generador y contenido Git LFS pointer tanto LF como
CRLF.

Un receipt prueba sólo un blob y no puede elevar evidencia global. El cierre exige
la tupla exacta de doce receipts, en el orden e identidad del mismo plan, más la
autoridad privada de captura same-root.

### 3. Frontera Linux descriptor-relative

El adaptador requiere Linux con `O_DIRECTORY`, `O_NOFOLLOW`, `O_CLOEXEC`,
`O_NONBLOCK` y soporte `dir_fd`; Windows o una capacidad ausente fallan antes de
coaccionar/abrir la raíz. La raíz debe ser absoluta, no `/`, sintácticamente
canónica y tener como máximo 128 componentes. Se rechazan `.`/`..`, separadores
duplicados/finales, symlinks en la raíz o ancestros y paths no canónicos.

La raíz se abre componente por componente desde `/` y toda navegación posterior es
descriptor-relative. El inventario debe ser exactamente:

- raíz: `oci-layout`, `index.json`, `blobs`;
- `blobs`: sólo `sha256`;
- `blobs/sha256`: exactamente los doce nombres autorizados.

Controles y blobs deben ser archivos regulares con un único hard link; directorios
deben ser directorios reales. Los controles se leen con límite y `fstat` antes y
después. Los blobs se hashean por stream; cada path se reabre y compara tras leerlo.
Después de doce receipts, un sweep final reabre raíz/directorios/controles/blobs y
revalida fingerprints e inventario. Toda falla, incluida apertura, lectura,
`scandir`, `fstat`, close o mutación TOCTOU, cierra los file descriptors exactamente
una vez y prohíbe sellar evidencia.

El claim es atomicidad observada por descriptores y sweep dentro de esta captura; no
es una promesa de snapshot filesystem absoluto frente a adversarios fuera del
modelo comprobado.

### 4. Evidencia y flags

Los flags verdaderos son exactamente:

- `artifact_integrity_verified`;
- `oci_manifest_semantics_verified`;
- `oci_layout_controls_bytes_verified`;
- `oci_blob_inventory_verified`;
- `oci_same_root_capture_verified`;
- `oci_manifest_blob_bytes_verified`;
- `oci_config_blob_bytes_verified`;
- `oci_layer_blobs_bytes_verified`;
- `oci_bytes_verified`.

Los flags falsos son exactamente:

- `lock_verified`, `sbom_verified`, `lock_sbom_consistent`;
- `runtime_config_semantics_verified`,
  `checkpoint_manifest_semantics_verified`, `checkpoint_bytes_verified`;
- `oci_config_semantics_verified`, `oci_layer_diff_ids_verified`,
  `oci_rootfs_verified`;
- `origin_verified`, `license_verified`, `base_ancestry_verified`;
- `rootfs_materialized`, `runtime_materialized`, `executor_available`,
  `inference_executed`.

En particular, verificar los bytes de config/layers no interpreta config, history,
diffIDs, tar entries ni rootfs. Tampoco demuestra procedencia, autenticidad, firma,
licencia, ancestry, seguridad o ejecutabilidad.

### 5. Summary privado y aislamiento

Plan, receipts, autoridad y evidencia son frozen/slotted/factory-sealed. `repr`,
errores y summary no exponen raíz, paths, bytes, inventario, sizes ni digests
privados de controles/blobs. El summary canónico contiene schemas/profile,
`RuntimeIdentityRef` —incluido el commitment público `runtime_identity_sha256`— y
flags.

El adaptador es el único módulo autorizado a usar ambos sealers privados. Ningún
backend, runner, script o flujo de readiness lo invoca todavía; por tanto PR20 no
habilita un caller productivo.

### 6. Gate externo serial y custodia de la raíz

El operador SHOULD proveer en `LAYA_RUNTIME_OCI_LAYOUT_ROOT` el path absoluto y
canónico de la fuente externa y SHOULD custodiarla con permisos o mount read-only.
El gate trata esa fuente como input read-only: MUST NOT modificarla, calcula su
fingerprint antes/después y copia o reflinkea todo a una raíz temporal distinta.
PR20 demuestra preservación del fingerprint, pero no inspecciona ni acredita los
permisos/mount read-only de la fuente. La captura positiva y las pruebas adversariales
operan sólo sobre el clon descartable; es ese clon el que el adaptador valida como
raíz absoluta, no-root y sintácticamente canónica.

Comando de release gate sobre Linux, ejecutado serialmente y sin xdist:

```bash
LAYA_RUNTIME_OCI_LAYOUT_ROOT=/ruta/absoluta/canonica/read-only/layout \
python -m pytest -q tests/test_laya_runtime_oci_layout.py \
  tests/test_laya_runtime_oci_layout_filesystem.py
```

No se debe agregar `-n`, activar xdist ni compartir el clon entre workers. Con la
variable válida y todas las capacidades Linux disponibles, el único skip esperado
es el test específico que comprueba el fail-closed de Windows. Esta es una orden de
release manual/opt-in; PR20 no afirma que exista un job CI obligatorio equivalente.

La ejecución real de ese gate serial sobre Linux terminó con `217 passed, 1
skipped`; el skip único fue precisamente el test específico de Windows. Este
resultado registra la evidencia externa ejecutada, no una corrida de CI ni una
política CI mandatory.

### 7. TDD implementado

La cadena versionada fue:

1. RED `07ec0bc`, hardening `3a47351` y `b9ff9a9`, autorización successor
   `af6f8a1`; GREEN `6430435` para plan cerrado de controles/grafo.
2. RED `33ee5b7`, hardening `581498b` y `d5da30e`; GREEN `b8e2852` para receipts y
   hashing incremental acotado.
3. RED `8531c99`, hardening `2cbd5f2`, `bfdaac1`, `2738a7c` y `6e82ad9`; GREEN
   `36e862f` para captura same-root, sweep final, cleanup y evidencia conservadora.
4. RED `a521670`; GREEN `0d997de` para cap previo de 128 componentes de raíz.

## Consecuencias y rollback

La evidencia externa ahora puede afirmar integridad exacta del layout sin confundir
bytes con semántica u operación. Como no hay caller productivo ni estado persistido,
el rollback elimina core/adaptador/tests/change y deja intactos los cinco roles y
summaries PR15-PR19. La fuente externa no requiere cleanup porque el gate verifica
que no la modificó; los clones temporales son descartables. Esto no acredita sus
permisos ni un mount read-only.
