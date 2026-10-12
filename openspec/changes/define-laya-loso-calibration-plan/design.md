# Diseño: particionado LOSO privado, determinista y group-safe

## Contexto y límite de confianza

El corpus humano candidato contiene identificadores y payload privados. Este slice
sólo transforma un corpus ya sellado en un plan estructural verificable. No entrena,
no calibra, no predice y no observa métricas. En consecuencia, la validez del plan
no es evidencia de desempeño ni habilita shadow review o producción.

## Decisiones

### 1. Tres folds LOSO exhaustivos

El orden de folds sigue el orden contractual de sitios del corpus: `cicytex`,
`melchor-romero` y `pergamino`. Cada fold usa todos los registros del sitio retenido
como test. Los registros de los otros dos sitios se asignan exhaustivamente a
`fit` o `calibration`; las tres particiones son no vacías y disjuntas.

Un `group_id` es indivisible dentro de cada fold. Ningún grupo puede cruzar ajuste,
calibración o test y el sitio retenido no puede aparecer en las particiones de
entrenamiento.

### 2. Política de calibración hash, versionada y label-blind

La política `laya-loso-group-calibration-sha256-v1` calcula para cada sitio una clave
SHA-256 con separación de dominio a partir de `policy_id`, `site_id` y `group_id`.
Ordena los grupos por esa clave, con `group_id` como desempate, y reserva los
primeros `ceil(0.20 * grupos_del_sitio)` para calibración. No existe RNG, seed ni
dependencia de comentario, anotación, adjudicación o gold label.

La cohorte se calcula una vez por sitio desde el corpus completo. Por ello, cuando
un sitio actúa como entrenamiento, contribuye siempre los mismos grupos a
calibración sin importar cuál de los otros sitios sea el test del fold.

Esta determinación no equivale a random sampling. Además, ser label-blind no la hace
resistente a identificadores elegidos adversarialmente: quien pueda cambiar nombres
de grupos puede buscar posiciones favorables en el ranking. La precondición del
protocolo es congelar corpus, grupos y sus identidades antes de construir, publicar
o inspeccionar la asignación. Un cambio posterior exige una nueva identidad del
corpus y un nuevo plan; no se permite renombrar para mejorar la partición.

### 3. Cardinalidad mínima, no suficiencia

Cada sitio debe contener al menos dos grupos. El constructor falla de forma cerrada
si no puede dejar al menos un grupo del sitio en calibración y otro en ajuste. Esta
regla sólo hace viable la estructura: no fija N científico, balance de clases,
balance entre sitios, poder estadístico ni representatividad.

### 4. Commitment privado de asignación

El plan calcula `assignment_sha256` sobre un payload canónico interno que enumera,
por fold y partición, las tuplas privadas de sitio, grupo y ejemplo. El campo está
marcado `repr=False` y permite detectar cualquier cambio de asignación al validar el
objeto.

El commitment no se publica. Dado que el universo de IDs puede ser pequeño o
predecible, exponer su digest permitiría ataques de diccionario o confirmación de
pertenencia. También permanecen fuera del summary los `example_id`, `group_id`,
comentarios, anotadores, adjudicaciones, gold labels y el resto del payload privado.

### 5. Summary público y fail-closed

El JSON público es canónico y determinista. Incluye `corpus_id`,
`evaluation_corpus_digest`, identidad del protocolo de muestreo, schema y política,
el sitio retenido y conteos de registros/grupos por partición. Publica los flags:

- `structurally_valid=true`;
- `evaluation_executed=false`;
- `calibration_fitted=false`;
- `scientifically_sufficient=false`;
- `eligible_for_shadow_review=false`;
- `production_enablement_authorized=false`.

No existe en este slice una transición que vuelva verdaderos los cinco últimos
estados. La reconstrucción directa o por reemplazo vuelve a validar schema,
exhaustividad, política, aislamiento de grupos y commitment.

### 6. Aislamiento arquitectónico

El plan no es importado por adapters, backend, gate offline, forecast, ingesta,
predictive modeling, experiment runners ni scripts. Un cambio posterior debe
incorporar runner, tuning, calibrador, métricas, baseline, bootstrap y runtime con su
propio TDD antes de conectar este contrato con readiness.

## Consecuencias

- La estructura cross-site es reproducible sin filtrar el corpus privado.
- La selección de calibración no puede adaptarse a las etiquetas observadas.
- Congelar los identificadores antes de asignar es parte indispensable del
  protocolo, no una propiedad que el hash pueda probar por sí solo.
- Un plan válido sigue siendo insuficiente para cualquier afirmación científica u
  operacional.
