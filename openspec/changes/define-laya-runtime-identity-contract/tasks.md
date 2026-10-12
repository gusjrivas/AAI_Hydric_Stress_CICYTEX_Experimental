## 1. Contrato TDD

- [x] 1.1 Registrar tests RED para parser bytes-only, schema exacto y JSON fail-closed.
- [x] 1.2 Registrar tests RED para fuente/runtime fijados y cinco roles de artefactos.
- [x] 1.3 Registrar tests RED para canonicalización, identidad, inmutabilidad y flags.
- [x] 1.4 Implementar GREEN mínimo preservando el summary golden y aislamiento de PR14.
- [x] 1.5 Registrar RED1d para rechazar otro commit del repo canónico y un path POSIX válido asignado al rol incorrecto.
- [x] 1.6 Implementar GREEN1d (`4e74d02f`) fijando source completo y mapping exacto rol-formato-path.
- [x] 1.7 Cerrar la revisión del gatekeeper tras revalidar contrato focal, regresión, aislamiento y OpenSpec estricto.

## 2. Identidad foundation-only

- [x] 2.1 Fijar Laya 0.4.2 y `NandhaKishorM/laya@68804629e8ccd9d616d48a40e87de9fabbeae069`.
- [x] 2.2 Exigir metadata exacta de proveedor, licencia, Python, plataforma e imagen base declarada.
- [x] 2.3 Exigir una declaración canónica para cada rol de lock, SBOM, config, checkpoint y OCI.
- [x] 2.4 Rechazar formatos, digests, tamaños y paths ambiguos o duplicados.
- [x] 2.5 Derivar la identidad SHA-256 de bytes canónicos, independiente del layout JSON.
- [x] 2.6 Compartir `RuntimeIdentityRef` con el contrato de ejecución PR14.

## 3. Límites e aislamiento

- [x] 3.1 Mantener en falso verificación de artefactos, lock, SBOM, checkpoint y OCI.
- [x] 3.2 Mantener en falso consistencia lock/SBOM, materialización, origen, executor e inferencia.
- [x] 3.3 No leer filesystem, descargar artefactos, consultar repositorios ni ejecutar red/modelo.
- [x] 3.4 Separar `convaiinnovations/laya` como posible checkpoint sujeto a revisión futura, no como source.
- [x] 3.5 Mantener el módulo aislado de readiness y flujos científicos u operacionales.

## 4. Próximos slices TDD

- [ ] 4.1 Verificar bytes y tamaños de lock, SBOM, config y manifests desde una raíz explícita.
- [ ] 4.2 Validar consistencia entre lock y SBOM y verificar supply chain/origen.
- [ ] 4.3 Revisar licencia, procedencia y compatibilidad del checkpoint de `convaiinnovations/laya`.
- [ ] 4.4 Materializar de forma reproducible entorno, checkpoint e imagen OCI.
- [ ] 4.5 Implementar executor HTTP y ejecutar inferencia gold-blind.
- [ ] 4.6 Integrar evidencia científica, readiness y shadow review sólo tras sus gates independientes.
