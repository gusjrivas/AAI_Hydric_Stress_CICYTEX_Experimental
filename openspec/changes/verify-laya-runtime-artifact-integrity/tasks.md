## 1. Contrato portable TDD

- [x] 1.1 Registrar RED `053ec08` para cobertura exacta, bytes, tamaño/SHA, privacidad, inmutabilidad y flags.
- [x] 1.2 Implementar GREEN `fef60a7` como verificador puro all-or-nothing de cinco artefactos.
- [x] 1.3 Registrar RED `0e23c8e` para punteros Git LFS efectivos con LF y CRLF.
- [x] 1.4 Implementar GREEN `589beef` rechazando variantes LFS sin normalizar contenido.

## 2. Frontera filesystem TDD

- [x] 2.1 Registrar RED `fdf8c8a` para captura descriptor-relative Linux, symlinks, no regulares, límites y capabilities.
- [x] 2.2 Implementar GREEN `32f7065` con `dir_fd`, `O_NOFOLLOW`, `O_NONBLOCK` y fallback fail-closed.
- [x] 2.3 Registrar RED `bc5261c` para mutaciones TOCTOU, sweep final y fallos de cleanup.
- [x] 2.4 Implementar GREEN `a66ab8a` con fstat antes/después, fingerprints finales y ownership de fds.

## 3. Claims y aislamiento

- [x] 3.1 Producir snapshot sólo cuando coinciden los cinco payloads de un único manifest.
- [x] 3.2 Mantener bytes fuera de `repr`, summary y errores; no filtrar root ni contenido.
- [x] 3.3 Mantener falsos todos los flags semánticos, origen, materialización, executor e inferencia.
- [x] 3.4 Documentar que el sweep final no equivale a atomicidad filesystem absoluta.
- [x] 3.5 Fallar en Windows/capabilities insuficientes sin abrir archivos ni degradar seguridad.
- [x] 3.6 Mantener runtime bundle sin caller productivo y aislado de readiness/operación.
- [x] 3.7 Registrar RED3 `4445eb3` para impedir filtración de paths/digests y rechazar roots no canónicas antes de abrir.
- [x] 3.8 Implementar GREEN3 `c0fc709` cerrando las brechas de privacidad y canonicalidad sin ampliar claims.
- [ ] 3.9 Cerrar la reauditoría independiente del gatekeeper sobre GREEN3 y su regresión completa.

## 4. PR17: semántica y supply

- [ ] 4.1 Parsear lock y SBOM con schemas cerrados y límites propios.
- [ ] 4.2 Verificar consistencia lock/SBOM y referencias a la versión exacta de Laya.
- [ ] 4.3 Validar semántica del runtime config sin ejecutar código.
- [ ] 4.4 Validar manifests de checkpoint y OCI y sus referencias cruzadas.
- [ ] 4.5 Incorporar verificación de origen/procedencia en un gate independiente.
- [ ] 4.6 Evaluar materialización y executor sólo después de cerrar semántica y supply.
