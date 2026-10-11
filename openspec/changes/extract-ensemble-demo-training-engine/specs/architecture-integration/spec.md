## ADDED Requirements

### Requirement: Motor de entrenamiento ensemble neutral por sitio
El sistema MUST ofrecer un motor común que reciba configuración científica
inmutable y dependencias explícitas para resolver el umbral y ajustar cada
familia. El motor MUST desconocer módulos, fuentes de datos, CLI, API y
manifiestos de ejecución específicos de un sitio.

#### Scenario: Ejecución de un horizonte
- **WHEN** una fachada entrega un frame válido, un plan y un horizonte soportado
- **THEN** el motor prepara las mismas features y particiones, ajusta las familias
  en el orden declarado y devuelve paths y conteos suficientes para el manifiesto.

#### Scenario: Fallo de una familia
- **WHEN** el ajustador inyectado falla durante un horizonte
- **THEN** el motor propaga el error y la fachada conserva el progreso confirmado
  de horizontes anteriores sin declarar la corrida completa.

### Requirement: Compatibilidad observable de la fachada Pergamino
`run_demo_from_frame` MUST conservar su firma, retorno, cortes, threshold,
features, identidades, paths, formatos y semántica de error existentes.

#### Scenario: Refactor compatible
- **WHEN** se ejecutan los fixtures previos y posteriores con iguales entradas
- **THEN** el árbol de artefactos y los contratos científicos son equivalentes y
  los bundles continúan cargando e infiriendo por la API operacional v2.

#### Scenario: Otros recorridos científicos
- **WHEN** se integra la extracción limitada a Pergamino
- **THEN** Melchor Romero, CICYTEX, Laboratorio y Laya siguen ejecutando sus
  recorridos sin cambios funcionales ni de configuración.
