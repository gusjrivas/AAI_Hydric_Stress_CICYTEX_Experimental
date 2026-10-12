# Change: Contrato de procedencia para el corpus humano de evaluación de Laya

Estado: implementado como contrato estructural candidato; no constituye evidencia
científica suficiente ni autoriza uso productivo.

## Why

El gate offline de Laya necesita, antes de incorporar un protocolo científico, una
frontera explícita para recibir un corpus humano privado sin versionar sus registros
ni exponer comentarios, identificadores de revisores o referencias de adjudicación.
Sin esa frontera, una colección bien formada podría confundirse con evidencia
cross-site suficiente o entrar accidentalmente en flujos operacionales.

## What Changes

- Define el schema cerrado `laya-human-evaluation-corpus-v1` para un candidato de
  corpus humano de campo conservado fuera del repositorio.
- Exige un manifest con identidad del corpus, digest SHA-256 de los registros,
  sitios exactos y metadatos de rúbrica, muestreo, anotación, adjudicación,
  desidentificación y custodia.
- Exige al menos dos anotadores distintos por ejemplo y una adjudicación explícita,
  trazable y realizada por una tercera persona cuando hay desacuerdo.
- Rechaza identificadores de grupo compartidos entre sitios y exige cobertura
  exactamente de `cicytex`, `melchor-romero` y `pergamino`.
- Produce sólo un summary público, canónico y determinista: conserva el digest que
  lo liga a los registros privados, pero excluye comentarios, ejemplos,
  identificadores de anotadores y datos de adjudicación.
- Mantiene `scientifically_sufficient=false` y
  `production_enablement_authorized=false` de manera incondicional.
- Mantiene el contrato completamente aislado del gate de readiness, backend,
  forecast, ingesta, entrenamiento, recalibración y runners experimentales.

## Impact

El cambio es aditivo y está contenido en
`human_feedback.evaluation_corpus`. No incorpora un dataset humano al repositorio,
no modifica la decisión del gate offline y no altera las corridas existentes de
CICYTEX, Pergamino, Melchor Romero ni laboratorio mock.

La validación de digests comprueba formato y, para `records_sha256`, correspondencia
con los bytes canónicos de los registros cargados. Los digests de protocolos y
custodia, junto con `deidentified=true`, `privacy_reviewed=true` y
`declared_source_kind=human_field`, son attestations declarativas del manifest: este
slice no descarga, abre ni autentica externamente esos documentos y por lo tanto no
los convierte en prueba automática.

## Deferred

Quedan expresamente fuera de este cambio:

- fijar N mínimo, alfa/acuerdo interanotador y balance por sitio o categoría;
- definir y ejecutar LOSO por sitio/grupo y el split independiente de calibración;
- comparar en los mismos folds contra baseline con delta pareado e intervalos de
  confianza bootstrap;
- conectar el corpus al gate o emitir `ELIGIBLE_FOR_SHADOW_REVIEW`;
- habilitar sugerencias visibles o cualquier uso productivo de Laya.
