## Context

PR20 produjo evidencia sellada de una captura OCI exacta: controles, manifest,
config y diez layers coincidieron en size/SHA-256 desde una raíz común. El config
no está versionado en Git. PR21 recibe de forma explícita sus bytes y una evidencia
PR20, valida primero el binding criptográfico y sólo después interpreta el JSON.
La composición sigue fuera de los productos: no existe caller productivo.

## Goals / Non-Goals

### Goals

- Validar de forma pura, fail-closed y acotada el perfil config exacto observado.
- Preservar la cadena canónica de evidencia bundle→OCI metadata→layout PR20.
- Distinguir con precisión semántica declarada de evidencia externa.
- Emitir un summary público mínimo, determinista y sin payload privado.

### Non-Goals

- Recapturar paths, reutilizar un FD o afirmar vigencia actual del layout externo.
- Calcular DiffIDs, desempaquetar layers o verificar el rootfs.
- Probar origen, autenticidad, licencia, base ancestry o historia de construcción.
- Materializar runtime/checkpoint, habilitar executor o ejecutar inferencia.

## Decisions

### 1. Binding antes del parser

La entrada del payload es exclusivamente `bytes`. Antes de UTF-8/JSON se exige el
tamaño exacto 10.261 y SHA-256
`bdd27ffe0d14dd637985f09bcdf461e58a64348829a4b3ad3cb7886ff56e20c5`,
obtenidos del descriptor config único de PR20. El límite absoluto es 64 KiB.
Después, el parser rechaza UTF-8 inválido, JSON duplicado/no finito, tipos o campos
inesperados y excesos de profundidad, miembros, listas, strings o nodos.

Esta secuencia impide usar el parser como oráculo para bytes no autorizados. No
hay I/O: PR21 no vuelve a leer el path, no usa el mismo FD de PR20 y no afirma que
el archivo actual conserve esos bytes.

### 2. Perfil cerrado observado

La raíz exige exactamente `architecture`, `config`, `created`, `history`, `os` y
`rootfs`. Los valores son `amd64`, `linux` y `1970-01-01T00:00:00Z`. `config`
contiene exactamente `User`, `Env`, `Entrypoint`, `WorkingDir` y `Labels`; por ello
`Cmd` está ausente y cualquier aparición falla. Se exigen, en orden y con valores
exactos, 15 entradas Env; `Entrypoint=["laya-serve"]`;
`User="65532:65532"`; `WorkingDir="/opt/laya-runtime"`; y diez Labels exactos del
perfil fijado.

`rootfs` declara `type="layers"` y diez DiffIDs SHA-256 únicos, ordenados y
exactos. `history` contiene exactamente 21 objetos, diez no vacíos; cada entrada
usa los campos/tipos cerrados, `empty_layer` sólo puede ser `true`, y sus timestamps
UTC de segundo entero deben ser calendar-valid, incluidos límites de mes y bisiesto.

El vector Env exacto y ordenado es:

1. `PATH=/opt/laya-runtime/.venv/bin:/usr/local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin`
2. `LANG=C.UTF-8`
3. `GPG_KEY=A035C8C19219BA821ECEA86B64E628F8D684696D`
4. `PYTHON_VERSION=3.11.10`
5. `PYTHON_SHA256=07a4356e912900e61a15cb0949a06c4a05012e213ecd6b4e84d0f67aabbee372`
6. `UV_LINK_MODE=copy`
7. `UV_PYTHON_DOWNLOADS=never`
8. `UV_PROJECT_ENVIRONMENT=/opt/laya-runtime/.venv`
9. `LAYA_DEVICE=cpu`
10. `LAYA_PRELOAD=1`
11. `LAYA_MODELS=multilingual`
12. `LAYA_AUTO_TASK=0`
13. `LAYA_DEFAULT_MODEL=multilingual`
14. `LAYA_REVISION=55cf4c4ebb4ebe31b2550e8bdf3bd21b99753851`
15. `HF_HUB_OFFLINE=1`

Los Labels exactos son los cuatro commitments AAI
(`checkpoint-manifest=e54ad4cf767dd653c0703f3671e5317a5dca18c351bee2ab0b7943b5472900bf`,
`config=9a14323b31c463add7188331ce2c98bb3afbd491e15d06b1f98838a917454b5f`,
`sbom=f2fde1a342990e3b5b4d74d4930bf37f6d2229768b509a27f34edffc009a03b2`,
`uv-lock=e968771680b9c6e683163230ebd98b43541325ccb36d6959d1f9ed5565bd5526`)
bajo sus claves `org.aai-hydric.runtime.*.sha256`, más:

- `org.opencontainers.image.base.digest=sha256:840e180ebcc6e5c8efab209c43f5e40fd2af98cb49db5c7103c90539c56bb30e`
- `org.opencontainers.image.base.name=docker.io/library/python:3.11.10-slim-bookworm`
- `org.opencontainers.image.licenses=Apache-2.0`
- `org.opencontainers.image.revision=68804629e8ccd9d616d48a40e87de9fabbeae069`
- `org.opencontainers.image.source=https://github.com/NandhaKishorM/laya`
- `org.opencontainers.image.version=0.4.2`

