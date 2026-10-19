// Registro de resultados por sitio. Solo PASS/FAIL/INFO y texto: nada con hora, duración ni puertos (corridas comparables).
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
  const ok = total("fail") === 0 && sites.every((s) => s.pass + s.fail > 0);
  return { pass: total("pass"), fail: total("fail"), info: total("info"), ok, sites };
}
