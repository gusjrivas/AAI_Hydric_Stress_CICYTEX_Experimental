## ADDED Requirements

### Requirement: Contrato versionado del dataset normalizado CICYTEX
La solución MUST declarar de forma inmutable la versión, las 21 identidades de
sonda, columnas requeridas, unidad, rango físico, patrón de archivo y política de
faltantes del dataset normalizado CICYTEX.

#### Scenario: Configuración inválida
- **WHEN** el contrato contiene nombres vacíos, sondas duplicadas, columnas de
  identidad ausentes, un patrón sin identidad o límites no finitos o invertidos
- **THEN** la configuración falla antes de leer datos o ejecutar un experimento.

#### Scenario: Evolución explícita
- **WHEN** cambie el esquema científico admitido
- **THEN** se declara una nueva versión del contrato sin modificar silenciosamente
  `cicytex-normalized-v1`.

### Requirement: Fuente CSV detrás de un puerto compatible
La fuente CSV MUST implementar `CicytexDatasetSource` y la fachada histórica MUST
seguir entregando un DataFrame observacionalmente idéntico.

#### Scenario: Carga válida
- **WHEN** existen las 21 series declaradas
- **THEN** se conservan exactamente columnas, columnas adicionales, tipos, valores,
  faltantes, orden por sonda/fecha e índice histórico.

#### Scenario: Validación histórica
- **WHEN** falta una serie, la identidad no coincide, hay una fecha duplicada o la
  humedad observada está fuera de rango
- **THEN** la carga falla con la misma categoría y mensaje de error vigentes.

#### Scenario: Consumidor existente
- **WHEN** un runner usa `load_normalized_cicytex()`
- **THEN** la fachada delega al adaptador CSV sin cambiar su firma ni exigir cambios
  en experimentos, ensemble causal, scripts, API o Laya.
