# Reproducción del experimento CICYTEX

El ZIP original permanece fuera de Git. La ejecución validada usa
`C:\Users\gusta\Downloads\AAI_Hydric_Stress_External_Datasets.zip` y verifica
SHA-256 `3B86919E95558217EE106855234B75D745A3B60F997E441ED39E1B9E3ABF67A5`.

1. Extraer solamente `originales/cicytex`, `normalizados/cicytex__*` y los metadatos
   a `data/cicytex/raw/` (ruta ignorada por Git), sin modificar el ZIP.
2. Comprobar que los puertos 5500, 55432, 59000 y 59001 estén libres.
3. Iniciar: `docker compose -p aai-cicytex-experiment -f compose.cicytex.yml up -d --build`.
4. Ejecutar:
   `python scripts/run_cicytex_experiment.py --zip C:\Users\gusta\Downloads\AAI_Hydric_Stress_External_Datasets.zip --tracking-uri http://localhost:5500`.
5. Verificar MLflow en `http://localhost:5500` y reiniciar el stack para comprobar persistencia.
6. Apagar sin limpiar otros proyectos: `docker compose -p aai-cicytex-experiment -f compose.cicytex.yml down`.

No usar `down -v`, `docker system prune` ni comandos globales de limpieza: los volúmenes
nombrados conservan PostgreSQL y MinIO para reproducibilidad.
