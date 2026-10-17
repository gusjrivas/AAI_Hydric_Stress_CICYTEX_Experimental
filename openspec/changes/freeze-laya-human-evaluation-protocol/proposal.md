# Change: congelar el protocolo de evaluación humana de Laya

## Por qué

El corpus humano y el plan LOSO ya tienen contratos estructurales, pero aún no
existe una autoridad preregistrada que fije tamaño, balance, acuerdo, artefactos
externos y análisis antes de observar predicciones. Sin ese cierre, cualquier
resultado podría depender de decisiones tomadas después de inspeccionarlo.

## Qué cambia

- Se agrega un verificador puro, basado en bytes, para un manifest cerrado.
- El manifest queda ligado por digest al corpus privado y al plan LOSO.
- Se verifican por contenido seis artefactos externos: muestreo, guía de
  anotación, adjudicación, desidentificación, cadena de custodia y protocolo del
  baseline.
- Se fijan pisos de cohorte y acuerdo nominal pre-adjudicación.
- Se fijan labels/zero-division de macro-F1, estimandos global/por sitio, baseline,
  márgenes, bootstrap pareado, probabilidades de cola y la regla Holm step-down.
  Los intervalos 95 % quedan descriptivos; el PASS exige rechazo de las cuatro
  hipótesis. También se congelan los umbrales legacy vigentes, sin ejecutar ni
  evaluar modelos.
- El summary público no contiene texto ni identificadores privados.

## Fuera de alcance

- No se versiona el corpus real ni los artefactos externos reales.
- No se ejecuta Laya, baseline, bootstrap ni inferencia estadística.
- No se acredita autenticidad científica, suficiencia, shadow readiness ni
  habilitación productiva.
- Los N de fixtures son sintéticos y no constituyen una decisión de potencia; sin
  corpus privado externo el estudio permanece `BLOCKED_CORPUS_NOT_PROVIDED`.
