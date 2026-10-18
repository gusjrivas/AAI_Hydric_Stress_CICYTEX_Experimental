# F7 — Verificación en navegador real del recorrido CICYTEX

Alcance: recorrido `#defensa-cicytex`. Las pruebas de componente (vitest) no sustituyen esta verificación; esta
tampoco es una auditoría de accesibilidad automatizada (decisión: sin dependencias nuevas, sin Playwright ni axe).

## Cómo reproducir

1. Backend con el paquete causal: `PYTHONPATH="src;backend;." python -m uvicorn backend.app.main:app --port 8010`
   (opcional `CICYTEX_REPLAY_SESSION_DB=<ruta>.sqlite` para no tocar la base por defecto).
2. Frontend con proxy de `/api`: `cd frontend && npx vite --config vite.verify.config.mjs` (puerto 5199, sólo `localhost`).
3. `BASE_URL=http://localhost:5199 node scripts/ui/verify-journeys.mjs` (Node ≥ 22, Chrome en Windows).

Salidas: `docs/design/capturas/f7-verificacion-navegador.json`, `f7-orden-de-foco.json` y tres capturas `f7-cicytex-*.png`.

## Qué comprueba (12 chequeos PASS y 1 informativo, J6, sin fallo en la última corrida)

| Id | Comprobación | Resultado |
|----|--------------|-----------|
| J0–J2b | Catálogo carga; sin sesión no hay «Día siguiente» ni feedback; abrir emisión muestra la decisión; el feedback no existe mientras la realidad está oculta | PASS |
| J3, J3b | Sin red (emulada por CDP) aparece un `role=alert` y el botón vuelve a quedar habilitado | PASS |
| J4 | Al volver la red el reloj avanza (2023-07-06 → 2023-07-07) y el error desaparece | PASS |
| J5 | Al revelar la realidad se habilita el formulario de feedback | PASS |
| J6 | Recarga: se registra qué persiste (ruta, sesión visible, selección) | INFO (observación, no cuenta como PASS) |
| J6b | Recarga: la ruta se conserva | PASS |
| J7, J7b, J7c | Foco por teclado: 7 paradas distintas sin trampa, todas con indicador de foco, selectores antes de «Abrir» | PASS |

## Hallazgo declarado (no es un fallo del chequeo)

**J6 (INFO):** tras recargar se conserva la ruta, pero la sesión abierta **no se reabre**: la selección vuelve a los valores
por defecto y hay que abrir de nuevo la emisión. El estado de la sesión vive en el servidor, pero la interfaz no lo rehidrata.
Se registra como limitación para F8; cambiarlo sería una ampliación de alcance que no se hizo.

## Lo que no cubre

- Otros sitios (Pergamino, Melchor Romero, laboratorio): verificados sólo por pruebas de componente y de resiliencia.
- Tab con la sesión abierta (el recorrido de foco se mide en la carga inicial, 7 paradas).
- Lectores de pantalla, zoom y contraste en el navegador (el contraste se calculó por valores de color, no medido en pantalla).
- No corre en CI: es un script manual reproducible.
