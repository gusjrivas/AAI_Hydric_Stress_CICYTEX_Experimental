# Proposal: recorrido del laboratorio de sensores con jerarquía de acciones y trazabilidad declarada (F5/F6)

- HU: HU6 (UI). Capacidad: `alerting-ui`. Fase CRISP-DM: evaluación.
- Impacto científico: ninguno. No cambia backend, modelos, endpoints, protocolos ni la lógica de fases. El laboratorio sigue siendo una simulación sin evidencia científica.
- Problema: todos los pasos tenían el mismo estilo, no se explicaba por qué un paso estaba deshabilitado y no se mostraba la trazabilidad de la sesión de prueba (sensor, semilla, procedencia sintética, reloj ficticio) ni lo que no existe en este recorrido.
- Cambio: paso de la fase actual como acción primaria y el resto secundarias; nota enlazada con `aria-describedby` a los pasos deshabilitados; panel «Trazabilidad de esta sesión de prueba» que declara los datos y la revisión como sintéticos, el reloj como ficticio y «no disponible» para commit, SHA-256 del dataset, MLflow, versión de modelo y linaje.
- Fuera de alcance, declarado: filtro de observaciones futuras (el laboratorio no tiene verdad oculta y su reloj es cosmético); verificación en navegador real del laboratorio.
