# Design: convergencia pura de autoridades supply

## Frontera y entradas

`verify_laya_runtime_supply_convergence` recibe exactamente tres predecessors:

1. `LayaRuntimeOciLayerDiffIdsEvidence` de PR22;
2. `LayaRuntimeProvenanceEvidence` de PR35;
3. `LayaRuntimeBaseAncestryEvidence` de PR36.

Cada valor debe ser exact-class, issued por su módulo y profundamente válido. El
combinador invoca exactamente
`canonical_laya_runtime_oci_layer_diff_ids_summary_bytes`,
`canonical_laya_runtime_provenance_summary_bytes` y
`canonical_laya_runtime_base_ancestry_summary_bytes`; no duplica sus sellos ni
acepta wrappers, clones, proxies o formas equivalentes.
`base_ancestry_evidence.layer_evidence` debe ser el mismo objeto PR22 recibido.
PR35 es una autoridad issued independiente: no necesita identidad Python compartida
con PR22/PR36 si su snapshot reconstruido converge profundamente.

## Convergencia de snapshots

La ruta PR22 exacta es
`layer_evidence.layout_evidence.plan.oci_evidence.snapshot`. La ruta PR35 exacta es
`provenance_evidence.checkpoint_evidence.deployment_evidence.snapshot`. La relación
PR36 exacta es `base_ancestry_evidence.layer_evidence`.

Para cada snapshot se deriva un mapping cerrado `path -> content` y se llama al
mismo constructor público
`verify_laya_runtime_artifact_bytes(snapshot.manifest, payload_by_path)`.

Los snapshots reconstruidos deben ser profundamente equivalentes en manifest,
cinco specs, cinco contenidos exactos, bindings y `RuntimeIdentityRef`. La igualdad
se compara por contenido canónico y no presta tokens de fábrica. Un digest interno
recalculado o una copia superficial no reemplaza la reconstrucción pública.

La equivalencia demuestra convergencia de contenido. No demuestra que PR22 y PR35
fueran capturados al mismo tiempo, desde la misma raíz filesystem, host, checkout o
sesión. Tampoco demuestra procedencia externa; esas afirmaciones permanecen fuera.

## Autoridad, registro y concurrencia

La evidencia final es frozen/slotted, exact-class y creada sólo por el combinador.
Un registro privado module-side protegido por lock conserva la autoridad por
identidad y una firma semántica profunda. Clones, mutaciones de ancestors,
mix-and-match y evidencia no registrada fallan en creación y summary.

La implementación actual usa referencias débiles y comprobaciones identity-safe
para liberar autoridad expirada sin alterar evidencia viva. Es una decisión interna,
no un contrato de representación: no se fijan nombre o tipo del registro, campos,
layout de callbacks, estrategia de cleanup ni reutilización de identificadores.
El contrato observable es que evidencia y predecessors expirados no retienen sus
grafos, que cleanup no revoca ni altera evidencia viva y que clones, aliases o
objetos unissued no adquieren autoridad.

El anti-mix por identidad se aplica exclusivamente a PR36→PR22. Una evidencia PR35
issued de otra captura es válida si los cinco artefactos, manifest, bindings y
runtime identity reconstruidos son profundamente equivalentes. Se rechaza sólo si
esa convergencia de contenido falla.

No existe un flag global one-shot ni una sesión global consumible. Llamadas válidas
independientes pueden ejecutarse concurrentemente; cada resultado tiene su propio
registro. El lock protege sólo la transición del registro y nunca se mantiene al
invocar validadores de predecessors o código que pueda pertenecer al caller. Los
summaries repetidos o concurrentes de evidencia viva producen bytes deterministas.

## Claims

El único claim nuevo verdadero es
`runtime_supply_content_convergence_verified=true`. Los once claims PR22 verdaderos
son, exactamente:

