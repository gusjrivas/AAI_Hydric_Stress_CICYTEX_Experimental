# Evaluación retrospectiva causal CICYTEX con ensamble

## Diseño y advertencia epistemológica

Se usaron 2.205 observaciones diarias de 21 sondas CICYTEX entre el 12/04/2023 y
el 25/07/2023, sin mezclar otros sitios. El ZIP y la tabla fuente fueron
verificados con SHA-256 `3b8691…f67a5` y `06d662…96482`, respectivamente.

Para cada horizonte se ajustaron Logistic Regression, Random Forest e
HistGradientBoosting con el pipeline existente. El escalado propio de la familia,
el ajuste y la calibración quedaron limitados a entrenamiento/calibración. La
selección metodológica termina el 05/07/2023 y todas las emisiones archivadas
comienzan el 06/07/2023. El ensamble es el promedio aritmético de los tres scores
calibrados, pesos 1/3 y umbral 0,5. Persistencia clasifica usando la humedad en T
contra el P20 congelado.

La evaluación CICYTEX anterior ya había inspeccionado este holdout. Este análisis
es retrospectivo adicional, no una confirmación ciega independiente. Tampoco hay
etiquetas agronómicas independientes: “positivo” significa humedad baja según el
proxy P20 de entrenamiento.

## Resultados diarios reales

| Horizonte | Método | n | MCC | Precision | Recall | F1 | FP | FN | Brier |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| +1 | Logistic Regression | 399 | 0.904 | 0.933 | 0.960 | 0.946 | 12 | 7 | 0.037 |
| +1 | Random Forest | 399 | 0.888 | 0.931 | 0.942 | 0.937 | 12 | 10 | 0.046 |
| +1 | HistGradientBoosting | 399 | 0.862 | 0.920 | 0.925 | 0.922 | 14 | 13 | 0.050 |
| +1 | Ensamble | 399 | 0.888 | 0.927 | 0.948 | 0.937 | 13 | 9 | 0.042 |
| +1 | Persistencia | 399 | 0.898 | 0.953 | 0.931 | 0.942 | 8 | 12 | 0.050 |
| +2 | Logistic Regression | 378 | 0.806 | 0.850 | 0.939 | 0.892 | 27 | 10 | 0.065 |
| +2 | Random Forest | 378 | 0.798 | 0.861 | 0.914 | 0.887 | 24 | 14 | 0.074 |
| +2 | HistGradientBoosting | 378 | 0.801 | 0.875 | 0.902 | 0.888 | 21 | 16 | 0.083 |
| +2 | Ensamble | 378 | 0.802 | 0.871 | 0.908 | 0.889 | 22 | 15 | 0.067 |
| +2 | Persistencia | 378 | 0.838 | 0.913 | 0.902 | 0.907 | 14 | 16 | 0.079 |
| +3 | Logistic Regression | 357 | 0.772 | 0.828 | 0.921 | 0.872 | 29 | 12 | 0.082 |
| +3 | Random Forest | 357 | 0.761 | 0.848 | 0.882 | 0.865 | 24 | 18 | 0.091 |
| +3 | HistGradientBoosting | 357 | 0.763 | 0.840 | 0.895 | 0.866 | 26 | 16 | 0.090 |
| +3 | Ensamble | 357 | 0.774 | 0.846 | 0.901 | 0.873 | 25 | 15 | 0.082 |
| +3 | Persistencia | 357 | 0.816 | 0.905 | 0.882 | 0.893 | 14 | 18 | 0.090 |

## Episodios y conclusiones

En +1, Logistic Regression fue el mejor clasificador diario por MCC y también
tuvo menos omisiones que el ensamble. En +2 y +3, persistencia obtuvo mejor MCC y
F1 que todos los modelos aprendidos. El ensamble no supera de forma consistente
ni a las familias individuales ni a persistencia.

La lectura cambia para inicios de episodios: persistencia no anticipó ninguno de
los 7 inicios evaluables a +1, mientras el ensamble anticipó 3; a +2 anticipó 2 de
6 frente a 1 de persistencia; a +3 anticipó 3 de 7 frente a 2 de persistencia.
Ese beneficio vino acompañado de más falsas alertas (13/22/25 para ensamble frente
a 8/14/14 para persistencia). No se atribuye significación estadística a estas
diferencias: hay pocos episodios y dependencia temporal/entre mediciones de una
misma campaña.

El desempeño diario se deteriora con el horizonte: MCC del ensamble 0,888, 0,802
y 0,774 para +1, +2 y +3. Los resultados completos, incluida ROC-AUC, PR-AUC,
matrices y conteos, están en `results/cicytex/causal_replay/metrics.csv`.

MLflow: experimento `cicytex-causal-ensemble-replay`, corrida padre
`6dda3d62a448426fb2ce510dea0d097a`; las nueve corridas hijas se registran en
`results/cicytex/causal_replay/summary.json`.

La alternativa secundaria por mayoría produjo MCC 0,893, 0,803 y 0,773 para
+1/+2/+3, respectivamente. No reemplaza al promedio principal y tampoco cambia
la conclusión frente a persistencia.
