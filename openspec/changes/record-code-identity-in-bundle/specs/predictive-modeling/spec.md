## ADDED Requirements

### Requirement: linaje de codigo en el bundle operativo

El sistema SHALL registrar en `bundle.json` de toda ejecucion nueva la
identidad del codigo (commit y estado del arbol) capturada al entrenar, y
`load_operational_bundle` SHALL aceptar bundles sin esa clave exponiendo
"no registrado" (`None`) sin inferirla ni modificar ninguna identidad de
modelo, calibrador, contrato o ensamble.

#### Scenario: bundle nuevo registra el commit de entrenamiento

- **GIVEN** una ejecucion operativa nueva persistida en un repositorio git
- **WHEN** se carga el bundle de cualquier horizonte
- **THEN** `code_identity.commit` es el commit capturado al entrenar y coincide
  con `run_metadata.json`

#### Scenario: bundle anterior sin la clave

- **GIVEN** un `bundle.json` sin `code_identity`
- **WHEN** se carga
- **THEN** la carga tiene exito y `code_identity` es `None`, sin inferir un commit

#### Scenario: git no disponible

- **GIVEN** que git no puede ejecutarse al entrenar
- **WHEN** se persiste el bundle
- **THEN** `code_identity` es `{"available": false, "reason": ...}` sin `commit`
