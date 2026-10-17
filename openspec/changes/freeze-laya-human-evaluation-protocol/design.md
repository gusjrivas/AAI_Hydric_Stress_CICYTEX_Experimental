# Diseño: preregistro humano congelado

## Frontera de confianza

`evaluation_preregistration` recibe bytes del manifest y artefactos ya leídos por
el caller. No descubre rutas, no toca red ni importa el gate offline. Verifica
integridad reproducible; no demuestra que la recolección, revisión ética o
custodia declaradas hayan ocurrido en el mundo real.

## Manifest cerrado y binding

El schema `laya-human-evaluation-preregistration-v1` rechaza campos faltantes,
adicionales o duplicados, números no finitos y coerciones booleano/número. Liga
`corpus_id`, `evaluation_corpus_sha256`, `loso_plan_sha256` y el
`loso_assignment_sha256` exacto con los objetos ya validados. `required_sites`
conserva el orden canónico CICYTEX, Melchor Romero y Pergamino.

## Artefactos externos

Se requieren exactamente los roles `sampling_protocol`, `annotation_guide`,
`adjudication_protocol`, `deidentification_protocol`, `custody_record` y
`baseline_protocol`. Cada entrada fija `artifact_id`, `size_bytes` y SHA-256. El
verificador recalcula
tamaño y digest sobre los bytes; además contrasta los digests e identificadores
que ya declaran el corpus o el análisis. El baseline queda ligado por
`baseline_protocol_id` y `baseline_protocol_sha256`, no sólo por un nombre lógico.
No se serializa el contenido en repr, errores o summary.

## Cohorte preregistrada

Antes de cualquier resultado se fijan `minimum_total_examples`,
`minimum_examples_per_site`, `minimum_groups_per_site`,
`minimum_examples_per_site_category`, `maximum_site_imbalance_ratio` y
`minimum_pre_adjudication_alpha_nominal`. El acuerdo es alpha de Krippendorff
nominal sobre las anotaciones originales, antes de adjudicar. Los incumplimientos
fallan cerrados y nunca se corrigen relajando el manifest.

El módulo valida los valores que recibe: no elige N, no realiza un cálculo de
potencia y no convierte los valores sintéticos de tests en tamaños aprobados para
el estudio. Sin manifest, corpus privado y artefactos externos provistos por la
autoridad del estudio, el estado científico real permanece
`BLOCKED_CORPUS_NOT_PROVIDED`.

## Análisis congelado

La métrica primaria es macro-F1 calculada sobre las cinco etiquetas canónicas, con
zero-division igual a cero. El estimando primario es la media de igual peso entre
sitios del delta macro-F1 Laya menos baseline; el estimando por sitio es ese delta
dentro de cada sitio. Se fijan superioridad global mínima 0,05 y no inferioridad
por sitio mínima -0,02. El bootstrap es percentil bilateral estratificado por
sitio cuya unidad de remuestreo es el grupo dentro del sitio, con 10.000 réplicas
pareadas por los mismos grupos/sitio, 95 % y semilla declarada. Los intervalos
percentiles bilaterales son descriptivos y no son el gate. Para cada hipótesis
`h`, con margen preregistrado `margin_h`, la probabilidad de cola es
`p_h = (1 + count(delta_h_bootstrap <= margin_h)) / (B + 1)`.

Holm/0,05 opera sobre una familia cerrada: global, CICYTEX, Melchor Romero y
Pergamino. Ordena por `(p_h, índice preregistrado)`, compara el rango `r` contra
`alpha / (m - r + 1)` y se detiene en el primer no rechazo. El PASS estadístico
exige rechazar las cuatro hipótesis; ningún intervalo descriptivo puede sustituir
esa regla. También se copian
sin reinterpretar los diez umbrales de `laya-readiness-policy-v1`; quedan como
criterios preregistrados, no como autoridad de readiness.

## Privacidad y estado

El summary puede publicar metadata, digests, restricciones y conteos agregados,
pero nunca comentarios, IDs de ejemplos/grupos/personas, decisiones privadas,
anotaciones ni gold labels por ejemplo. Un protocolo aceptado sólo acredita
estructura, binding e integridad de bytes. Mantiene `evaluation_executed`,
`scientifically_sufficient`, `eligible_for_shadow_review` y
`production_enablement_authorized` en `false`.
