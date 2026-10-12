# Change: Validación semántica del config OCI de Laya

Estado: implementado como validador puro y digest-bound posterior a PR20; no
recaptura filesystem, no materializa ni ejecuta el runtime.

## Why

PR20 probó por bytes el config OCI exacto dentro de una captura same-root, pero
dejó explícitamente falsa su conformidad semántica. PR21 interpreta únicamente ese
payload ya ligado por size/SHA-256 y exige el perfil observado cerrado de Laya,
sin convertir declaraciones internas del config en evidencia de origen, licencia,
ancestry o corrección del rootfs.

## What Changes

- Añade un parser JSON estricto, acotado y puro para el config OCI exacto; valida
  tipo `bytes`, tamaño y SHA-256 antes de decodificar o parsear.
- Exige el perfil cerrado observado: `amd64`/`linux`, epoch UTC, ausencia de
  `Cmd`, 15 entradas `Env`, 10 `Labels`, `Entrypoint=["laya-serve"]`,
  `User="65532:65532"`, workdir, diez DiffIDs declarados y 21 entradas de
  history, diez de ellas no vacías y todas con timestamps UTC calendar-valid.
- Reconstruye canónicamente, mediante las APIs públicas existentes, la cadena
  bundle→manifest OCI→layout antes de aceptar la evidencia PR20. Acepta clones
  content-equivalent sólo cuando conservan la clase exacta y normaliza únicamente
  wrappers carrier `CapturedRuntimeArtifact` con spec, contenido y bindings
  canónicos exactos. Rechaza wrappers, proxies y subclasses de prior, snapshot,
  manifest, spec, proyección OCI, layout o plan; no se afirma procedencia de
  constructores Python.
- Eleva exclusivamente `oci_config_semantics_verified=true`, además de preservar
  los claims por bytes de PR20. DiffIDs calculados, rootfs, origen, licencia,
  ancestry, materialización, executor e inferencia permanecen falsos.
- Mantiene los cinco roles de artefactos, no versiona el blob config y no añade
  caller productivo.
- Publica una API mínima para validación y summary canónico. El summary sólo
  expone esquemas, flags y `runtime_identity_sha256`; bytes, Env, Labels, history,
  paths y digests privados no salen de la evidencia.

## Impact

`oci_config_semantics_verified=true` significa que los bytes suministrados
coincidieron exactamente con el descriptor config probado por PR20 y cumplieron
el perfil sintáctico-semántico cerrado de PR21. No significa que los diez DiffIDs
declarados coincidan con las layers descomprimidas, que el rootfs resultante sea
correcto ni que Labels/history auto-declarados prueben origen, licencia, base o
proceso de construcción.

El validador no abre paths, no recaptura desde el mismo FD ni acredita el estado
actual del layout externo. PR20 conserva la autoridad de su captura pasada. PR21
no toca la raíz: tampoco amplía el claim de PR20 a enforcement de permisos o mount
read-only; allí sólo se acreditó no modificación y preservación de fingerprint en
el gate manual.

Las suites registradas fueron: focal ordinaria `514 passed, 1 skipped`, gate real
Linux `152 passed` y suite Laya completa `949 passed, 30 skipped`, con Black, Ruff
y diff-check limpios. El gate real es manual/opt-in y no se declara job obligatorio
de CI.

## Deferred

- PR22 calculará DiffIDs por streaming de las diez layers y validará el vínculo
  con `rootfs.diff_ids`;
- verificar rootfs materializado, origen, firma, licencia o ancestry independiente;
- verificar checkpoint bytes o compatibilidad modelo-runtime;
- materializar runtime, habilitar executor o ejecutar inferencia;
- integrar esta evidencia en un caller productivo o readiness.
