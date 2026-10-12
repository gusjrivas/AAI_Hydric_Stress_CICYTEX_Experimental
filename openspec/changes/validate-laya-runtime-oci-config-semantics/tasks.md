## 1. TDD del parser y perfil

- [x] 1.1 Registrar RED `746ceab`, `35c28e5` y `cee1d22` para perfil cerrado, parser estricto, caps y pureza.
- [x] 1.2 Implementar GREEN `8d5d32a` para validar el config OCI exacto después del binding size/SHA.
- [x] 1.3 Registrar RED `243412f` y GREEN `8737f08` para timestamps UTC calendar-valid.

## 2. TDD de evidencia digest-bound

- [x] 2.1 Registrar RED/hardening `a422ca6`, `322b9ef`, `b9a0f29`, `2f603ea`, `0a7d858` y `d8f1349` para composición, sellado, revalidación profunda, summary y autorización successor.
- [x] 2.2 Implementar GREEN `344a227` para evidencia config ligada al descriptor exacto PR20.

## 3. TDD de ancestry canónico

- [x] 3.1 Registrar RED/hardening `a917fdb`, `178e158`, `fc317d3`, `9a1be32`, `0174f26` y `20570b6` para reconstrucción pública bundle→OCI metadata, tipos exactos y clones content-equivalent.
- [x] 3.2 Implementar GREEN `8496b1e` para reconstruir y comparar ancestry sellado sin afirmar provenance de constructor.
- [x] 3.3 Registrar RED `4a009e8` y GREEN `ae3fbe4` para ligar el esquema canónico previo exacto.

## 4. Gates y alcance

- [x] 4.1 Mantener cinco roles fijos, no versionar el blob config y no añadir caller productivo.
- [x] 4.2 Elevar sólo `oci_config_semantics_verified`; mantener falsos DiffIDs/rootfs/origin/license/ancestry/materialización/executor/inferencia.
- [x] 4.3 Ejecutar suite focal ordinaria: `514 passed, 1 skipped`.
- [x] 4.4 Ejecutar gate manual real Linux: `152 passed`; no presentarlo como CI obligatorio.
- [x] 4.5 Ejecutar suite Laya completa `949 passed, 30 skipped`, Black, Ruff y diff-check limpios.
- [x] 4.6 Documentar que PR21 no recaptura ni toca la raíz y no eleva la no modificación/fingerprint de PR20 a enforcement de permisos/mount read-only.
- [x] 4.7 Completar auditoría independiente final y merge gate: GO, cero P0-P2; Windows focal `514 passed, 1 skipped`, Windows Laya `887 passed, 92 skipped`, Linux real `152 passed`, Linux Laya `949 passed, 30 skipped`; OpenSpec strict, quality gates y árbol limpios; fuente externa preservada.

## 5. Próximo slice

- [ ] 5.1 PR22 calculará por streaming los diez DiffIDs desde las layers descomprimidas y validará `rootfs.diff_ids`.
- [ ] 5.2 Posponer origen/firma/licencia/ancestry, materialización, caller productivo, executor e inferencia hasta contar con evidencia independiente.
