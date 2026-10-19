# F7 — Verificación en navegador real de los recorridos de la UI (CICYTEX, Pergamino, Melchor Romero, laboratorio y Laya)

Alcance de las secciones históricas más abajo: recorrido `#defensa-cicytex` (primera versión, PR #54). El alcance actual
está en la sección siguiente (PR #62). Las pruebas de componente (vitest) no sustituyen esta verificación; esta
tampoco es una auditoría de accesibilidad automatizada (decisión: sin dependencias nuevas, sin Playwright ni axe).

## Alcance actual del script (extensión multi-sitio, integrada en CI)

`scripts/ui/verify-journeys.mjs` recorre en Chrome real (CDP, Node ≥ 22, sin dependencias nuevas) cinco pantallas contra el build del
frontend y un servidor de fixtures determinista (`scripts/ui/fixture-server.mjs`, respuestas grabadas del backend real; ver
`frontend/e2e/fixtures/README.md`). Es verificación de navegador, no pruebas de componente ni auditoría de accesibilidad.

| Sitio (ruta) | Chequeos (PASS/FAIL) |
|--------------|----------------------|
| Melchor Romero (`#defensa-melchor-romero`) y Pergamino (`#defensa-pergamino`), 17 c/u en #62; 18 c/u con #67 (se añaden M4b/P4b) | veredicto y acuerdo visibles; realidad futura oculta; trazabilidad con «no disponible»; acción primaria/secundaria; «Día siguiente» mueve el reloj y no revela filas ni objetivos posteriores; retroceder re-oculta; backend desconectado (error `role=alert`, sin decisión vigente) y recuperación con «Reintentar»; evidencia declarada del sitio; Tab sin trampa con foco visible |
| CICYTEX (`#defensa-cicytex`), 26 | lo anterior de J0–J7 y además: trazabilidad (SHA-256 y «no disponible»), observado oculto, gráfico sin futuro, feedback sin preselección, J6 pasa de INFO a chequeo: recarga con sesión restaurada y recarga con el servidor en 404 (explicación, sin sesión fantasma, foco en «Abrir emisión») |
| Laboratorio (`#laboratorio-sensores`), 12 | simulación declarada; orden A→B→C→D; backend desconectado en A (error, sin avance) y recuperación con sesión nueva; A (120 lecturas) y B (anomalía de medición, no alerta); Tab |
| Arquitectura (`#arquitectura`), 6 + 1 INFO | Laya «Desactivado por defecto», sin acciones; Tab. El INFO lista rutas de API sin fixture (hoy `GET /api/v2/sectors` y `/api/v2/sensors`, 404 inocuos) |

Total: 78 PASS, 0 FAIL y 1 INFO en #62 (17+17+26+12+6); con #67 son 80 PASS, 0 FAIL y 1 INFO (18+18+26+12+6) por M4b/P4b y la fixture de procedencia.

Salidas en `OUT_DIR` (por defecto un directorio temporal): `<sitio>.json` y `summary.json` (sólo PASS/FAIL/INFO y texto: dos corridas dan
archivos idénticos), `*-orden-de-foco.json` y capturas `*.png` (las capturas no se comparan). Portabilidad: `CHROME_PATH` o detección
(Windows, Linux, macOS), perfil en `os.tmpdir()`, `--no-sandbox` con `CI=true`, `BASE_URL`.

Reproducir (local o CI): `cd frontend && VITE_API_BASE_URL= npm run build -- --outDir dist/e2e --emptyOutDir`, luego
`PORT=4173 node scripts/ui/fixture-server.mjs &` y `BASE_URL=http://127.0.0.1:4173 OUT_DIR=ui-journeys-out node scripts/ui/verify-journeys.mjs`.
El job `browser-journeys` de `.github/workflows/ci.yml` hace lo mismo en `ubuntu-latest` y sube `OUT_DIR` como artefacto.
Pruebas de los helpers puros: `node --test "scripts/ui/**/*.test.mjs"`.

No cubre: otros ejes de accesibilidad (lectores de pantalla, zoom, contraste medido), segmentos internos de `input type=date` (cuentan como
una parada y se juzga su primer foco), revisiones humanas de Pergamino/Melchor (POST), escenarios C/D del laboratorio, ni el backend real
(las fixtures fijan el contrato grabado: un cambio de contrato exige regrabar). Los chequeos fallan con mutaciones del frontend o de las
fixtures (ver `openspec/changes/extend-browser-journeys-ci/tasks.md`).

> Las secciones siguientes describen la primera versión del script (sólo CICYTEX, ejecución manual con proxy a un backend real) y se
> conservan como historial; el hallazgo J6 ya no aplica: la recuperación de sesión existe y se verifica.

## Cómo reproducir (primera versión, manual)

1. Backend con el paquete causal: `PYTHONPATH="src;backend;." python -m uvicorn backend.app.main:app --port 8010`
   (opcional `CICYTEX_REPLAY_SESSION_DB=<ruta>.sqlite` para no tocar la base por defecto).
2. Frontend con proxy de `/api`: `cd frontend && npx vite --config vite.verify.config.mjs` (puerto 5199, sólo `localhost`).
3. `BASE_URL=http://localhost:5199 node scripts/ui/verify-journeys.mjs` (Node ≥ 22, Chrome en Windows).

Salidas (primera versión): `docs/design/capturas/f7-verificacion-navegador.json`, `f7-orden-de-foco.json` y tres capturas `f7-cicytex-*.png`.

## Qué comprueba (primera versión: 12 chequeos PASS y 1 informativo, J6, sin fallo en esa corrida; superada por la corrida de #62)

| Id | Comprobación | Resultado |
|----|--------------|-----------|
| J0–J2b | Catálogo carga; sin sesión no hay «Día siguiente» ni feedback; abrir emisión muestra la decisión; el feedback no existe mientras la realidad está oculta | PASS |
| J3, J3b | Sin red (emulada por CDP) aparece un `role=alert` y el botón vuelve a quedar habilitado | PASS |
| J4 | Al volver la red el reloj avanza (2023-07-06 → 2023-07-07) y el error desaparece | PASS |
| J5 | Al revelar la realidad se habilita el formulario de feedback | PASS |
| J6 | Recarga: se registra qué persiste (ruta, sesión visible, selección) | INFO en la primera versión; en #62 pasó a chequeos (C7, C10, C10b) |
| J6b | Recarga: la ruta se conserva | PASS |
| J7, J7b, J7c | Foco por teclado: 7 paradas distintas sin trampa, todas con indicador de foco, selectores antes de «Abrir» | PASS |

## Hallazgo histórico (resuelto en #59 y verificado en #62)

**J6 (INFO, primera versión):** tras recargar se conservaba la ruta pero la sesión no se reabría. El PR #59 agregó la
recuperación por `sessionStorage` (`cicytex-defense-session`) más `GET /sessions/{id}`; el script de #62 la verifica con el reloj
restaurado (C7) y con el servidor en 404 (C10, C10b). Si falla la recuperación (por ejemplo 404, registro mal formado o sesión que
no coincide) se muestra el aviso y se borra la referencia; el script sólo ejercita el caso 404. La recuperación es por pestaña.

## Lo que no cubre (primera versión; vigente sólo lo no superado por la sección de alcance actual)

- Otros sitios: en la primera versión sólo CICYTEX; desde #62 el script cubre los cuatro sitios y la ficha de Laya (ver arriba).
- Tab con la sesión abierta: en la primera versión sólo se medía la carga inicial (7 paradas); desde #62 se mide también con la sesión abierta (C8, L8).
- Lectores de pantalla, zoom y contraste en el navegador (el contraste se calculó por valores de color, no medido en pantalla).
- En la primera versión no corría en CI; desde #62 corre en el job `browser-journeys` con fixtures.
