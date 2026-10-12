## ADDED Requirements

### Requirement: Plan LOSO exhaustivo y seguro por grupo

El sistema MUST construir exactamente un fold por cada sitio requerido del corpus,
MUST usar el sitio retenido completo como test y MUST asignar exhaustivamente los
otros registros a ajuste o calibración sin dividir ningún grupo.

#### Scenario: Tres folds cross-site

- **GIVEN** un corpus válido que cubre `cicytex`, `melchor-romero` y `pergamino`
- **WHEN** se construye el plan LOSO
- **THEN** existen exactamente tres folds en el orden contractual de sitios
- **AND** cada fold usa exclusivamente su sitio retenido como test
- **AND** ambos sitios restantes contribuyen registros a ajuste y calibración.

#### Scenario: Particiones exhaustivas, disjuntas y group-safe

- **GIVEN** un fold construido desde el corpus sellado
- **WHEN** se inspeccionan sus particiones
- **THEN** la unión de ajuste, calibración y test contiene exactamente todos los ejemplos del corpus
- **AND** ninguna pareja de particiones comparte ejemplos
- **AND** cada `group_id` aparece en una sola partición del fold.

#### Scenario: Estado inválido construido directamente

- **GIVEN** un fold o plan con particiones vacías, superpuestas, incompletas, con un grupo dividido o con un sitio incorrecto
- **WHEN** se construye o reemplaza el objeto
- **THEN** la validación falla de forma cerrada.

### Requirement: Cohorte de calibración determinista y label-blind

El sistema MUST aplicar `laya-loso-group-calibration-sha256-v1`, MUST reservar para
calibración `ceil(20% de los grupos)` de cada sitio de entrenamiento y MUST determinar
esa selección sin RNG, seed, comentarios, anotaciones, adjudicaciones ni gold labels.

#### Scenario: Asignación por hash versionado

- **GIVEN** grupos de un sitio y la política versionada
- **WHEN** se ordenan por SHA-256 de política, sitio y `group_id`
- **THEN** los primeros `ceil(20%)` grupos forman la cohorte de calibración
- **AND** todos sus ejemplos permanecen juntos.

#### Scenario: Misma cohorte cuando el sitio entrena

- **GIVEN** un sitio que participa como entrenamiento en dos folds distintos
- **WHEN** se comparan sus grupos de calibración
- **THEN** la cohorte de ese sitio es idéntica en ambos folds.

#### Scenario: Orden y labels no alteran la asignación

- **GIVEN** dos representaciones equivalentes con distinto orden de registros/anotaciones o distinto payload humano y gold labels, pero iguales sitios, grupos y ejemplos
- **WHEN** se construyen sus planes
- **THEN** las asignaciones de ajuste, calibración y test son iguales
- **AND** sus commitments internos de asignación son iguales.

#### Scenario: Menos de dos grupos en un sitio

- **GIVEN** cualquier sitio con menos de dos grupos
- **WHEN** se intenta construir el plan
- **THEN** la construcción falla de forma cerrada
- **AND** el error no expone IDs ni payload privados.

### Requirement: Identidades congeladas antes de asignar

El protocolo MUST congelar `corpus_id`, `group_id` y la identidad del muestreo antes
de construir o inspeccionar el plan, porque la política label-blind no impide que
quien controle los nombres influya en el ranking hash.

#### Scenario: Renombrado posterior de un grupo

- **GIVEN** un corpus y grupos previamente congelados
- **WHEN** cambia un `group_id` después de conocer la política o la asignación
- **THEN** el corpus previo no puede reutilizarse como la misma evidencia
- **AND** se exige una nueva identidad de corpus y un nuevo plan
- **AND** la validez estructural no se interpreta como prueba de muestreo aleatorio.

### Requirement: Commitment privado y summary público seguro

El plan MUST ligar internamente sus asignaciones mediante un SHA-256 canónico, MUST
excluir ese commitment y los registros de su representación, y MUST publicar un
summary determinista sin IDs de ejemplo/grupo ni payload humano.

#### Scenario: Commitment detecta una reasignación

- **GIVEN** dos planes cuya asignación de grupos difiere
- **WHEN** se calculan sus commitments internos
- **THEN** los digests son distintos
- **AND** un objeto cuyo commitment no coincide con sus particiones es rechazado.

#### Scenario: Summary público sin superficie de diccionario

- **GIVEN** un plan con IDs y contenido humano privados
- **WHEN** se serializa su summary público o su `repr`
- **THEN** no contiene `assignment_sha256`, `example_id`, `group_id`, comentarios, anotadores, adjudicaciones ni gold labels
- **AND** contiene `corpus_id`, `evaluation_corpus_digest`, conteos por partición y flags fail-closed.

### Requirement: Validez exclusivamente estructural

El plan MUST declarar únicamente validez estructural y MUST mantener en falso
ejecución de evaluación, ajuste de calibración, suficiencia científica, elegibilidad
para shadow review y autorización productiva.

#### Scenario: Plan estructural válido

- **GIVEN** un corpus que satisface todos los requisitos de particionado
- **WHEN** se construye el plan
- **THEN** `structurally_valid` es verdadero
- **AND** `evaluation_executed` es falso
- **AND** `calibration_fitted` es falso
- **AND** `scientifically_sufficient` es falso
- **AND** `eligible_for_shadow_review` es falso
- **AND** `production_enablement_authorized` es falso.

#### Scenario: Sin afirmación de suficiencia

- **GIVEN** un plan estructuralmente válido
- **WHEN** todavía no se ejecutaron runner, calibrador, métricas, baseline pareado e intervalos bootstrap
- **THEN** el plan no acredita N, balance, random sampling, representatividad ni suficiencia científica
- **AND** no habilita readiness, shadow review, runtime ni producción.

### Requirement: Aislamiento de flujos existentes

El plan LOSO MUST NOT ser importado ni invocado por adapters, backend, gate offline,
forecast, ingesta, predictive modeling, experiment runners o scripts.

#### Scenario: Corridas existentes sin plan configurado

- **GIVEN** ningún plan LOSO conectado a runtime
- **WHEN** se ejecutan el gate offline y las corridas de CICYTEX, Pergamino, Melchor Romero y laboratorio mock
- **THEN** conservan sus contratos previos
- **AND** el constructor del plan no se invoca.
