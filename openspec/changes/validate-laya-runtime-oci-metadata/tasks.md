## 1. TDD del manifest OCI exacto

- [x] 1.1 Registrar RED `f592412` para fixture raw, schema/media types, descriptors, annotations, límites y privacidad.
- [x] 1.2 Registrar hardening RED `0ea8770` contra claves extra/duplicadas, no finitos, mutaciones de orden/cardinalidad y construcción directa.
- [x] 1.3 Implementar GREEN `2023afe` con parser puro, acotado, canónico y factory-sealed.
- [x] 1.4 Fijar checkout byte-stable LF en `815e22d` y corregir el fixture exacto en `b836951`.

## 2. TDD de evidencia agregada

- [x] 2.1 Registrar RED `b3ea9dd` para snapshot exacto, raw manifest, cross-links y summary privado.
- [x] 2.2 Registrar hardening RED `8638594` contra mutación de evidencia, descriptors, identidad y flags.
- [x] 2.3 Registrar RED `77c5ba8` y `45f31a5` para aislamiento de módulos productivos sin bypasses por alias/atributos.
- [x] 2.4 Implementar GREEN `fbc4dce` ligando el manifest raw y sus annotations al mismo snapshot.

## 3. Perfil y claims auditables

- [x] 3.1 Fijar fixture en 3.166 bytes y SHA-256 `7e46eb4f9e10b81e550b2587d1b12d50e0e9d746e346077e860e702ce169d9f0`.
- [x] 3.2 Registrar Laya 0.4.2/commit unsigned, Python base y uv 0.12.3 por digest, y Debian snapshot `20261010T000000Z`.
- [x] 3.3 Registrar generación repetida con digest de manifest idéntico y validación de layout durante generación con umoci 0.6.0 pinneado.
- [x] 3.4 Elevar sólo integridad del snapshot y semántica local del manifest; mantener falsos todos los claims no demostrados.
- [x] 3.5 Mantener summary/repr/errores privados y módulo sin caller productivo.
- [ ] 3.6 Completar auditoría independiente final del board y merge gate.

## 4. Próximo slice

- [ ] 4.1 PR20: capturar y verificar por bytes `oci-layout`, `index.json`, config y todas las layers.
- [ ] 4.2 PR20: comprobar cobertura cerrada, digest/size y enlaces entre index, manifest, config y layers antes de elevar `oci_bytes_verified`.
- [ ] 4.3 Verificar procedencia/firma/licencia/ancestry por evidencia independiente; no derivarlas de annotations.
- [ ] 4.4 Verificar checkpoint bytes y compatibilidad antes de materialización, executor o inferencia.
