# Diseño: corpus humano privado y candidato

## Contexto y límite de confianza

El corpus real contiene texto y trazas humanas que no deben entrar al control de
versiones. El repositorio sólo define un parser fail-closed y una representación
pública de su identidad. El objeto resultante acredita que el material presentado
cumple el contrato estructural; no acredita que la recolección declarada haya
ocurrido, que los protocolos externos correspondan a sus digests ni que la muestra
sea científicamente suficiente.

## Decisiones

### 1. Dos archivos privados y un schema cerrado

El loader recibe rutas explícitas a un manifest y a un array de registros ubicados
fuera del repositorio. Ambos documentos rechazan campos faltantes, adicionales o
duplicados, números no finitos y strings no canónicos. No se incluye fixture con
comentarios humanos reales ni se descubre el corpus mediante variables de entorno.

El manifest fija:

- `schema_version`, `corpus_id`, `evidence_role=human_corpus_candidate`;
- `records_count` y `records_sha256`;
- los sitios exactos y la política de anotación/adjudicación;
- versión de rúbrica;
- identificadores y SHA-256 de los protocolos de muestreo, guía de anotación,
  adjudicación y desidentificación;
- `custody_digest` y `frozen_at` UTC canónico;
- `declared_source_kind=human_field`, `deidentified=true` y
  `privacy_reviewed=true`.

Salvo `records_sha256`, que se recalcula sobre la representación canónica de los
registros, estos digests y booleanos se validan sintácticamente como attestations.
Su verificación contra artefactos externos pertenece a un cambio posterior.

### 2. Identidad ligada a los registros privados

Antes de construir el corpus se ordenan registros por `example_id` y anotaciones
por `annotator_id`, se serializan como JSON canónico y se compara su SHA-256 con el
manifest. Esto hace que cualquier cambio material en comentario, sitio, grupo,
anotaciones, adjudicación o gold label invalide el manifest.

`evaluation_corpus_digest` resume el summary público, que incluye
`records_sha256`. Por ello la identidad publicada sigue ligada al corpus privado
sin publicar su payload.

### 3. Adjudicación humana trazable

Cada ejemplo requiere al menos dos `annotator_id` distintos. Si todas las
anotaciones coinciden, el gold label debe ser ese consenso y no puede existir
adjudicación. Si difieren, debe existir un objeto de adjudicación con categoría,
`decision_ref` e identificador de adjudicador; ese adjudicador debe ser distinto de
todos los anotadores y su categoría debe coincidir con el gold label.

Los identificadores y referencias permiten auditoría dentro del entorno privado,
pero nunca se incluyen en el summary público.

### 4. Cohorte cross-site sólo a nivel estructural

Los registros deben cubrir exactamente `cicytex`, `melchor-romero` y `pergamino`.
Un mismo `group_id` no puede aparecer en más de un sitio, evitando contaminación
estructural entre sitios. Esto todavía no define folds LOSO, aislamiento temporal,
calibración ni balance de muestra.

### 5. Summary público sin PII ni texto humano

La serialización pública contiene únicamente metadata del manifest, attestations,
digests y los flags estructurales. Excluye la lista de registros completa y, con
ella, comentarios, `example_id`, `group_id`, `annotator_id`, `adjudicator_id`,
`decision_ref`, anotaciones y gold labels. Su orden y encoding son deterministas.

### 6. Aislamiento y estado provisional inmutable

El módulo no es importado por el gate offline, backend ni flujos científicos u
operacionales. Construcción directa y reemplazos inconsistentes vuelven a validar
metadata, cohorte, cardinalidad y digest. Un corpus aceptado siempre informa:

- `structurally_valid=true`;
- `scientifically_sufficient=false`;
- `production_enablement_authorized=false`.

No existe en este slice una transición hacia suficiencia científica, shadow review
o producción.

## Consecuencias

- Se puede verificar localmente un candidato privado sin filtrar su contenido.
- La procedencia declarada queda explícita y ligada a una identidad reproducible.
- Una declaración falsa pero sintácticamente correcta no es detectable aquí; debe
  contrastarse con protocolos y cadena de custodia externos en una revisión futura.
- La evaluación estadística continúa bloqueada hasta preregistrar tamaño, balance,
  LOSO, calibración, baseline y CI bootstrap.
