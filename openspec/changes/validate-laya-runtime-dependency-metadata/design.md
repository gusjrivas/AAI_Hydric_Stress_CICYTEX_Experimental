# Diseño: perfil local exacto de uv.lock y CycloneDX SBOM

## Contexto y frontera de confianza

La entrada es un `LayaRuntimeBundleSnapshot` PR16 cuyos blobs coinciden con el
manifest por tamaño/SHA-256. PR18 interpreta únicamente `dependency_lock` y `sbom` y
los compara entre sí. Los parsers son puros: no resuelven paquetes, no acceden a
índices, no descargan artefactos y no ejecutan installers.

Los tres flags positivos describen conformidad con un corpus cerrado conocido, no
soporte general del formato ni evidencia de una instalación real.

## Decisiones

### 1. Generación auditable y congelada

El lock fue generado con uv 0.12.3 bajo este perfil:

- CPython exactamente 3.11.10;
- marker CPython/Linux/x86_64 y objetivo CPU;
- `exclude-newer = 2026-10-10T09:19:05Z`;
- Laya desde `NandhaKishorM/laya` commit
  `68804629e8ccd9d616d48a40e87de9fabbeae069`, commit sin firma;
- extra `serve` activado;
- Torch `2.14.0+cpu` desde el índice CPU de PyTorch;
- build constraint `setuptools==84.0.0`.

El fixture `uv.lock` tiene exactamente 37.599 bytes y SHA-256
`e968771680b9c6e683163230ebd98b43541325ccb36d6959d1f9ed5565bd5526`.
La identidad semántica canónica evita depender del orden de colecciones TOML, pero
el combinador exige además los bytes/digest exactos del artefacto capturado.

El commit unsigned no se presenta como autenticado. Fijarlo evita movilidad; no
demuestra autoría ni procedencia.

### 2. Perfil lock cerrado, no parser uv genérico

El parser bytes-only valida UTF-8/TOML, límites de payload, paquetes,
distribuciones, strings y URLs, y rechaza valores ambiguos o no canónicos. Exige el
inventario completo de 45 identidades, fuentes exactas, hashes de distribuciones y
las relaciones activadas por el perfil `serve`.

Esto no promete aceptar cualquier lock válido producido por uv. Un cambio legítimo
de versión, orden semántico, índice o grafo requiere otro perfil y nueva revisión.

### 3. Excepción Torch sin tamaño, cerrada por identidad

El único artefacto al que se permite omitir `size` es:

- URL
  `https://download-r2.pytorch.org/whl/cpu/torch-2.14.0%2Bcpu-cp311-cp311-manylinux_2_28_x86_64.whl`;
- SHA-256
  `673dbf5c9bbadfffab7a386b6dd7a0c219f1408a328b7b4e86d0ae551cdafa42`;
- package `torch`, kind `wheel`, versión `2.14.0+cpu`.

La excepción no se aplica a otra URL, paquete, sdist o hash. Es metadata tolerada,
no un permiso de descarga: PR18 nunca descarga ese wheel ni impone un cap de
descarga porque no existe descarga alguna.

### 4. SBOM determinista y validación de schema

El SBOM fue generado determinísticamente con cdxgen 13.3.0 en lifecycle `pre-build`.
Tiene 65.198 bytes y SHA-256
`f2fde1a342990e3b5b4d74d4930bf37f6d2229768b509a27f34edffc009a03b2`.

El documento declara:

- `bomFormat=CycloneDX`, `specVersion=1.6` y version 1;
- `$schema=https://cyclonedx.org/schema/bom-1.6.schema.json`;
- tool cdxgen 13.3.0;
- propiedad `aai:uv-lock:sha256` igual al digest del lock;
- propiedad de generación uv 0.12.3;
- 45 identidades normalizadas y 70 aristas activadas.

Además del parser local cerrado, el mismo fixture obtuvo PASS con CycloneDX CLI
oficial 0.33.1 contra schema 1.6. Este PASS cubre conformidad del documento con ese
schema; no audita la veracidad del inventario, sus licencias o su seguridad.

### 5. Identidades PURL y grafo exacto

Las identidades se forman por nombre, versión, source kind y source URL. PURL y
`bom-ref` deben ser exactos; en Torch se preserva deliberadamente la diferencia
entre `+cpu` en `bom-ref` y `%2Bcpu` en PURL. Ninguna arista puede referenciar una
identidad ausente.

La consistencia lock↔SBOM compara:

1. digest del lock contra la propiedad SBOM;
2. inventario completo de 45 identidades/fuentes;
3. conjunto exacto de 70 aristas activadas, incluyendo extra `serve`.

No compara bytes instalados, resolución en otra plataforma ni el grafo de un perfil
diferente.

### 6. Combinador y flags

El combinador extrae ambos blobs exclusivamente de un snapshot íntegro y conserva su
`RuntimeIdentityRef`. Los objetos son frozen/slotted/factory-sealed y no exponen
URLs, digests, paquetes o payloads en `repr`, errores o summary público.

Los flags significan:

- `lock_verified=true`: lock exacto conforme al perfil uv local;
- `sbom_verified=true`: SBOM exacto conforme al perfil local cerrado y validado
  externamente contra CycloneDX schema 1.6;
- `lock_sbom_consistent=true`: inventario/fuentes/aristas y digest son exactamente
  coherentes dentro de este perfil.

Permanecen falsos `runtime_config_semantics_verified`,
`checkpoint_manifest_semantics_verified`, `checkpoint_bytes_verified`, todos los
flags OCI, `origin_verified`, `runtime_materialized`, `executor_available` e
`inference_executed`. PR18 no compone automáticamente evidencia PR17 en un objeto
que eleve más flags.

### 7. Claims que el perfil no puede soportar

La evidencia no demuestra:

- compatibilidad genérica con uv/CycloneDX;
- instalación o build reproducible bit a bit;
- origen, autenticidad o firma del commit/artefactos;
- licencias, vulnerabilidades/CVE, malware o seguridad;
- bytes de wheels/sdists seleccionados;
- checkpoint u OCI;
- materialización, disponibilidad de executor o inferencia.

### 8. TDD y auditoría

La cadena versionada fue:

1. RED `be61983`, compatibilidad test Python 3.10 `99c60fb`, GREEN `5f98930` para el
   perfil inicial de lock.
2. RED `8d76ff5`, GREEN `a303a76` para semántica completa del lock.
3. RED `e1da051`, GREEN `1eb4657` para el perfil CycloneDX.
4. RED `7927125`, GREEN `4aca4c9` para identidad PURL/BOM-ref.
5. RED `756e80c`, GREEN `512e783` para evidencia y consistencia lock↔SBOM.

El GO TDD+arquitectura permite documentar el slice; la auditoría final independiente
del board/merge gate permanece pendiente y se registra como tal.

## Consecuencias

- El perfil de dependencias puede reproducirse y auditarse con inputs precisos.
- Lock y SBOM están ligados sin ampliar la garantía a artefactos no descargados.
- Las tareas lock/SBOM pendientes de PR16/PR17 quedan resueltas conceptualmente para
  este perfil, mientras OCI y toda operación continúan bloqueados.
