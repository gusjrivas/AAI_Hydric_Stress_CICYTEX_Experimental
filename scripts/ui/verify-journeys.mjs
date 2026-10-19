// Uso: BASE_URL=http://127.0.0.1:4173 OUT_DIR=ui-journeys-out node scripts/ui/verify-journeys.mjs
// Verificación en NAVEGADOR REAL (Chrome headless por CDP, Node >= 22, sin dependencias) de cinco recorridos:
// Melchor Romero, Pergamino, CICYTEX, Laboratorio de sensores y la ficha de Laya en #arquitectura.
// Requiere el servidor de fixtures (scripts/ui/fixture-server.mjs) sirviendo el build del frontend; ver
// docs/design/f7-verificacion-navegador.md. No es una auditoría de accesibilidad automatizada ni una prueba de componentes:
// comprueba lo que declara cada chequeo y nada más. Variables: BASE_URL, OUT_DIR (o argv[2]), CHROME_PATH, CI.
import { mkdirSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { launchBrowser, sleep } from "./lib/cdp.mjs";
import { classifyUnmatched, createRecorder, summarize } from "./lib/results.mjs";
import { fetchWithTimeout } from "./lib/timeout.mjs";
import { analyzeTabStops } from "./lib/tab-audit.mjs";

const base = (process.env.BASE_URL ?? "http://127.0.0.1:4173").replace(/\/$/, "");
const outDir = process.env.OUT_DIR ?? process.argv[2] ?? join(tmpdir(), "ui-journeys");
mkdirSync(outDir, { recursive: true });

const fixture = async (path, body) => {
  const response = await fetchWithTimeout(`${base}/__fixture/${path}`, {
    method: body === undefined ? "GET" : "POST",
    headers: { "content-type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok) throw new Error(`control de fixtures ${path}: HTTP ${response.status}`);
  return response.json();
};
const setMode = (mode) => fixture("mode", { mode });

const browser = await launchBrowser();
const { evaluate, waitFor, press, shot } = browser;
const q = JSON.stringify;

// ---------- utilidades de página ----------
const clickText = (text) =>
  evaluate(
    `(() => { const b=[...document.querySelectorAll('button,a,summary')].find(x=>x.textContent.trim().startsWith(${q(text)})&&!x.disabled&&x.getAttribute('aria-disabled')!=='true'); if(b) b.click(); return !!b; })()`,
  );
const hasText = (text) => `document.body.innerText.toLowerCase().includes(${q(text.toLowerCase())})`;
const buttonState = (text) =>
  evaluate(
    `(() => { const b=[...document.querySelectorAll('button')].find(x=>x.textContent.trim().startsWith(${q(text)})); return b ? (b.disabled ? 'disabled' : 'enabled') : 'absent'; })()`,
  );
const alerts = () => evaluate(`[...document.querySelectorAll('[role=alert]')].map(e=>e.textContent.trim())`);
const fmtDate = (iso) =>
  evaluate(`new Intl.DateTimeFormat('es-AR',{day:'numeric',month:'short',year:'numeric',timeZone:'UTC'}).format(new Date(${q(iso)}+'T00:00:00Z'))`);
const addDays = (iso, n) => {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, d + n)).toISOString().slice(0, 10);
};
async function openFresh(route) {
  await fixture("reset", {});
  await browser.open(`${base}/`);
  await evaluate(`try { sessionStorage.clear(); localStorage.clear(); } catch {}`);
  await browser.open(`${base}/#${route}`);
}

/** Recorre la página con Tab: paradas distintas (por identidad de elemento), sin trampa (sale o completa la vuelta) y foco visible. */
async function tabAudit(rec, id, label, { max = 120, minStops = 6, outFile } = {}) {
  await evaluate(`document.activeElement && document.activeElement.blur(); window.scrollTo(0,0); window.__tabSeq = window.__tabSeq || 0;`);
  const probe = () =>
    evaluate(
`(() => { const e=document.activeElement; if(!e||e===document.body) return null; if(!e.__tabId) e.__tabId=++window.__tabSeq; const cs=getComputedStyle(e); const r=e.getBoundingClientRect(); return {id:e.__tabId, tag:e.tagName.toLowerCase(), text:(e.textContent||e.value||e.getAttribute('aria-label')||'').trim().replace(/\\s+/g,' ').slice(0,48), outline:cs.outlineStyle!=='none'&&parseFloat(cs.outlineWidth)>0, shadow:cs.boxShadow!=='none', visible:r.width>0&&r.height>0}; })()`,
    );
  const raw = [];
  let left = false;
  // Chrome retoma Tab desde el último elemento pulsado: enfocar el <body> (tabindex temporal) reinicia el punto de partida.
  await evaluate(`(() => { const b = document.body; b.setAttribute('tabindex', '-1'); b.focus(); b.removeAttribute('tabindex'); window.scrollTo(0, 0); })()`);
  for (let i = 0; i < max; i++) {
    await press("Tab", "Tab", 9);
    const info = await probe();
    if (!info) {
      left = true;
      break;
    }
    if (raw.length > 0 && info.id === raw[0].id) break; // vuelta completa al primer elemento
    raw.push(info);
  }
  const { stops, ended, trapped, withoutIndicator } = analyzeTabStops(raw, { max, left });
  rec.check(id, `${label}: el foco recorre elementos distintos y no queda atrapado`, !trapped && stops.length >= minStops, `termina: ${ended === "left" ? "sale de la página" : ended === "wrapped" ? "vuelve al primer elemento" : "sin fin"}`);
  rec.check(`${id}b`, `${label}: todo elemento enfocado muestra indicador de foco`, withoutIndicator.length === 0, withoutIndicator.map((s) => `${s.tag}:${s.text}`).join(" | "));
  if (outFile) writeFileSync(join(outDir, outFile), JSON.stringify(stops.map(({ id: _id, ...rest }) => ({ ...rest, text: rest.text.replace(/lab-[0-9a-f]{10}/g, 'lab-<id>') })), null, 2));
  return stops;
}

// ---------- Melchor Romero y Pergamino (historial persistido) ----------
const PRODUCER_SITES = [
  { key: "melchor-romero", prefix: "M", route: "defensa-melchor-romero", name: "Melchor Romero", d0: "2024-10-20", source: "ESA CCI" },
  { key: "pergamino", prefix: "P", route: "defensa-pergamino", name: "Pergamino", d0: "2023-06-13", source: "ERA5-Land" },
];
const VERDICT = `!!document.querySelector('[aria-label="Veredicto del ensamble"]')`;

async function producerSite(cfg) {
  const rec = createRecorder(cfg.key);
  const p = cfg.prefix;
  await openFresh(cfg.route);
  const loaded = await waitFor(VERDICT);
  rec.check(`${p}0`, "carga con datos: aparece el veredicto del ensamble", loaded);
  if (!loaded) return rec;
  rec.check(
    `${p}1`,
    "título y localidad activa",
    (await evaluate(`document.querySelector('h1')?.textContent.trim()`)) === cfg.name &&
      (await evaluate(`document.querySelector('.site-switch [aria-current=page]')?.textContent.trim()`)) === cfg.name,
  );

  const verdict = await evaluate(`document.querySelector('.historical-verdict-label')?.textContent.trim()`);
  rec.check(`${p}2`, "decisión visible y acuerdo entre modelos declarado", /^(ALERTA|SIN ALERTA) DE HUMEDAD BAJA$/.test(verdict ?? "") && (await evaluate(hasText("Acuerdo entre modelos:"))), verdict);
  rec.check(`${p}3`, "la realidad futura permanece oculta al emitir", await evaluate(`/todavía no disponible según el reloj/i.test(document.querySelector('.historical-verdict-reality')?.textContent||'')`));
  const trace = await evaluate(`document.querySelector('.historical-trace')?.innerText ?? ''`);
  const missing = ["SHA-256 del dataset: no disponible", "Commit: no disponible", "Semilla: no disponible", "Corridas de MLflow: no disponible", "Linaje de recalibración: no disponible"].filter((t) => !trace.includes(t));
  rec.check(
    `${p}4`,
    "trazabilidad: modelo, identidad SHA-256 y «no disponible» para lo que el backend no expone",
    /Identidad del ensamble \(SHA-256\): [0-9a-f]{64}/.test(trace) && trace.includes("Versión del modelo:") && trace.includes(cfg.source) && missing.length === 0,
    missing.join(" | "),
  );
  rec.check(`${p}5`, "procedencia y calidad: la falta de datos no se lee como ausencia de alerta", await evaluate(hasText("Una fecha o variable faltante no se interpreta como ausencia de alerta.")));
  rec.check(
    `${p}6`,
    "acción primaria habilitada y secundaria deshabilitada al inicio",
    (await buttonState("Día siguiente")) === "enabled" &&
      (await buttonState("‹ Día anterior")) === "disabled" &&
      (await evaluate(`!!document.querySelector('.historical-step-primary') && !!document.querySelector('.historical-step-secondary')`)),
  );
  await shot(outDir, `${cfg.key}-inicial`);

  // Avanzar un día: se revela sólo hasta el reloj.
  const d1 = addDays(cfg.d0, 1);
  const d1Label = await fmtDate(d1);
  await clickText("Día siguiente");
  const advanced = await waitFor(`document.querySelector('.historical-walkthrough-clock')?.textContent.includes(${q(d1Label)})`);
  await waitFor(`${VERDICT} && !document.querySelector('.historical-walkthrough-observations')?.innerText.includes('Cargando')`);
  rec.check(`${p}7`, "«Día siguiente» mueve el reloj un día", advanced, `reloj ${cfg.d0} → ${d1}`);
  const futureLabels = await Promise.all([1, 2, 3].map((n) => fmtDate(addDays(d1, n))));
  const allowed = await Promise.all([0, 1, 2, 3, 4, 5, 6, 7, 8, 9].map((n) => fmtDate(addDays(d1, -n))));
  const rows = await evaluate(`[...document.querySelectorAll('.historical-walkthrough-observations tbody th')].map(e=>e.textContent.trim())`);
  rec.check(
    `${p}8`,
    "observaciones: ninguna fila posterior al reloj y la última es la del reloj",
    rows.length > 0 && rows.every((r) => allowed.includes(r)) && !rows.some((r) => futureLabels.includes(r)) && rows[rows.length - 1] === d1Label,
    `${rows.length} filas`,
  );
  const pending = await evaluate(`[...document.querySelectorAll('.historical-target-observation')].filter(e=>/todavía no disponible según el reloj/i.test(e.textContent)).length`);
  const expectedPending = [1, 2, 3].filter((h) => addDays(cfg.d0, h) > d1).length;
  rec.check(`${p}9`, "los objetivos posteriores al reloj siguen ocultos tras avanzar", pending === expectedPending && expectedPending === 2, `${pending} ocultos de 3 (esperados ${expectedPending})`);
  await shot(outDir, `${cfg.key}-avanzado`);

  await clickText("‹ Día anterior");
  await waitFor(`document.querySelector('.historical-walkthrough-clock')?.textContent.includes(${q(await fmtDate(cfg.d0))})`);
  await waitFor(VERDICT);
  rec.check(`${p}10`, "retroceder vuelve a ocultar el futuro", await evaluate(`/todavía no disponible según el reloj/i.test(document.querySelector('.historical-verdict-reality')?.textContent||'')`));

  // Backend desconectado y recuperación.
  await setMode("disconnected");
  await clickText("Día siguiente");
  const errored = await waitFor(`document.querySelectorAll('[role=alert]').length >= 1 && document.body.innerText.includes('Reintentar')`, 8000);
  const errTexts = await alerts();
  rec.check(`${p}11`, "sin backend aparece un mensaje de error (role=alert) con «Reintentar»", errored && errTexts.some((t) => t.startsWith("No se pudo")), errTexts[0] ?? "");
  rec.check(`${p}12`, "sin backend no queda una decisión vigente en pantalla", !(await evaluate(VERDICT)));
  await shot(outDir, `${cfg.key}-sin-conexion`);
  await setMode("normal");
  await clickText("Reintentar emisión");
  await clickText("Reintentar lecturas");
  const recovered = await waitFor(`${VERDICT} && document.querySelectorAll('[role=alert]').length === 0`, 10000);
  rec.check(`${p}13`, "al volver el backend y reintentar, la decisión reaparece y el error desaparece", recovered && (await evaluate(`document.querySelector('.historical-walkthrough-clock')?.textContent.includes(${q(d1Label)})`)), `reloj conservado en ${d1}`);

  // Evidencia declarada del sitio.
  if (cfg.key === "melchor-romero") {
    rec.check(`${p}14`, "sin evaluación agregada propia: no se le atribuyen resultados de otro sitio", (await evaluate(hasText("Sin evaluación agregada equivalente."))) && (await evaluate(hasText("no se le atribuyen los resultados de Pergamino"))));
  } else {
    rec.check(`${p}14`, "la evidencia agregada se declara exploratoria y no independiente", await evaluate(hasText("exploratoria y no independiente")));
  }
  await tabAudit(rec, `${p}15`, "teclado con datos cargados", { outFile: `${cfg.key}-orden-de-foco.json`, minStops: 8 });
  return rec;
}

// ---------- CICYTEX ----------
async function cicytexSite() {
  const rec = createRecorder("cicytex");
  const openReady = `!![...document.querySelectorAll('button')].find(b=>b.textContent.startsWith('Abrir emisión congelada')&&!b.disabled)`;
  const CLOCK = String.raw`(document.body.innerText.match(/reloj revelado\s*([0-9-]+)/i) || [])[1] || ''`;
  const clock = () => evaluate(CLOCK);
  await openFresh("defensa-cicytex");
  rec.check("C0", "catálogo cargado en navegador real", await waitFor(openReady));
  rec.check("C1", "sin sesión no hay «Día siguiente» ni feedback", (await buttonState("Día siguiente")) === "absent" && (await buttonState("Registrar feedback")) === "absent");
  const startStops = await tabAudit(rec, "C2", "teclado al cargar", { outFile: "cicytex-orden-de-foco.json", minStops: 6 });
  const idxSensor = startStops.findIndex((s) => s.tag === "select");
  const idxOpen = startStops.findIndex((s) => s.text.startsWith("Abrir emisión congelada"));
  rec.check("C2c", "los selectores se alcanzan antes que «Abrir»", idxSensor >= 0 && idxOpen > idxSensor, `select@${idxSensor}, abrir@${idxOpen}`);

  await clickText("Abrir emisión congelada");
  rec.check("C3", "abrir la emisión muestra la decisión de la arquitectura", await waitFor(hasText("Decisión de la arquitectura")));
  rec.check("C3b", "la realidad futura permanece oculta y no hay feedback", (await evaluate(hasText("La realidad permanece oculta"))) && (await buttonState("Registrar feedback")) === "absent");
  await clickText("Identidad del paquete y de los modelos");
  const cyTrace = await evaluate(`document.querySelector('.cy-trace')?.innerText ?? ''`);
  rec.check("C3c", "trazabilidad: identidad SHA-256 del dataset y «no disponible» para lo que no existe", /Dataset \(SHA-256\)\s*[0-9a-f]{64}/.test(cyTrace) && cyTrace.includes("Versión del modelo: no disponible") && cyTrace.includes("Linaje de recalibración: no disponible"));
  const hiddenCells = await evaluate(`[...document.querySelectorAll('.cy-panel tbody tr')].filter(tr=>tr.querySelectorAll('td').length===4).every(tr => /Oculto hasta avanzar/.test(tr.innerText) && /Pendiente/.test(tr.innerText))`);
  rec.check("C3d", "ningún método muestra el observado futuro antes de avanzar", hiddenCells);
  rec.check("C3e", "acción primaria «Día siguiente» habilitada y secundaria «Reiniciar»", (await buttonState("Día siguiente")) === "enabled" && (await evaluate(`!!document.querySelector('.cy-primary') && !!document.querySelector('.cy-secondary')`)));
  await shot(outDir, "cicytex-sesion-abierta");

  // Desconexión y recuperación.
  const before = await clock();
  await setMode("disconnected");
  await clickText("Día siguiente");
  rec.check("C4", "sin backend aparece un mensaje de error (role=alert)", await waitFor(`!!document.querySelector('[role=alert]')`, 8000), (await alerts())[0] ?? "");
  rec.check("C4b", "tras el error «Día siguiente» vuelve a estar habilitado y el reloj no cambió", (await buttonState("Día siguiente")) === "enabled" && (await clock()) === before);
  await shot(outDir, "cicytex-sin-conexion");
  await setMode("normal");
  await clickText("Día siguiente");
  const advanced = await waitFor(`(${CLOCK}) !== ${q(before)}`);
  const after = await clock();
  rec.check("C5", "al volver el backend el reloj avanza y el error desaparece", advanced && !(await evaluate(`!!document.querySelector('[role=alert]')`)), `reloj ${before} → ${after}`);
  rec.check("C5b", "tras avanzar se revela el objetivo y se muestra el resultado", await waitFor(hasText("Realidad revelada")));
  const lastObs = await evaluate(`(document.querySelector('[data-testid=moisture-summary]')?.textContent.match(/\\((\\d{4}-\\d{2}-\\d{2})\\)/)||[])[1]||''`);
  rec.check("C5c", "el gráfico no dibuja observaciones posteriores al reloj", lastObs !== "" && lastObs <= after, `última ${lastObs}, reloj ${after}`);

  // Feedback sin preselección.
  rec.check("C6", "el formulario de feedback aparece con la realidad revelada", (await buttonState("Registrar feedback")) !== "absent");
  rec.check(
    "C6b",
    "feedback sin preselección: ninguna opción marcada y registrar deshabilitado",
    (await evaluate(`[...document.querySelectorAll('input[name=cicytex-feedback]')].every(r=>!r.checked) && document.querySelectorAll('input[name=cicytex-feedback]').length===2`)) && (await buttonState("Registrar feedback")) === "disabled",
  );
  await evaluate(`document.querySelectorAll('input[name=cicytex-feedback]')[0].click()`);
  rec.check("C6c", "elegir una opción habilita «Registrar feedback»", (await buttonState("Registrar feedback")) === "enabled");
  await shot(outDir, "cicytex-realidad-revelada");

  // Recarga: sesión restaurada.
  await browser.send("Page.reload");
  const restored = await waitFor(hasText("Decisión de la arquitectura"), 15000);
  rec.check("C7", "recarga: la sesión se restaura con el mismo reloj", restored && (await clock()) === after, `reloj ${await clock()}`);
  rec.check("C7b", "recarga: la ruta se conserva y el borrador de feedback no se restaura", (await evaluate("location.hash")) === "#defensa-cicytex" && (await evaluate(`[...document.querySelectorAll('input[name=cicytex-feedback]')].every(r=>!r.checked)`)));
  await tabAudit(rec, "C8", "teclado con la sesión abierta", { minStops: 12 });

  // Registrar feedback explícito.
  await evaluate(`document.querySelectorAll('input[name=cicytex-feedback]')[1].click()`);
  await clickText("Registrar feedback");
  rec.check("C9", "el feedback registrado se confirma con el estado elegido", await waitFor(hasText("Feedback registrado: rechazada")));

  // Recarga con el servidor sin la sesión (404).
  await setMode("session-404");
  await browser.send("Page.reload");
  const notice = await waitFor(`[...document.querySelectorAll('[role=alert]')].some(e=>e.textContent.includes('No se pudo recuperar la sesión anterior'))`, 15000);
  rec.check("C10", "recarga con 404: se explica que no se pudo recuperar la sesión", notice, (await alerts())[0] ?? "");
  rec.check("C10b", "con 404 no queda una sesión fantasma en pantalla y se ofrece «Iniciar otra emisión»", !(await evaluate(hasText("Decisión de la arquitectura"))) && (await evaluate(`!![...document.querySelectorAll('button')].find(b=>b.textContent.trim()==='Iniciar otra emisión')`)));
  await shot(outDir, "cicytex-sesion-no-recuperable");
  await clickText("Iniciar otra emisión");
  rec.check("C10c", "«Iniciar otra emisión» cierra el aviso y deja el foco en «Abrir emisión congelada»", (await evaluate(`document.activeElement?.textContent.trim()`)) === "Abrir emisión congelada" && !(await evaluate(`!![...document.querySelectorAll('[role=alert]')].find(e=>e.textContent.includes('No se pudo recuperar'))`)));
  await setMode("normal");
  return rec;
}

// ---------- Laboratorio de sensores ----------
async function labSite() {
  const rec = createRecorder("laboratorio");
  await openFresh("laboratorio-sensores");
  rec.check("L0", "carga el laboratorio", await waitFor(`document.querySelector('h1')?.textContent.includes('Laboratorio de sensor simulado')`));
  rec.check("L1", "se declara simulación y sin sensor físico", (await evaluate(`document.querySelector('.sl-badge')?.textContent.includes('SIMULACIÓN')`)) && (await evaluate(hasText("Sin sensor físico conectado"))) && (await evaluate(hasText("no prueban precisión en campo"))));
  rec.check("L2", "al inicio sólo el paso A está habilitado (orden A→B→C→D)", (await buttonState("A — Generar historial")) === "enabled" && (await buttonState("B — Introducir")) === "disabled" && (await buttonState("C — Simular una interrupción")) === "disabled" && (await buttonState("D — Simular la recuperación")) === "disabled");
  await tabAudit(rec, "L3", "teclado al cargar", { outFile: "laboratorio-orden-de-foco.json", minStops: 8 });

  // Backend desconectado durante el escenario A y recuperación con sesión nueva.
  await setMode("disconnected");
  await clickText("A — Generar historial");
  rec.check("L4", "sin backend el paso A muestra un error (role=alert) y no deja avanzar", (await waitFor(`!!document.querySelector('.sl-error[role=alert]')`, 10000)) && (await buttonState("B — Introducir")) === "disabled", (await alerts())[0] ?? "");
  await shot(outDir, "laboratorio-sin-conexion");
  await setMode("normal");
  await clickText("Iniciar una sesión nueva");
  rec.check("L5", "tras «Iniciar una sesión nueva» el error desaparece y A vuelve a estar habilitado", (await waitFor(`!document.querySelector('.sl-error[role=alert]')`)) && (await buttonState("A — Generar historial")) === "enabled");

  await clickText("A — Generar historial");
  const doneA = await waitFor(hasText("Historial sintético cargado: 120 lecturas normales"), 30000);
  rec.check("L6", "escenario A: 120 lecturas sintéticas confirmadas por la calidad del backend", doneA, (await evaluate(`document.querySelector('.sl-log li')?.textContent.slice(0,50)`)) ?? "");
  rec.check("L6b", "tras A queda habilitado B y A deja de estarlo", (await waitFor(`(() => { const b=[...document.querySelectorAll('button')].find(x=>x.textContent.trim().startsWith('B — Introducir')); return b && !b.disabled; })()`)) && (await buttonState("A — Generar historial")) === "disabled");
  await clickText("B — Introducir");
  rec.check("L7", "escenario B: la anomalía se marca como medición, no como estrés hídrico", (await waitFor(hasText("fuera del rango físico esperado"), 20000)) && (await evaluate(hasText("no una alerta de estrés hídrico"))));
  await waitFor(`(() => { const b=[...document.querySelectorAll('button')].find(x=>x.textContent.trim().startsWith('C — Simular una interrupción')); return b && !b.disabled; })()`, 20000);
  await waitFor(`/Se agregó el pronóstico|Se usó la última fecha/.test(document.body.innerText)`, 20000);
  await shot(outDir, "laboratorio-escenario-b");
  await tabAudit(rec, "L8", "teclado con la sesión en curso", { minStops: 10, outFile: "laboratorio-sesion-orden-de-foco.json" });
  return rec;
}

// ---------- Laya en #arquitectura ----------
async function layaSite() {
  const rec = createRecorder("arquitectura-laya");
  await openFresh("arquitectura");
  rec.check("A0", "carga la arquitectura del sistema", await waitFor(`document.querySelector('h1')?.textContent.length>0 && !!document.querySelector('.af-table')`));
  const row = await evaluate(`(() => { const r=[...document.querySelectorAll('.af-table tbody tr')].find(tr=>tr.querySelector('th')?.textContent.trim()==='Laya'); return r ? [...r.querySelectorAll('td')].map(td=>td.textContent.trim()) : null; })()`);
  rec.check("A1", "la tabla declara a Laya como adaptador consultivo «Desactivado por defecto»", !!row && row[0] === "Adaptador consultivo" && row[1] === "Desactivado por defecto", row ? row.join(" | ").slice(0, 120) : "sin fila");
  await clickText("Laya");
  rec.check("A2", "la ficha de Laya muestra estado desactivado y sin efecto automático", (await waitFor(`!!document.querySelector('[aria-label="Ficha de Laya"]')`)) && (await evaluate(`(() => { const sheet=document.querySelector('[aria-label="Ficha de Laya"]'); const dt=[...sheet.querySelectorAll('dt')].find(x=>x.textContent==='Estado'); return dt?.nextElementSibling?.textContent==='Desactivado por defecto' && /sin efecto autom/i.test(sheet.innerText); })()`)));
  rec.check("A3", "Laya no ofrece ninguna acción: sólo su selector de ficha", (await evaluate(`[...document.querySelectorAll('button,a')].filter(e=>/laya/i.test(e.textContent)).length`)) === 1);
  await tabAudit(rec, "A4", "teclado", { minStops: 8 });
  return rec;
}

// ---------- ejecución ----------
const recorders = [];
let crashed = null;
try {
  for (const run of [() => producerSite(PRODUCER_SITES[0]), () => producerSite(PRODUCER_SITES[1]), cicytexSite, labSite, layaSite]) {
    recorders.push(await run());
  }
  const state = await fixture("state");
  const { known, unknown } = classifyUnmatched(state.unmatched);
  const laya = recorders[recorders.length - 1];
  if (unknown.length) laya.check("A9", "ninguna ruta de API sin fixture fuera de KNOWN_UNMATCHED", false, unknown.join(", "));
  else laya.info("A9", "rutas de API sin fixture durante toda la corrida (solo las conocidas e inocuas)", known.length ? known.join(", ") : "ninguna");
} catch (error) {
  crashed = error;
  console.error(`ERROR en la ejecución: ${error?.stack ?? error}`);
} finally {
  await browser.close();
}

for (const rec of recorders) writeFileSync(join(outDir, `${rec.site}.json`), JSON.stringify({ site: rec.site, results: rec.results }, null, 2));
const summary = summarize(recorders);
writeFileSync(join(outDir, "summary.json"), JSON.stringify({ ...summary, crashed: crashed ? String(crashed.message ?? crashed) : null }, null, 2));
console.log(`\n${summary.pass} PASS, ${summary.fail} FAIL, ${summary.info} INFO — ${summary.sites.map((s) => `${s.site}:${s.pass}/${s.fail}/${s.info}`).join(" ")}`);
await sleep(50);
process.exit(summary.ok && recorders.length === 5 && !crashed ? 0 : 1);
