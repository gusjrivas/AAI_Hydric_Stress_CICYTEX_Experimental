## Context

ADR-0014 fija Laya `v0.4.2`, commit
`68804629e8ccd9d616d48a40e87de9fabbeae069`, checkpoint multilingüe revisión
`55cf4c4ebb4ebe31b2550e8bdf3bd21b99753851` y los hashes del peso y tokenizer.
También exige corpus de dominio, evaluación fuera de muestra y calibración antes de
habilitar sugerencias visibles.

## Decisiones

1. El evaluador es una hoja arquitectónica pura y offline. No importa FastAPI ni
   ejecuta transporte HTTP.
2. Las cinco categorías y su orden forman parte del contrato versionado.
3. La abstención cuenta como error en accuracy y macro-F1, pero tiene costo menor que
   una clasificación incorrecta aceptada.
4. Las métricas globales se calculan sólo sobre CICYTEX, Pergamino y Melchor Romero.
   El laboratorio mock verifica el contrato operacional, pero no aporta evidencia
   científica.
5. Todo sitio científico se evalúa por separado y un fallo local bloquea el gate.
6. La evidencia sintética jamás puede cambiar el estado a elegible.
7. La serialización canónica excluye el texto del comentario y cualquier dato de
   ejecución no determinista.
8. La verificación de artefactos opera sobre bytes locales y rechaza punteros LFS; no
   descarga pesos ni consulta servicios externos.

## Política V1 preregistrada

Los límites se registran antes de observar un holdout humano y sólo pueden cambiar en
una nueva versión de política:

- coverage >= 0.60;
- accuracy total >= 0.70;
- selective accuracy >= 0.80;
- macro-F1 >= 0.65;
- Brier <= 0.60;
- ECE de diez bins <= 0.10;
- costo medio <= 1.00, con costo 0 correcto, 1 abstención y 5 error aceptado;
- macro-F1 por sitio >= 0.55;
- latencia p95 <= 640 ms.

Estos límites permiten caracterizar el mecanismo; no sustituyen intervalos de
confianza, adjudicación humana ni comparación pareada con baseline. Por diseño, esta
versión emite `BLOCKED_SCIENTIFIC_METHOD_PENDING` aunque los point estimates superen
todos los límites. Esas condiciones deben incorporarse antes de una revisión de
sombra real.

## Consecuencias

- El gate es reproducible en CI sin pesos, red o datos sensibles.
- Una ejecución sin artefactos reales verificados nunca acredita supply chain.
- Una ejecución con fixture sintética puede pasar todas las métricas y aun así queda
  en `CHARACTERIZATION_ONLY`.
- El caller no puede autoafirmar supply chain: el evaluador exige una verificación
  ligada por digest a la identidad fijada y predicciones de la revisión declarada.
- La activación productiva permanece fuera de alcance y requiere otro cambio
  arquitectónico con TDD, evidencia humana cross-site y revisión independiente.
