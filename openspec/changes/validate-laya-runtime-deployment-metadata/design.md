# Diseño: conformidad local de metadata sin claims externos

## Contexto y frontera epistemológica

La entrada es un `LayaRuntimeBundleSnapshot` de PR16: sus cinco blobs coinciden con
el manifest por tamaño/SHA-256. PR17 interpreta únicamente los blobs capturados con
roles `runtime_config` y `checkpoint_manifest`. No recibe sustitutos del caller y no
consulta estado externo.

Los flags `runtime_config_semantics_verified` y
`checkpoint_manifest_semantics_verified` significan sólo conformidad
sintáctico-semántica con el perfil local exacto descrito aquí, más coherencia de
enlaces internos. No prueban verdad, licencia, procedencia/origen, autenticidad,
compatibilidad de ejecución, bytes referenciados, seguridad ni operabilidad.

## Decisiones

### 1. Parser bytes-only, cerrado y acotado

Ambos parsers reciben exclusivamente bytes UTF-8. Rechazan JSON inválido, top-level
no-object, claves duplicadas, constantes no finitas, recursión excesiva y campos
faltantes/adicionales, también en objetos anidados.

El runtime config se rechaza si supera 16 KiB y el checkpoint manifest si supera 64
KiB; el límite se comprueba antes de decodificar o parsear. Después del parseo del
checkpoint, el array `files` debe tener cardinalidad exactamente cinco antes de
invocar el parser de elementos. Estas cotas reducen superficie de recursos, pero no
son un análisis de complejidad general del JSON.

### 2. Perfil local exacto del runtime config

`laya-runtime-config-v1` fija:

- entrypoint `laya-serve`;
- proveedor, engine, source, Python y plataforma idénticos al manifest PR15;
- modelo declarado `convaiinnovations/laya`, revisión
  `55cf4c4ebb4ebe31b2550e8bdf3bd21b99753851`, subfolder/name `multilingual`;
- ambiente exacto CPU/offline, sin extensiones, secretos ni URLs adicionales;
- SHA-256 no nulo del blob `checkpoint_manifest` esperado.

La coincidencia es una regla del perfil local, no una prueba de que el entrypoint
exista, que el ambiente sea suficiente o que el modelo pueda cargarse.

### 3. Perfil local exacto del checkpoint manifest

`laya-checkpoint-manifest-v1` repite repository, revisión y subfolder declarados y
contiene exactamente cinco roles canónicos: configuración del encoder, weights,
config de Laya, tokenizer y tokenizer config. Para cada rol se fija path, SHA-256 y
tamaño positivo del perfil. El orden de entrada se normaliza al orden contractual.

Estos son metadatos sobre archivos externos. PR17 no posee ni abre esos cinco
archivos; por eso `checkpoint_bytes_verified=false`, aun cuando el blob JSON del
checkpoint manifest sí pertenezca al bundle íntegro de PR16.

### 4. Combinador desde un único snapshot

`validate_laya_runtime_deployment_metadata` extrae ambos blobs únicamente del
snapshot sellado. Verifica:

1. provider/engine/source/Python/platform del config contra el manifest del bundle;
2. repository/revision/subfolder del config contra el checkpoint manifest;
3. `checkpoint_manifest_sha256` del config contra los bytes capturados de ese mismo
   checkpoint manifest;
4. `RuntimeIdentityRef` de la evidencia contra el snapshot.

La evidencia es factory-sealed, frozen/slotted y no puede reconstruirse para elevar
flags o sustituir config/checkpoint/snapshot.

### 5. Reconciliación con PR15

PR15 fija `NandhaKishorM/laya` como source del engine. PR17 no redefine esa fuente.
`convaiinnovations/laya` aparece solamente como identidad declarada del checkpoint
en metadata no operativa. Admitir esa string y revisión demuestra sólo coincidencia
con el perfil local.

La revisión independiente de licencia, procedencia/origen, autenticidad,
compatibilidad con el engine y bytes reales sigue pendiente. Esa deuda bloquea
descarga, uso, materialización, executor e inferencia; no puede cerrarse mediante
flags dentro de este parser.

### 6. Flags con significado acotado

La evidencia combinada puede declarar verdaderos únicamente:

- `artifact_integrity_verified`: heredado del snapshot PR16;
- `runtime_config_semantics_verified`: config conforme al perfil local;
- `checkpoint_manifest_semantics_verified`: checkpoint manifest conforme al perfil
  local y enlaces internos coherentes.

Permanecen falsos:

- `lock_verified`, `sbom_verified`, `lock_sbom_consistent`;
- `checkpoint_bytes_verified`;
- `oci_bytes_verified`, `oci_manifest_semantics_verified`;
- `origin_verified`, `runtime_materialized`;
- `executor_available`, `inference_executed`.

En particular, “semantics” no significa licencia válida, origen verificado,
autenticidad, compatibilidad de ejecución ni validación de bytes referenciados.

### 7. Privacidad, pureza y aislamiento

Config, checkpoint, file specs y evidencia usan `repr` opaco. Errores no incluyen
secretos ni valores desconocidos. El summary público contiene sólo schema, runtime
identity y flags; excluye repository/revision/subfolder, environment, paths, digests
de checkpoint y blobs capturados.

El módulo depende sólo de stdlib, `runtime_identity` y `runtime_bundle`. No usa I/O,
red, procesos, Docker o adapters, y ningún flujo operativo lo importa.

### 8. TDD y próximos gates

RED `a7bebfc` fijó schemas, perfil y enlaces; RED `995c706` cerró privacidad antes de
GREEN `9435c42`, que implementó el validador puro. RED `8a79720` añadió límites de
16/64 KiB, recursión fail-closed y cardinalidad cinco previa al parseo; GREEN
`17a19d9` implementó esas cotas sin ampliar claims.

El próximo slice debe abordar lock/SBOM/OCI y, por separado, la revisión externa del
checkpoint. Ninguno debe reutilizar los flags semánticos locales como sustituto de
evidencia externa.

## Consecuencias

- Metadata ambigua o incoherente se rechaza antes de cualquier operación.
- El perfil es reproducible y privacy-safe, pero sigue siendo declarativo.
- La identidad de checkpoint no obtiene estatus de origen confiable por ser aceptada.
- Materialización e inferencia permanecen explícitamente bloqueadas.
