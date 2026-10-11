## ADDED Requirements

### Requirement: Snapshot content-addressed de normalizados CICYTEX
La fuente CSV MUST identificar los bytes exactos de las 21 series que materializa
y MUST construir un manifiesto determinista en el orden del contrato.

#### Scenario: Captura válida
- **WHEN** existen las 21 series declaradas y permanecen estables durante la lectura
- **THEN** cada entrada registra sonda, nombre relativo, tamaño y SHA-256 de los
  mismos bytes entregados al parser.

#### Scenario: Identidad agregada reproducible
- **WHEN** dos directorios contienen los mismos bytes contractuales
- **THEN** producen el mismo hash agregado sin depender de ruta absoluta, mtime,
  orden de enumeración ni archivos inesperados.

#### Scenario: Cambio concurrente
- **WHEN** un archivo cambia, se reemplaza o desaparece durante la captura
- **THEN** la fuente falla cerrada antes de devolver un snapshot parcial.

#### Scenario: Compatibilidad DataFrame
- **WHEN** un consumidor existente llama `load()` o `load_normalized_cicytex()`
- **THEN** recibe el mismo DataFrame, validaciones y semántica que antes.

### Requirement: Procedencia explícita sin reinterpretación histórica
Los runners CICYTEX MUST poder persistir un sidecar que separe snapshot
normalizado, CSV primario y ZIP de distribución.

#### Scenario: Runner enriquecido
- **WHEN** un script oficial ejecuta un runner con procedencia v2
- **THEN** el sidecar registra las tres identidades, calidad descriptiva y estado
  `external_derivative_unverified` sin incluir rutas absolutas.

#### Scenario: Alias legado
- **WHEN** se persiste procedencia junto a `dataset_sha256` y `zip_sha256`
- **THEN** el runner valida que identifican respectivamente el CSV primario y el
  ZIP, conservando el significado de corridas anteriores.

#### Scenario: Consumidor legado
- **WHEN** un consumidor llama un runner sin procedencia
- **THEN** la firma y los artefactos previos siguen funcionando sin sidecar nuevo.
