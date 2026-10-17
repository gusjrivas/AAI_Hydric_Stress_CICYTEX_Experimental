# Diseño F3: experiencia de operación, trazabilidad y arquitectura

HU6/HU7 (presentación) · `alerting-ui`, `architecture-integration` · CRISP-DM Deployment.
Sin impacto sobre hipótesis, datos, modelos, umbrales, política del ensamble ni permisos.

## Decisiones

| Decisión | Resolución |
|---|---|
| Una app, tres lecturas | Las lecturas son agrupaciones de las rutas hash existentes, no apps ni autoridades de datos distintas. |
| Compatibilidad | Todas las rutas actuales (`#productor`, `#defensa-*`, `#laboratorio-sensores`, `#evidencia-resultados`, `#resumen`, `#prediccion`, `#calidad`, `#linaje`, `#evidencia`, `#demo`, `#reproduccion-historica`) siguen resolviendo a la misma vista. |
| Ruta nueva | `#arquitectura` (grupo `arquitectura`): `ArchitectureFlow` evolucionado, fuera del `<details>` colapsado. Es la única ruta añadida. |
| Indicador de modo | Componente `ModeBadge` común, derivado sólo de la ruta: **Operación**, **Replay histórico**, **Laboratorio sintético**, **Documentación de diseño**. No consulta backend y no cambia estado. |
| Cambio de vista | No ejecuta modelos, no borra sesiones, no recalibra. Las acciones mutantes conservan su confirmación y alcance actuales. |
| Lecturas | Operación = `cultivo`, `laboratorio`, `herramientas`. Trazabilidad = `seguimiento` (tres recorridos) y `#linaje`. Arquitectura y defensa = `evidencia`, `arquitectura`. |
| Retiro | Nada se retira en este ciclo; se unifica sólo con equivalencia probada (CICYTEX → componentes compartidos, en F5). |

## Mapa de navegación

```text
Encabezado (un solo <nav>)
 ├─ Operación ........ Mi cultivo · Laboratorio · Herramientas técnicas
 ├─ Trazabilidad ..... Seguimiento histórico (Pergamino · Melchor Romero · CICYTEX) · Linaje
 └─ Arquitectura y defensa ... Evidencia · Arquitectura
Cada pantalla: ModeBadge + una tarea principal + detalle progresivo.
```

## Wireframe de Arquitectura (F6)

```text
[ModeBadge: Documentación de diseño]
Nivel 1: flujo conceptual (7 etapas, lista ordenada con enlaces) 
Nivel 2: ficha del nodo seleccionado (botón, no zoom):
  responsabilidad · entrada/salida · frontera · evidencia (ruta versionada) · límites
Categorías visibles: Diseño documentado | Estado observado | Recorrido guiado
Alternativa textual: la misma lista como tabla accesible.
Laya: adaptador consultivo integrado, desactivado, científicamente BLOCKED.
```

Un mapa estático versionado no es descubrimiento en vivo; ninguna salud, métrica ni traza se simula.

## Estados a especificar por pantalla

Cargando · vacío · sin datos · error con reintento · parcial · madurez pendiente ·
desconectado · desactivado · experimental. Ninguno depende sólo del color (texto/ícono).

## Accesibilidad y responsividad

Foco visible (`--focus-ring` existente), skip-link existente, `aria-current`,
foco al encabezado al cambiar de vista (existente), `prefers-reduced-motion`
respetado, tablas con encabezados, texto alternativo en gráficos, escritorio/proyector
y viewport estrecho. Verificación renderizada en F7.

## Contratos mínimos de componentes

- `modeForRoute(route | "demo" | "reproduccion-historica") -> "operacion" | "replay" | "laboratorio" | "diseno"` (función pura, testeable).
- `ModeBadge({ mode })`: `role="note"`, texto visible.
- Catálogo de arquitectura: datos TypeScript tipados con `evidence` = ruta relativa del repo; prueba de correspondencia contra archivos existentes (F6).

No se requiere backend nuevo en F4–F6.
