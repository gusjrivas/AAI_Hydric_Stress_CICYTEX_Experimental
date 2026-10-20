// Registro de resultados por sitio. Solo PASS/FAIL/INFO y texto: nada con hora, duración ni puertos (corridas comparables).
// Mínimo de chequeos (PASS+FAIL+INFO) por sitio: un sitio que aborta pronto no puede verse igual que uno completo.
export const EXPECTED_MIN_CHECKS = {
  "melchor-romero": 18,
  pergamino: 18,
  cicytex: 26,
  laboratorio: 12,
  "demo-guiada": 23,
  "arquitectura-laya": 7, // 6 chequeos + 1 INFO (A9)
};

// Rutas del panel de resumen sin fixture: el 404 es inocuo y se registra solo como INFO. Cualquier otra ruta sin fixture es FAIL.
export const KNOWN_UNMATCHED = ["GET /api/v2/sectors", "GET /api/v2/sensors"];

export function classifyUnmatched(routes) {
  const unique = [...new Set(routes)].sort();
  return { known: unique.filter((r) => KNOWN_UNMATCHED.includes(r)), unknown: unique.filter((r) => !KNOWN_UNMATCHED.includes(r)) };
}

export function createRecorder(site, log = console.log) {
  const results = [];
  const add = (status, id, name, evidence = "") => {
    results.push({ id, name, status, evidence: String(evidence ?? "") });
    log(`${status.padEnd(4)}  ${id} ${name}${evidence ? ` — ${evidence}` : ""}`);
  };
  return {
    site,
    results,
    check: (id, name, ok, evidence) => add(ok ? "PASS" : "FAIL", id, name, evidence),
    info: (id, name, evidence) => add("INFO", id, name, evidence),
  };
}

export function summarize(recorders) {
  const sites = recorders.map(({ site, results }) => ({
    site,
    pass: results.filter((r) => r.status === "PASS").length,
    fail: results.filter((r) => r.status === "FAIL").length,
    info: results.filter((r) => r.status === "INFO").length,
  }));
  const total = (key) => sites.reduce((sum, s) => sum + s[key], 0);
  // Un sitio sin chequeos nunca cuenta como verde.
  const shortSites = Object.entries(EXPECTED_MIN_CHECKS)
    .map(([site, min]) => {
      const s = sites.find((x) => x.site === site);
      return { site, total: s ? s.pass + s.fail + s.info : 0, min };
    })
    .filter((x) => x.total < x.min);
  const ok = total("fail") === 0 && sites.every((s) => s.pass + s.fail > 0) && shortSites.length === 0;
  return { pass: total("pass"), fail: total("fail"), info: total("info"), ok, shortSites, sites };
}
