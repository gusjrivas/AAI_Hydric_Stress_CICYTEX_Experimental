# Proposal: robustez operativa del recorrido CICYTEX (F5, primer sitio)

- HU: UI (recorrido de defensa). Capacidad: `alerting-ui`. Fase CRISP-DM: despliegue/evaluación.
- Impacto científico: ninguno (no cambia modelos, datos, umbrales ni protocolo; no abre holdouts).
- Alcance: sólo `CicytexDefensePage` (sitio representativo). Los demás sitios se migran en cortes posteriores.

## Problemas corregidos
1. Una respuesta tardía de otra sonda/horizonte/fecha podía pisar la vista actual.
2. El feedback podía enviarse dos veces (Enter repetido) y usaba un `session` capturado obsoleto.
3. Un catálogo fallido no tenía reintento ni estado de carga.
4. El componente estaba minificado en pocas líneas, difícil de revisar.
