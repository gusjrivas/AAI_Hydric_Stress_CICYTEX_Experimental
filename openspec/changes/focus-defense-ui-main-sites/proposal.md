# Centrar la UI de defensa en Pergamino y Melchor Romero

## Motivo y autorización

El autor solicita que no se muestre CICYTEX en la UI del repositorio experimental.
La presentación de la memoria y el video priorizan los dos sitios principales.
Esta decisión cambia el alcance visible, no el alcance de la evidencia archivada.

## Trazabilidad

- HU: HU6; capacidad OpenSpec: `alerting-ui`.
- CRISP-DM: despliegue / comunicación del prototipo.
- Configuración experimental e hipótesis: sin cambios.
- Arquitectura: se conservan módulos, adaptadores, API y componentes archivados.
- HU7/HU8: sin ejecuciones ni cambios de resultados o protocolo.
- Memoria: alinear sólo la descripción y capturas de la interfaz; no editar
  métricas ni conclusiones por este cambio.

## Criterios

- Navegación histórica sólo con Pergamino y Melchor Romero.
- Recorrido guiado de tres pasos: ambos sitios y laboratorio sintético.
- Sin montaje de la pantalla CICYTEX mediante su antigua URL, ni consultas a su
  API al entrar por esa URL o abrir el recorrido guiado.
- Preservar la procedencia independiente de cada sitio, foco de teclado,
  revelado causal, reinicio al volver y estados de error.
- Mantener las pruebas de los componentes CICYTEX archivados como pruebas
  directas, sin reintroducirlos en el recorrido.

## Validación

Ver `tasks.md`. Los recorridos de navegador usan fixtures; no son evidencia
científica ni una ejecución del backend real.
