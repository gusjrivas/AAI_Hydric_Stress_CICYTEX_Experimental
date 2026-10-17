# Change: Destino «Arquitectura» e indicador de modo en la UI

## Trazabilidad

- **HU:** HU6 (integración) y presentación HU7; **capacidad:** `alerting-ui`; **CRISP-DM:** Despliegue.
- **Insumos:** `docs/design/ui-arquitectura-defensa.md`, ADR-0014, `docs/superpowers/plans/2026-10-17-arquitectura-ui-checkpoint-f0-f1.md`.
- **Impacto científico:** ninguno (sin cambios en datos, modelos, umbrales, protocolo, permisos ni revelación de observaciones).

## Why

El mapa de arquitectura estaba oculto en un `<details>` colapsado de Herramientas y no hay indicación común de si una vista es operación, replay histórico o laboratorio sintético.

## What Changes

- Nuevo destino `#arquitectura` (grupo `arquitectura`) que aloja `ArchitectureFlow` sin cambiar sus etapas.
- `ModeBadge` derivado sólo de la ruta (`modeForView`), sin I/O.
- Los cinco destinos previos y todas las anclas siguen resolviendo.

## Non-goals

Backend, contrato OpenAPI, telemetría, ejecución de modelos, cambios de umbrales o de ensamble.

## Rollback

Revertir el PR; las anclas previas no se modifican.
