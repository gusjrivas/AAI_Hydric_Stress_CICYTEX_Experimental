# Evaluación experimental CICYTEX

## Alcance y datos

Se ejecutó una evaluación real sobre el subconjunto CICYTEX del DOI
`10.5281/zenodo.17583691`: tomate de industria, Talavera la Real, campaña 2023,
21 sondas Teros 10 a 20 cm. La serie diaria contiene 2.205 filas (105 días por
sonda), del 12 de abril al 25 de julio de 2023, sin valores nulos ni fechas
duplicadas de humedad; 112 filas-día tienen cobertura intradiaria parcial.

El paquete no aporta meteorología utilizable junto con estas series. Por ello se
usaron únicamente humedad actual, retardos 1/2/3 y medias móviles 3/7, calculados
por sonda. No se mezclaron Pergamino, Melchor Romero, datos sintéticos ni otros
datasets del ZIP.

## Diseño

La partición fue cronológica por fecha objetivo: 50% entrenamiento, 15%
calibración sigmoide, 15% validación para elegir familia y 20% evaluación final
intacta. El percentil 20 de humedad futura se ajustó exclusivamente con
entrenamiento. Se reutilizaron las familias y el ajuste ponderado de
`controlled_daily_v4`: regresión logística, Random Forest e HistGradientBoosting.

El evento positivo es un **proxy estadístico** (`humedad futura < P20_train`), no
una observación fisiológica de estrés hídrico. Los MAE/RMSE corresponden al
baseline numérico de persistencia, no a un regresor entrenado.

## Resultados finales

| Horizonte | Familia | N final | MCC | Precision | Recall | F1 | ROC-AUC | PR-AUC | Brier | Persistencia MAE | Persistencia RMSE |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| +1 día | Logistic Regression | 420 | 0.8941 | 0.9194 | 0.9607 | 0.9396 | 0.9907 | 0.9884 | 0.0419 | 0.00493 | 0.00759 |
| +2 días | Random Forest | 420 | 0.7838 | 0.8526 | 0.9050 | 0.8780 | 0.9641 | 0.9305 | 0.0805 | 0.00769 | 0.01154 |
| +3 días | Random Forest | 420 | 0.7378 | 0.8306 | 0.8686 | 0.8492 | 0.9402 | 0.8810 | 0.0980 | 0.00954 | 0.01425 |

Matrices de confusión `[TN, FP; FN, TP]`: +1 `[[227,15],[7,171]]`, +2
`[[213,28],[17,162]]`, +3 `[[214,31],[23,152]]`.

## Trazabilidad e infraestructura

MLflow exclusivo: `http://localhost:5500`, experimento
`cicytex-external-validation`. Parent run:
`d70d1468c70c4c269bc4888ab83bc8aa`; children +1
`41ce10f969134823b1a9896aae77c665`, +2
`7ee4a8cc664648948438beed03b71409`, +3
`5c814afbcad1497d87aa6c9b9a31887d`. El parent registra el commit ejecutado
`80853b16b9ccc0ec5172630f094222c073575349`. Una ejecución completa anterior también
persistió tras reiniciar PostgreSQL, MinIO y MLflow; las cuatro corridas siguieron
`FINISHED` y sus artefactos permanecieron listables. Hubo una corrida inicial fallida por codificación CP1252 de la salida
de MLflow; se corrigió sin alterar datos ni metodología y se repitió completa.

## Limitaciones y conclusión

Hay un único sitio y una única campaña de humedad; las 21 sondas comparten el
mismo calendario y no equivalen a 2.205 días independientes. La etiqueta deriva
de la misma variable pronosticada, no de mediciones fisiológicas, y no existe una
campaña externa separada. Los resultados evidencian capacidad temporal para
anticipar el proxy dentro de esta campaña; no demuestran estrés fisiológico,
generalización agronómica ni validación externa multi-sitio/multi-campaña. La
degradación monotónica con el horizonte es coherente con mayor incertidumbre.