Los diez DiffIDs declarados, en orden, son:
`c0f1022b22a9b36851b358f44e5475e39d166e71a8073cf53c894a299239b1c5`,
`bc9155b10ccec596b3283ceca7cc847bc4046db14eab7f77b9b170b5e825e0a5`,
`0266a6d27cd42ef4422dfb0b6dbd4186f3524600502559e13947f8d4de65c931`,
`cfc6e3b5400ce78d3df9c4826f39a78db0e7e9a01d2581b860b5611ac6829af6`,
`3b0ebae606bef07327bd2eb738a1fbb118531d66d718cb0e4308a2a8ef6ee147`,
`32da0000f413e50749de746d1b8c6178ba367bb9fb8b071578b06b9f029fefaa`,
`4db0c1957d9b2082f64699c9af2a21da88c9db1afe5f1eb702d268a6a3beecb7`,
`5f70bf18a086007016e948b04aed3b82103a36bea41755b6cddfaf10ace3c6ef`,
`23a2fba237de474cf363c925aedf483647f31f2f3510e2dced6e629a319961b4`
y `1805c5276e5a93fa136190900c0469b491e778b00748a739c78e2698427e0758`,
todos con prefijo `sha256:`.

Los valores exactos prueban conformidad con este perfil, no verdad externa. Labels
de source/revision/license/base son auto-declaraciones. History es una narrativa
auto-declarada, no evidencia independiente del proceso que creó la imagen.

### 3. Ancestry canónico por contenido

La evidencia PR20 se revalida profundamente y debe usar esquemas y tipos exactos
detectables, cinco artefactos con roles/paths únicos, un config descriptor único y
los flags PR20 esperados. A partir de sus cinco payloads se reconstruye un bundle
canónico mediante `verify_laya_runtime_artifact_bytes`; sobre él se reconstruye la
metadata OCI mediante `validate_laya_runtime_oci_metadata`, y se comprueba la
equivalencia completa con el grafo recibido antes de componer PR21.

Esto admite clones o wrappers content-equivalent, porque se canonizan mediante APIs
públicas y contenido verificable. No se acredita qué constructor creó el objeto ni
se usa identidad de objeto como provenance.

### 4. Claims conservadores

La nueva evidencia preserva los claims verdaderos PR20 de integridad, manifest,
controles, inventario, same-root y bytes exactos. El único claim nuevo verdadero es
`oci_config_semantics_verified`. Permanecen falsos
`oci_layer_diff_ids_verified`, `oci_rootfs_verified`, `origin_verified`,
`license_verified`, `base_ancestry_verified`, materialización, executor e
inferencia, además de cualquier claim no heredado sobre lock/SBOM/deployment.

PR21 no cambia los cinco roles (`dependency_lock`, `sbom`, `runtime_config`,
`checkpoint_manifest`, `oci_manifest`) ni incorpora un sexto artefacto. El blob
config sigue externo a Git.

### 5. API y privacidad

La superficie pública se limita a
`validate_laya_runtime_oci_config_semantics`,
`canonical_laya_runtime_oci_config_summary_bytes`, los tipos sellados
`ValidatedLayaRuntimeOciConfig` y `LayaRuntimeOciConfigEvidence`, y las constantes
de esquemas/caps allowlisted. El summary canónico expone sólo versiones de esquema,
flags y el commitment público `runtime_identity_sha256`. No expone bytes config,
Env, Labels, history, paths ni digests privados.

### 6. Evidencia de gate y frontera filesystem

La suite focal ordinaria dio `514 passed, 1 skipped`; el gate con evidencia real
Linux dio `152 passed`; la suite Laya completa dio `949 passed, 30 skipped`.
Black, Ruff y diff-check quedaron limpios. El gate real fue manual y opt-in; PR21
no crea ni declara CI obligatorio.

PR21 no interactúa con la raíz OCI. En particular no acredita permisos o mount
read-only absolutos. Sólo conserva la interpretación de PR20: su gate no modificó
la fuente y verificó preservación de fingerprint.

## TDD

1. Parser/perfil: RED `746ceab`, `35c28e5`, `cee1d22`; GREEN `8d5d32a`;
   calendario RED `243412f`, GREEN `8737f08`.
2. Evidencia digest-bound/sellado: RED/hardening `a422ca6`, `322b9ef`, `b9a0f29`,
   `2f603ea`, `0a7d858`, `d8f1349`; GREEN `344a227`.
3. Ancestry canónico: RED/hardening `a917fdb`, `178e158`, `fc317d3`, `9a1be32`,
   `0174f26`, `20570b6`; GREEN `8496b1e`.
4. Schema canónico previo: RED `4a009e8`; GREEN `ae3fbe4`.

## Risks / Trade-offs

- El perfil intencionalmente exacto rechazará cambios legítimos de imagen; todo
  cambio requiere un nuevo perfil y su cadena TDD/evidencia.
- El binding por digest evita ambigüedad del payload, pero no reemplaza una nueva
  captura si se necesita probar el estado presente del filesystem.
- Los DiffIDs declarados quedan disponibles para PR22, pero no deben consumirse
  como verificados hasta calcularlos desde las layers descomprimidas.
