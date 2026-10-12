## 1. TDD de metadata local

- [x] 1.1 Registrar RED `a7bebfc` para schemas cerrados, perfil exacto, enlaces, flags y aislamiento.
- [x] 1.2 Registrar RED `995c706` para privacidad de metadata, errores, `repr` y summary.
- [x] 1.3 Implementar GREEN `9435c42` como validador puro desde el snapshot PR16.
- [x] 1.4 Registrar RED `8a79720` para caps 16/64 KiB, recursión fail-closed y cardinalidad cinco previa.
- [x] 1.5 Implementar GREEN `17a19d9` para los límites de parsing de RED `8a79720` sin ampliar claims.
- [ ] 1.6 Completar auditoría independiente y regresión del GREEN de límites.

## 2. Conformidad y enlaces internos

- [x] 2.1 Fijar el perfil local exacto de runtime config, ambiente offline y modelo declarado.
- [x] 2.2 Fijar cinco roles exactos de archivos declarados por checkpoint manifest.
- [x] 2.3 Enlazar identidad runtime config↔manifest del bundle.
- [x] 2.4 Enlazar modelo config↔checkpoint y digest config↔blob capturado del manifest.
- [x] 2.5 Construir evidencia factory-sealed/frozen/slotted sólo desde un snapshot íntegro.

## 3. Límites de claims

- [x] 3.1 Definir flags semánticos como conformidad con perfil local, no evidencia externa.
- [x] 3.2 Mantener falsos lock/SBOM, checkpoint bytes, OCI, origen, materialización, executor e inferencia.
- [x] 3.3 Admitir `convaiinnovations/laya` sólo como identidad declarada no operativa.
- [x] 3.4 Mantener pendientes licencia, procedencia, autenticidad, compatibilidad y bytes del checkpoint.
- [x] 3.5 Mantener metadata privada fuera de `repr`, summary y errores.
- [x] 3.6 Mantener el módulo puro, aislado y sin caller operativo.

## 4. Próximos slices

- [ ] 4.1 Validar schemas y consistencia de lock/SBOM mediante TDD separado.
- [ ] 4.2 Validar semántica OCI y referencias cruzadas sin materializar.
- [ ] 4.3 Auditar licencia, procedencia/origen y autenticidad del checkpoint.
- [ ] 4.4 Verificar bytes reales del checkpoint contra sus declaraciones.
- [ ] 4.5 Ejecutar pruebas explícitas de compatibilidad antes de materializar.
- [ ] 4.6 Diseñar executor/inferencia sólo tras cerrar todos los gates anteriores.
