# Presentación centrada en los dos sitios principales

Alcance vigente por decisión del autor (2026-10-24). La UI permite mostrar
Pergamino, Melchor Romero y laboratorio sintético. CICYTEX permanece archivado
como extensión experimental; no se ofrece desde menús, seguimiento histórico
ni recorrido guiado. `#defensa-cicytex` abre la vista predeterminada «Mi cultivo».

## Recorrido para grabar

1. `#arquitectura`: explicar los módulos y sus relaciones. El diagrama describe
   el diseño; no es telemetría de una ejecución.
2. Mostrar por separado la ejecución real preparada y los registros existentes
   de MLflow. La UI histórica no reentrena ni crea evidencia experimental nueva.
3. `#demo-guiada`: Pergamino, Melchor Romero y laboratorio, en ese orden.
   Mostrar procedencia, pronóstico, avance y observación posterior en cada sitio.
   Identificar el laboratorio como simulación.
4. Para ampliar el detalle, usar `#defensa-pergamino` y
   `#defensa-melchor-romero`.

Preparar los datos y servicios de los dos sitios según las secciones pertinentes
[de la guía de arranque](defense-demo-startup-guide.md). Retirar una pantalla no
elimina las dependencias de los recorridos que continúan visibles.

## Verificación técnica

`verify-journeys.mjs` comprueba la UI con respuestas grabadas; incluye el nuevo
recorrido y la URL retirada. `rehearse-demo.mjs` ensaya arquitectura, los dos
sitios y laboratorio. Ambos usan el servidor de fixtures y Chrome; sus resultados
no demuestran inferencia real ni la disponibilidad del backend de producción.
Los informes y guiones anteriores con CICYTEX son antecedentes históricos.

No cambian modelos, protocolos, métricas ni resultados. No se deriva ninguna
conclusión científica del retiro de CICYTEX de la presentación.
