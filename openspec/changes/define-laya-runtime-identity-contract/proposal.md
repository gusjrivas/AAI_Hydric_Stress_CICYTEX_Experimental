# Change: Contrato declarativo de identidad del runtime Laya

Estado: implementado como foundation-only; define identidad canónica, pero no
verifica ni materializa artefactos y no ejecuta inferencia.

## Why

El contrato de evidencia LOSO acepta una referencia opaca de runtime. Antes de
construir un executor hace falta una identidad reproducible que fije qué versión de
Laya, entorno y conjunto de artefactos pretende usar una ejecución. Sin un manifest
cerrado, referencias móviles, layouts ambiguos o roles duplicados podrían producir
la misma etiqueta humana con suministros técnicamente distintos.

## What Changes

- Define `laya-runtime-manifest-v1` como JSON estricto, cerrado y cargado sólo desde
  bytes UTF-8 válidos; rechaza claves duplicadas, campos adicionales o ausentes y
  números no finitos.
- Fija el runtime declarado en `laya==0.4.2`, proveedor `laya-http`, Python
  `3.11.10`, `linux/amd64`, licencia `Apache-2.0` y una base OCI referenciada por
  digest no nulo.
- Fija como fuente canónica el release 0.4.2 del repositorio
  `NandhaKishorM/laya`, commit completo
  `68804629e8ccd9d616d48a40e87de9fabbeae069`.
- Exige exactamente una declaración para cada rol `dependency_lock`, `sbom`,
  `runtime_config`, `checkpoint_manifest` y `oci_manifest`, con formato, path POSIX
  relativo único, SHA-256 no nulo y tamaño positivo.
- Ordena los cinco roles canónicamente y deriva `identity_sha256` de la
  serialización JSON canónica; objetos y referencia son frozen/slotted.
- Unifica `RuntimeIdentityRef` con el contrato de ejecución de PR14 sin cambiar sus
  bytes públicos ni conectar runtime con ejecución.
- Mantiene falsos todos los estados de verificación, materialización, disponibilidad
  del executor e inferencia.

## Impact

El cambio es aditivo y queda aislado en `human_feedback.runtime_identity`. Describe
qué bytes deberían existir, pero no abre paths, no descarga repositorios o imágenes,
no compara digests contra archivos y no autentica origen. No modifica adapters,
backend, readiness, forecast, ingesta, entrenamiento, runners ni scripts; las
corridas de CICYTEX, Pergamino, Melchor Romero y laboratorio mock permanecen
inalteradas.

`convaiinnovations/laya` no es la fuente de este runtime. Cualquier checkpoint
publicado allí requiere una revisión futura independiente de licencia, procedencia,
compatibilidad y bytes antes de poder incorporarse como artefacto declarado.

## Deferred

Quedan expresamente fuera de este cambio:

- verificar bytes de lock, SBOM, configuración, checkpoint manifest u OCI manifest;
- comprobar consistencia lock/SBOM o integridad de checkpoint e imagen;
- materializar un filesystem, entorno Python, checkpoint o imagen OCI;
- autenticar origen, release, commit, licencia o supply chain;
- evaluar el checkpoint de `convaiinnovations/laya`;
- implementar executor HTTP, cargar modelo o ejecutar inferencia;
- integrar este manifest con readiness, evidencia científica, shadow o producción.
