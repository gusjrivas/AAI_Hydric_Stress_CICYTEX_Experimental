## 1. TDD de snapshot
- [x] 1.1 Registrar RED de manifiesto, digest canónico e identidad por archivo.
- [x] 1.2 Implementar GREEN leyendo cada CSV una vez y parseando los bytes capturados.
- [x] 1.3 Conservar igualdad exacta del DataFrame y fachada histórica.

## 2. TDD de procedencia
- [x] 2.1 Registrar RED de identidades normalizada, primaria y de archivo.
- [x] 2.2 Implementar sidecar determinista y validación de aliases históricos.
- [x] 2.3 Conectar runners y scripts mediante kwargs opcionales.

## 3. Verificación
- [x] 3.1 Ejecutar regresiones focales CICYTEX y pruebas de TOCTOU.
- [x] 3.2 Ejecutar regresiones Pergamino, Melchor, Laboratorio y Laya.
- [x] 3.3 Validar lint, OpenSpec, suite completa y grafo.

## Evidencia de cierre
- CICYTEX focal, scripts y equivalencia diferencial: 41 pruebas verdes.
- Suite raíz: 1320 verdes, 11 omitidas y 8 fallos ambientales reproducidos sin
  diferencias sobre `main@27f6dd2`.
- Backend: 190 pruebas verdes.
- Frontend: 309 pruebas verdes, lint sin errores y build productivo verde.
- OpenSpec: validación estricta verde.
- Grafo final: 12 384 nodos y 35 283 aristas; símbolos nuevos localizados. Los scripts
  continúan excluidos del índice y se verificaron por lectura directa.
- Historia TDD final: commit RED sólo con pruebas (19 fallos contractuales), commit
  GREEN sólo con implementación (41 pruebas focales verdes) y este cierre sólo con
  especificación y evidencia.
- Los dos runners se ejecutaron en modo legacy y enriched: el sidecar fue el único
  archivo nuevo; CSV, métricas, resultados y artefactos deterministas fueron idénticos,
  y los modelos conservaron tipo, parámetros y `predict_proba` sobre la sonda
  determinista del gate.
