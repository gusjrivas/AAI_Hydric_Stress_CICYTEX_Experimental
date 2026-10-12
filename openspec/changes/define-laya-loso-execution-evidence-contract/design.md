# Diseño: evidencia LOSO canónica, privada y fail-closed

## Contexto y límite de confianza

Este slice recibe un plan LOSO privado ya sellado y un lote de predicciones que un
caller afirma haber obtenido de Laya. Su responsabilidad termina en validar forma,
cobertura, identidad declarada y reproducibilidad del lote. No invoca red ni modelo,
no inspecciona una imagen o paquete de runtime y no puede probar que las
predicciones provengan realmente del runtime declarado o hayan sido generadas sin
acceso a gold labels.

## Decisiones

### 1. Contrato ligado a plan, corpus, runtime y protocolo

`laya-loso-execution-contract-v1` recalcula y valida los digests del plan LOSO y del
corpus. Además conserva una referencia opaca `laya-runtime-identity-v1`, ID y SHA-256
del protocolo de ejecución, proveedor `laya-http` y una revisión del modelo expresada
como SHA-1 lowercase completo y no nulo.

`loso_plan_sha256` y `evaluation_corpus_sha256` existen únicamente como bindings
internos. Ambos quedan fuera de `repr` y del summary público: el digest del plan
deriva a su vez del digest del corpus, por lo que exponer cualquiera de sus claves o
valores crearía una superficie indirecta de confirmación del corpus privado.

La referencia del runtime todavía no verifica artefactos. Por ello
`runtime_identity_verified`, `origin_verified`,
`gold_blind_execution_attested` y `supply_identity_verified` permanecen en falso en
contrato, evidencia y summary público.

### 2. Cobertura outer-test exacta

El conjunto esperado se deriva exclusivamente de `test_records` de cada fold. La
validación exige una y sólo una fila para cada par privado de fold y ejemplo. Una
fila ausente, adicional, duplicada, asignada a otro sitio retenido o proveniente de
fit/calibración invalida el lote completo. Los errores son genéricos y no incluyen
IDs ni payload humano.

El proveedor y la revisión de cada fila deben coincidir con el contrato. Esta regla
evita mezclar outputs de ejecuciones declarativamente distintas, aunque todavía no
autentica su origen.

### 3. Predicción cerrada y numéricamente inequívoca

Cada fila usa el orden fijo de categorías del contrato humano. Las probabilidades
deben ser numéricas no booleanas, finitas, no negativas, sumar uno y tener un argmax
único que coincida con la categoría elegida. `unclassified` no es una salida válida.
La confidence es opcional, pero cuando existe debe estar en `[0, 1]`; la latencia
debe ser finita y no negativa.

La representación canónica normaliza enteros y floats equivalentes, incluido cero
negativo, para que diferencias de representación no creen evidencias distintas.

### 4. Orden canónico y commitment privado completo

Las filas se ordenan por el orden contractual de sitios retenidos y luego por ID de
ejemplo. El commitment privado `prediction_content_sha256` cubre, con separación de
dominio, fold, ejemplo, categoría, probabilidades, confidence, latencia, proveedor y
revisión de cada fila canónica. Construcción directa o reemplazo vuelve a validar el
contenido y rechaza un digest inconsistente o el sentinel nulo.

El commitment está excluido de `repr` y del summary público. Como el universo de
ejemplos y categorías puede ser pequeño o predecible, publicarlo facilitaría
confirmación por diccionario.

### 5. Summary público mínimo y sensible sólo a agregados seguros

El summary JSON canónico incluye sólo identidades no derivadas del corpus: referencia
de runtime, protocolo, proveedor y revisión del modelo. Agrega el número total de
predicciones, flags y un único agregado de latencia con `count`, `minimum`, `maximum`
y `mean`. Este agregado hace que el digest público sea sensible a cambios de latencia
sin publicar hashes de filas ni commitments del contenido.

Quedan excluidos `example_id`, `group_id`, comentarios, anotadores, adjudicaciones,
categorías, probabilidades, `records_sha256`, hashes por fila y
`prediction_content_sha256`. También se excluyen explícitamente las claves y valores
de `loso_plan_sha256` y `evaluation_corpus_sha256`; ambos bindings permanecen
disponibles sólo dentro del objeto privado. Dos lotes con iguales agregados públicos
pueden tener el mismo summary aun cuando sus commitments privados difieran; esa
separación es intencional.

### 6. Estado fail-closed y alcance TDD

Un lote validado sólo establece `execution_evidence_validated=true` y conserva:

- `execution_completed=false`;
- `scientifically_sufficient=false`;
- `eligible_for_shadow_review=false`;
- `production_enablement_authorized=false`.

El cambio se construyó mediante una cadena RED/GREEN: primero se fijaron tests de
binding, cobertura, validación numérica, determinismo, privacidad, commitments,
attestations y aislamiento; luego se implementó el mínimo contrato que los satisface.
Todo endurecimiento posterior requiere un nuevo RED antes de modificar producción.

### 7. Aislamiento arquitectónico

Ningún adapter, backend, gate offline, módulo de forecast, ingesta, predictive
modeling, experiment runner o script importa este contrato. PR15 incorporará la
identidad verificable de runtime, lock y SBOM; otro slice posterior implementará el
executor. Hasta entonces no existe un camino desde este objeto hacia readiness o
producción.

## Consecuencias

- Un lote estructuralmente válido queda reproducible y ligado a identidades
  declaradas sin exponer sus filas privadas.
- El commitment interno detecta cambios que el resumen público deliberadamente no
  revela.
- La frontera evita contaminación entre folds y revisiones, pero no prueba origen ni
  ejecución real.
- Cualquier afirmación científica u operacional permanece bloqueada.
