## ADDED Requirements

### Requirement: Protocolo de entrenamiento temporal compartido CICYTEX
La solución MUST mantener features, familias autorizadas, cortes temporales y
selección de particiones en un módulo puro compartido por los runners CICYTEX.

#### Scenario: Features por horizonte y sonda
- **WHEN** se construyen features para los horizontes 1, 2 o 3
- **THEN** lags, medias móviles y targets se calculan de forma independiente por
  sonda sin modificar el DataFrame recibido.

#### Scenario: Cuatro particiones temporales
- **WHEN** existen al menos 60 fechas únicas
- **THEN** los límites corresponden a 50% entrenamiento, 15% calibración, 15%
  validación y 20% evaluación, sin solapamientos ni filas omitidas.

#### Scenario: Historia insuficiente
- **WHEN** existen menos de 60 fechas únicas
- **THEN** el protocolo falla antes del ajuste con el error histórico compatible.

### Requirement: Runners desacoplados y compatibilidad pública
El ensemble causal MUST depender del protocolo compartido y MUST NOT importar el
runner experimental; el runner experimental MUST conservar sus símbolos públicos
históricos como referencias a las mismas implementaciones compartidas.

#### Scenario: Consumidor histórico
- **WHEN** un consumidor importa constantes, DTO o helpers desde `experiment.py`
- **THEN** recibe los mismos objetos del protocolo sin modificar su código.

#### Scenario: Evolución de un runner
- **WHEN** cambia la orquestación de uno de los runners
- **THEN** el otro no queda acoplado a su módulo, efectos laterales ni dependencias.
