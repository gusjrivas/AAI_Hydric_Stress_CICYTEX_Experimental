# Índice de documentos de investigación

Actualizado 2026-10-20, rama `docs/actualizacion-memoria-defensa`, commit
revisado `d173215`. Este índice reemplaza la versión del 2026-09-17, que
describía la ejecución científica como pendiente. Esa lectura quedó superada.

## Estado vigente

- Campaña `controlled_daily_v4` de Pergamino: A, B, C y H ejecutadas, no se
  repiten. B y C son evidencia retrospectiva exploratoria. Estado canónico en la
  cabecera de
  [current-execution-checkpoint.md](../../openspec/scientific-closure/current-execution-checkpoint.md)
  y en [la síntesis canónica](scientific-closure-synthesis-2026-09-22.md).
- CICYTEX: evaluación inicial y replay causal del ensamble, archivados en
  `results/cicytex/`. Fuera del alcance del checkpoint v4.
- Síntesis para memoria y defensa:
  [thesis-defense-position.md](thesis-defense-position.md).

Estados distintos: diseñado, implementado, probado con fixtures, integrado,
ejecutado y evidencia consolidada no son equivalentes. Que las pruebas pasen no
atribuye mejora científica.

## Qué documento usar

### Defensa y memoria

| Necesidad | Documento |
| --- | --- |
| Qué se puede afirmar, matriz de evidencias, preguntas del tribunal | [thesis-defense-position.md](thesis-defense-position.md) |
| Guion y arranque de la demo | [demo-guion-defensa](../design/demo-guion-defensa.md), [defense-demo-startup-guide](../design/defense-demo-startup-guide.md), [f8-paquete-defensa](../design/f8-paquete-defensa.md) |

### Metodología

| Necesidad | Documento |
| --- | --- |
| Protocolo v3 (congelado) | [protocolo-experimental-v3.md](protocolo-experimental-v3.md) |
| Protocolo v4 y manifiesto | [protocolo](controlled-daily-v4-external-pergamino-protocol.md), [manifiesto](controlled-daily-v4-external-pergamino-manifest.yaml) |
| Decisiones previas a la ejecución | [scientific-closure-decisions.md](scientific-closure-decisions.md) |
| Protocolo de la evaluación retrospectiva del ensamble | [ensemble-retrospective-evaluation-protocol.md](ensemble-retrospective-evaluation-protocol.md) |
| Diseño de CICYTEX | [cicytex-external-validation-report.md](cicytex-external-validation-report.md), [cicytex-causal-ensemble-replay.md](cicytex-causal-ensemble-replay.md) |

### Implementación

| Necesidad | Documento |
| --- | --- |
| Decisiones de arquitectura | [docs/adr](../adr/), incluido ADR-0014 (multisitio y Laya) |
| Reproducir CICYTEX | [cicytex-reproduction.md](cicytex-reproduction.md) |
| Guía operativa de cierre | [scientific-closure-runbook.md](scientific-closure-runbook.md) |

### Resultados

| Análisis | Documento | Datos |
| --- | --- | --- |
| Melchor Romero v3 | [reference-v3-formal-table.md](reference-v3-formal-table.md) | [reference-v3-formal-results.json](reference-v3-formal-results.json) |
| Pergamino A/B/C/H | [scientific-closure-synthesis-2026-09-22.md](scientific-closure-synthesis-2026-09-22.md) | |
| Pergamino, ensamble retrospectivo 2023 | [ensemble-retrospective-evaluation-results.md](ensemble-retrospective-evaluation-results.md) | [tables/ensemble-retrospective-2023](tables/ensemble-retrospective-2023) |
| CICYTEX, evaluación inicial | [cicytex-external-validation-report.md](cicytex-external-validation-report.md) | [summary.json](../../results/cicytex/summary.json) |
| CICYTEX, replay causal | [cicytex-causal-ensemble-replay-report.md](cicytex-causal-ensemble-replay-report.md) | [metrics.csv](../../results/cicytex/causal_replay/metrics.csv), [summary.json](../../results/cicytex/causal_replay/summary.json) |

Los análisis de CICYTEX tienen denominadores, modelos seleccionados y métricas
propios. No deben combinarse en una sola tabla.

### Fundamentación (HU1 a HU8)

Los documentos `hu1-*` a `hu8-*` y las auditorías de revalidación son registros
de cada historia de usuario. Para resultados y discusión de HU8 véase
[hu8-resultados-discusion-conclusiones.md](hu8-resultados-discusion-conclusiones.md).

## Notas de alcance sobre documentos históricos

Estos documentos se conservan sin cambios. Su fecha y su título describen el
momento en que se redactaron.

- `controlled-daily-v4-stage-b-c-decisiones-pendientes.md`, el runbook, la
  [auditoría de preejecución](scientific-closure-preexecution-audit.md) y la
  [síntesis del 2026-09-20](scientific-closure-synthesis-2026-09-20.md):
  anteriores a la ejecución. Las menciones a «B/C no implementadas» o a
  ejecución pendiente quedan reemplazadas por el estado vigente de este índice.
- `protocolo-experimental-v3.md`, `reference-v3-formal-table.md` y
  `reference-v3-formal-results.json`: evidencia v3 congelada. No es una réplica
  directa de v4 ni de CICYTEX.
- [ensemble-retrospective-evaluation-results.md](ensemble-retrospective-evaluation-results.md):
  conserva la desviación de doble ejecución y su veredicto `FAIL` de gobernanza.
- `cicytex-external-validation-report.md` y
  `cicytex-causal-ensemble-replay-report.md`: resultados archivados de CICYTEX.
  El objetivo es un proxy estadístico, el replay recorre un período ya
  inspeccionado y no hay etiquetas fisiológicas independientes. Ninguno
  subsana los incumplimientos de gobernanza de Pergamino.
- Las secciones del checkpoint posteriores a su cabecera son registro histórico.
