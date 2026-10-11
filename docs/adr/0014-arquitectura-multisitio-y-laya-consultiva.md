# ADR-0014: Núcleo multisitio y Laya como asistencia consultiva

Estado: **Aceptado para implementación incremental el 2026-10-11**.

Trazabilidad: HU6 (`architecture-integration`) para el puerto de replay; HU5
(`human-feedback`) y UI (`alerting-ui`) para el triaje. Fase CRISP-DM: despliegue e
integración experimental. No cambia configuraciones experimentales, hipótesis ni HU7/HU8.

## Contexto

El repositorio debe conservar cuatro contextos que no son intercambiables:

- Pergamino, con ERA5+NASA, ventanas temporales y protocolo de ensemble propios.
- Melchor Romero, con imputación causal por partición y procedencia explícita.
- CICYTEX, con 21 sondas, P20 sólo para entrenamiento y replay causal archivado.
- Laboratorio, con sensores sintéticos deterministas para prueba operacional; no es
  evidencia científica.

La incorporación del dataset CICYTEX dejó lógica de lectura CSV dentro de la ruta
HTTP. Además se solicita incorporar Laya, un motor de decisiones tipadas, sin que
una dependencia experimental pueda alterar predicciones, recalibración o evidencia.

## Decisión

Adoptar una evolución hexagonal incremental, sin reescritura completa:

1. Los casos de uso y puertos compartidos viven en `src/`; FastAPI sólo adapta HTTP.
2. Cada fuente científica conserva su adaptador, protocolo temporal y artefactos.
   Compartir mecanismos no autoriza homogeneizar hipótesis ni datasets.
3. El catálogo CICYTEX depende de `ReplayCatalogSource`; pandas y CSV quedan en el
   adaptador `CsvReplayCatalogSource`.
4. Laya implementa `DecisionPolicyEngine` por HTTP y sólo clasifica comentarios para
   una cola de revisión humana. Toda respuesta conserva `human_review_required=true`.
5. Baja confianza implica abstención. Timeout, indisponibilidad o respuesta inválida
   producen un fallback determinista y no bloqueante.
6. Laya está desactivada por defecto. `LAYA_DECISION_URL` y
   `LAYA_MODEL_REVISION` deben configurarse juntas. Su endpoint es aditivo:
   `POST /api/v2/feedback/triage`.
7. Queda prohibido invocar `DecisionPolicyEngine` desde forecast, cálculo de stress,
   recalibración, admisión de evidencia o recomendaciones de riego.

## Cadena de suministro fijada

- Código Laya: `v0.4.2`, commit
  `68804629e8ccd9d616d48a40e87de9fabbeae069`, licencia Apache-2.0.
- Runtime verificado: Python 3.11, Laya 0.4.2 y PyTorch 2.14.0+cpu.
- Bundle de checkpoints: `convaiinnovations/laya`, revisión revisada
  `55cf4c4ebb4ebe31b2550e8bdf3bd21b99753851`.
- Peso `multilingual/model.safetensors`: SHA-256
  `9d628fd971b700382ac6f65920a86f149777b2e748e0c955fb3b19695aa8f204`.
- Tokenizer `multilingual/tokenizer/tokenizer.json`: SHA-256
  `609d8f4c067cd3950f88594c5a802616cea245823836ef5848ee4fc40aab5b6f`.

Los pesos no se versionan en Git. El despliegue debe montar un caché externo, fijar
la revisión y verificar los digests antes de habilitar el sidecar.

## Evidencia y límites

Cada cambio de producción se precede por un commit RED y otro GREEN. El primer corte
conservó el contrato HTTP CICYTEX y luego introdujo el puerto. Los cortes Laya
especificaron primero el caso de uso, el adaptador y el endpoint.

La verificación inicial aprobó las suites dirigidas de CICYTEX, Pergamino, Melchor
Romero y laboratorio, además del build y las pruebas frontend. La inferencia de humo
de Laya se ejecutó con el checkpoint multilingüe fijado.

Esto no demuestra calidad agronómica ni autoriza decisiones automáticas. El model
card declara sobreconfianza y desempeño zero-shot cercano al azar en decisiones
tipadas; antes de habilitar sugerencias visibles se requiere un corpus etiquetado del
dominio, evaluación fuera de muestra, calibración y un umbral decidido por costo de
error. Hasta entonces Laya permanece en sombra y toda salida es experimental.

## Consecuencias

- Los flujos existentes siguen siendo la referencia de regresión.
- Nuevos sitios implementan puertos compartidos sin introducir condicionales de sitio
  en los casos de uso.
- El sidecar puede actualizarse o retirarse sin cambiar el dominio ni los pipelines.
- La observabilidad futura debe registrar latencia, revisión, confianza, abstención y
  decisión humana final, sin reutilizar esos datos para entrenar automáticamente.