- `artifact_integrity_verified`, `oci_manifest_semantics_verified`;
- `oci_layout_controls_bytes_verified`, `oci_blob_inventory_verified`;
- `oci_same_root_capture_verified`, `oci_manifest_blob_bytes_verified`;
- `oci_config_blob_bytes_verified`, `oci_layer_blobs_bytes_verified`;
- `oci_bytes_verified`, `oci_config_semantics_verified`;
- `oci_layer_diff_ids_verified`.

PR36 añade `base_ancestry_verified`. PR35 añade, además del artifact claim común,
`runtime_config_semantics_verified`, `checkpoint_manifest_semantics_verified`,
`checkpoint_bytes_verified`, `provenance_objects_verified`,
`source_git_content_verified`, `checkpoint_git_content_verified`,
`source_license_declaration_observed` y
`checkpoint_license_declaration_observed`. Todos conservan su significado original.

Permanecen falsos `lock_verified`, `sbom_verified`, `lock_sbom_consistent`,
`oci_rootfs_verified`, `tar_semantics_verified`, `origin_verified`,
`license_verified`, `runtime_build_recipe_verified`, `build_process_attested`,
`reproducible_build_verified`, `rootfs_materialized`, `runtime_materialized`,
`executor_available` e `inference_executed`.

El combinador comprueba cardinalidades existentes, sin crear caps nuevos: tres
predecessors; cinco artefactos por snapshot; cinco archivos checkpoint; diez layers
PR22; dieciséis objetos PR35; y prefijos PR36 de cuatro compressed layers y cuatro
DiffIDs. Los límites de parsing/streaming siguen perteneciendo a los predecessors.

## Privacidad y superficie pública

La superficie pública contiene exactamente dos operaciones y un tipo de evidencia:

- `verify_laya_runtime_supply_convergence`;
- `canonical_laya_runtime_supply_convergence_summary_bytes`;
- `LayaRuntimeSupplyConvergenceEvidence`.

El summary público mínimo tiene exactamente estas keys no booleanas:

- `schema_version`, `layer_evidence_schema_version`;
- `provenance_evidence_schema_version`, `base_ancestry_evidence_schema_version`;
- `runtime_identity_schema_version`, `runtime_identity_sha256`.

Su matriz booleana contiene exactamente los 21 claims verdaderos enumerados arriba
(incluido el nuevo claim) y los 14 claims falsos enumerados arriba. No incluye otro
commitment, digest ni agregado.

Omitirá bytes, paths, manifests, digests de artefactos/Git/OCI, sizes, receipts,
tuples de layers, timestamps, roots y detalles de captura. `repr` y errores aplican
la misma privacidad y no incluyen valores desconocidos.

## Aislamiento

El módulo depende sólo de módulos puros PR22/PR35/PR36 y `runtime_bundle`. No abre
archivos, no crea fixtures, no usa adapters, no ejecuta subprocess/red y no tiene
callers productivos. Los flujos científicos y operativos existentes no lo importan.

## TDD y CI

GREEN queda bloqueado hasta completar cuatro RED:

- RED A: API, exact types, issuance y relación PR36→PR22;
- RED B: reconstrucción pública y equivalencia profunda de snapshots;
- RED C: anti-mix, clones, mutaciones, registro, lock y concurrencia;
- RED D: claims, privacidad, aislamiento y ausencia de autoridad co-temporal.

Después del GREEN mínimo se añadirá un job CI focal Linux/Windows. Ese job requiere
que los contratos PR36 base ancestry y PR35 provenance ya estén disponibles; usa
evidencia sintética emitida, no captura externa ni fixtures nuevos.

El positivo RED/GREEN no puede monkeypatchear los tres validadores canónicos. Tampoco
puede usar un helper PR22 legado sin snapshot real. Debe emitir ancestry legítima
con `layer_evidence.layout_evidence.plan.oci_evidence.snapshot` reconstruible y
mantener las funciones canónicas originales durante toda la prueba positiva.
