## 1. TDD del lock uv

- [x] 1.1 Registrar RED `be61983` para perfil exacto, parser fail-closed, límites y privacidad.
- [x] 1.2 Añadir compatibilidad de parser de tests Python 3.10 en `99c60fb` sin relajar producción.
- [x] 1.3 Implementar GREEN `5f98930` para el perfil inicial de lock.
- [x] 1.4 Registrar RED `8d76ff5` para semántica completa, fuentes, hashes y aristas.
- [x] 1.5 Implementar GREEN `a303a76` ligando el lock completo al perfil exacto.

## 2. TDD del SBOM y consistencia

- [x] 2.1 Registrar RED `e1da051` para CycloneDX 1.6 cerrado, deterministicidad, schema y grafo.
- [x] 2.2 Implementar GREEN `1eb4657` para el perfil SBOM exacto.
- [x] 2.3 Registrar RED `7927125` para preservar identidades PURL/BOM-ref, incluido Torch `+cpu`.
- [x] 2.4 Implementar GREEN `4aca4c9` para identidad CycloneDX canónica.
- [x] 2.5 Registrar RED `756e80c` para inventario, fuentes, digest y 70 aristas consistentes.
- [x] 2.6 Implementar GREEN `512e783` para evidencia combinada lock↔SBOM.

## 3. Perfil auditado y claims

- [x] 3.1 Congelar generación uv 0.12.3, Python 3.11.10, Linux x86_64 CPU y cutoff.
- [x] 3.2 Fijar Laya commit unsigned, extra serve, Torch CPU y setuptools.
- [x] 3.3 Fijar tamaños/SHA-256 de lock y SBOM deterministas.
- [x] 3.4 Registrar cdxgen 13.3.0 y PASS externo CycloneDX CLI 0.33.1/schema 1.6.
- [x] 3.5 Verificar 45 identidades y 70 aristas activadas dentro del perfil.
- [x] 3.6 Limitar la excepción sin size al único wheel Torch URL/hash exacto, sin descarga.
- [x] 3.7 Mantener falsos todos los claims externos, de seguridad y operación.
- [x] 3.8 Completar auditoría independiente final del board y merge gate.

## 4. Reconciliación y próximos slices

- [x] 4.1 Resolver conceptualmente PR16 tasks 4.1/4.2 para lock/SBOM de este perfil.
- [x] 4.2 Resolver conceptualmente PR17 task 4.1 sin editar el change histórico.
- [ ] 4.3 Mantener pendiente PR17 task 4.2: semántica y referencias OCI.
- [ ] 4.4 Verificar firma/origen, licencias, CVE/seguridad y bytes de distribuciones.
- [ ] 4.5 Demostrar materialización/compatibilidad antes de diseñar executor.
