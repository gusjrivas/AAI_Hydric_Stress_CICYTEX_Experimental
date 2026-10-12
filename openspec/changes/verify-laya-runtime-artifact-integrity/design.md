# Diseño: bundle portable y captura segura descriptor-relative

## Contexto y límite de confianza

PR15 estableció una identidad declarativa. PR16 verifica que un conjunto concreto de
bytes coincide con esa declaración. La solución se divide en una frontera pura,
portable y testeable, y un adapter de filesystem deliberadamente limitado a Linux.
Ninguna de las dos interpreta el contenido ni acredita procedencia o ejecución.

## Decisiones

### 1. Verificador puro all-or-nothing

`verify_laya_runtime_artifact_bytes` recibe un `LayaRuntimeManifest` y un diccionario
path→bytes sin realizar I/O. La cobertura debe coincidir exactamente con los cinco
paths del manifest: no se aceptan faltantes, adicionales, valores textuales, buffers
ni booleanos. Cada payload debe tener el `size_bytes` exacto y el SHA-256 declarado.

La verificación es all-or-nothing: ante un solo error no se construye ningún
`LayaRuntimeBundleSnapshot` parcial. El snapshot canónico contiene exactamente los
cinco `CapturedRuntimeArtifact` en el orden del manifest y se liga a
`runtime_identity_ref(manifest)`. Manifest, artefactos y snapshot son frozen/slotted;
los factories usan un token privado para impedir autoafirmar verificación por
construcción directa.

### 2. Punteros Git LFS y bytes exactos

Un archivo que comienza con `version https://git-lfs.github.com/spec/v1` es un
puntero, no el artefacto. Se rechaza tanto con líneas LF como CRLF. El digest se
calcula sobre bytes exactos: no se normalizan line endings ni se decodifica texto,
porque LF y CRLF son contenidos distintos y sólo uno puede coincidir con el manifest.

### 3. Adapter Linux descriptor-relative

El adapter acepta una raíz absoluta y canónica. Abre `/` y recorre cada componente
de la raíz con `dir_fd`, `O_DIRECTORY`, `O_NOFOLLOW` y `O_CLOEXEC`; luego recorre
cada path del manifest de la misma forma. El archivo final usa además `O_NONBLOCK`
para evitar bloqueo en targets especiales.

Se rechazan symlinks en ancestros de la raíz, raíz, directorios intermedios o archivo
final. El target debe ser regular y tener el tamaño declarado antes de leer. No se
usan resolución textual, `Path.resolve`, `read_bytes` ni aperturas pathname-based
para artefactos.

Windows y cualquier host sin flags/`dir_fd` requeridos fallan antes del primer open
mediante `SecureRuntimeCaptureUnavailableError`. No existe fallback menos seguro.

### 4. Límites de lectura y recursos

La suma declarada del bundle no puede exceder 256 MiB y se valida antes de abrir la
raíz. Cada archivo se lee como máximo hasta `size_bytes + 1`; el byte adicional sólo
sirve para detectar crecimiento. Truncamiento, crecimiento o lectura incompleta
invalidan la captura antes de llamar al verificador portable.

Cada descriptor abierto tiene ownership explícito y se intenta cerrar exactamente
una vez. Los caminos de éxito, error, excepción y fallo inyectado de `close` barren
los descriptors restantes; un fallo de cleanup vuelve fallida la operación y nunca
produce un snapshot.

### 5. Defensa TOCTOU observacional

Para cada archivo se compara el fingerprint de `fstat` antes y después de leer:
device, inode, mode, link count, size, mtime y ctime. Esto detecta mutaciones in-place
observables durante la captura.

Además se registra un fingerprint descriptor-relative de cada cadena de directorios
y archivo. Después de capturar los cinco payloads se vuelve a recorrer todo el
bundle; cualquier cambio de path, inode o metadata invalida la operación antes de
entregar bytes al verificador puro. Así, el claim es que los paths/inodes coinciden en
ese sweep final y los bytes entregados coinciden con tamaño/SHA del manifest.

No se afirma atomicidad absoluta del filesystem. Una mutación y restauración no
observable entre mediciones, o un cambio posterior al sweep, está fuera de la
garantía. Un snapshot fuerte requiere una primitive del storage o materialización
inmutable futura.

### 6. Privacidad y summary público

Los bytes capturados están marcados `repr=False`. Errores del verificador y del
adapter son genéricos: no incluyen root absoluto, payloads ni contenido privado. El
summary canónico publica sólo schema, `RuntimeIdentityRef`, cantidad de artefactos y
flags; nunca paths, bytes ni digests individuales de artefactos.

### 7. Claims fail-closed

`artifact_integrity_verified=true` significa solamente que los cinco bytes del
snapshot coinciden por tamaño y SHA-256 con un único manifest. Permanecen falsos:

- `lock_verified`, `sbom_verified` y `lock_sbom_consistent`;
- `runtime_config_semantics_verified`;
- `checkpoint_manifest_semantics_verified`;
- `oci_manifest_semantics_verified`;
- `runtime_materialized` y `origin_verified`;
- `executor_available` e `inference_executed`.

No se parsean formatos, no se siguen referencias internas, no se inspeccionan
dependencias y no se autentica supply chain.

### 8. TDD, aislamiento y ausencia de caller productivo

La implementación siguió ciclos separados:

1. RED `053ec08` / GREEN `fef60a7`: integridad portable all-or-nothing.
2. RED `0e23c8e` / GREEN `589beef`: punteros LFS efectivos LF/CRLF.
3. RED `fdf8c8a` / GREEN `32f7065`: captura Linux descriptor-relative y fail-closed.
4. RED `bc5261c` / GREEN `a66ab8a`: bounded reads, TOCTOU, sweep final y cleanup.

El verificador puro no importa filesystem ni adapters. El adapter depende sólo de
stdlib y de los contratos de identidad/bundle. Backend, readiness, runners y scripts
no lo invocan; PR16 no tiene caller productivo.

## Consecuencias

- La identidad declarada puede ligarse a bytes concretos sin interpretar su contenido.
- La captura Linux elimina fallbacks inseguros y detecta las carreras cubiertas por
  sus fingerprints, sin prometer una transacción filesystem.
- Los fallos no filtran root ni contenido privado y no generan evidencia parcial.
- PR17 debe agregar semántica mediante nuevos RED antes de elevar cualquier flag.
