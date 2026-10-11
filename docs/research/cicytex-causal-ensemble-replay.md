# Reproducción causal CICYTEX

## Alcance

Esta capacidad usa exclusivamente CICYTEX (tomate de industria, Talavera la Real,
campaña 2023). El evento evaluado es humedad volumétrica a 20 cm por debajo del
percentil 20 estimado solo con entrenamiento. No es una etiqueta independiente de
estrés fisiológico.

La validación empleada para fijar el diseño termina el 5 de julio de 2023. Por eso
la primera emisión legítima es el 6 de julio. Las predicciones anteriores no se
presentan en la interfaz.

## Reproducir

1. Mantener intacto el ZIP en
   `C:\Users\gusta\Downloads\AAI_Hydric_Stress_External_Datasets.zip`.
2. Verificar SHA-256
   `3b86919e95558217ee106855234b75d745a3b60f997e441ed39e1b9e3abf67a5`.
3. Preparar la copia ignorada `data/cicytex/raw/` siguiendo
   `docs/research/cicytex-reproduction.md`.
4. Iniciar el tracking aislado: `docker compose -f compose.cicytex.yml up -d postgres-cicytex minio-cicytex minio-init-cicytex mlflow-cicytex`.
5. Ejecutar: `python scripts/run_cicytex_causal_ensemble.py`.
6. Levantar UI/API sin inferencia: `docker compose -f compose.cicytex.yml up -d --build backend frontend-cicytex`.
7. Abrir `http://localhost:55180/index.html#defensa-cicytex`.

Para detener únicamente esta interfaz: `docker compose -f compose.cicytex.yml stop frontend-cicytex backend`.
No se requiere ni se debe usar una limpieza global de Docker.

La navegación lee `results/cicytex/causal_replay/predictions.csv`. Los modelos se
registran en MLflow/MinIO y la copia local ignorada se conserva bajo
`results/cicytex/causal_replay/models/`; la UI no entrena ni infiere.
