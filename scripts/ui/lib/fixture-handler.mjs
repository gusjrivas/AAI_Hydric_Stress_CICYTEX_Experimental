// Lógica determinista del servidor de fixtures (sin red ni disco propios: `load(rutaRelativa)` entrega JSON grabado).
// Las respuestas provienen de grabaciones del backend real (frontend/e2e/fixtures/README.md); lo único calculado
// aquí es el estado en memoria de las sesiones CICYTEX y los campos derivados de las lecturas del laboratorio.
const MODES = ["normal", "disconnected", "session-404"];
const TEMPERATURE_RANGE = [-10, 50]; // mismo rango agronómico que src/data_quality/rules.py
const CICYTEX = "/api/v2/cicytex/replay";

const addDays = (iso, n) => {
  const d = new Date(`${iso}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + n);
  return d.toISOString().slice(0, 10);
};
const lastDay = (rows) => rows.map((r) => r.timestamp.slice(0, 10)).sort().pop();
const ok = (body, status = 200) => ({ status, body });
const notFound = (detail) => ({ status: 404, body: { detail } });

export function createFixtureHandler({ load }) {
  let mode = "normal";
  let nextSession = 1;
  let sessions = new Map();
  let labReadings = new Map();
  let labForecasts = new Map();
  let unmatched = [];

  const api = {
    get mode() {
      return mode;
    },
    get unmatched() {
      return [...unmatched];
    },
    setMode(next) {
      if (!MODES.includes(next)) throw new Error(`modo desconocido: ${next} (válidos: ${MODES.join(", ")})`);
      mode = next;
    },
    reset() {
      mode = "normal";
      nextSession = 1;
      sessions = new Map();
      labReadings = new Map();
      labForecasts = new Map();
      unmatched = [];
    },
    handle({ method, path, body }) {
      const [pathname, queryString = ""] = path.split("?");
      const query = new URLSearchParams(queryString);
      if (mode === "disconnected") return { drop: true };
      return (
        cicytex(method, pathname, body) ??
        producerProvenance(method, pathname) ??
        producer(method, pathname, query) ??
        lab(method, pathname, body) ??
        miss(method, pathname)
      );
    },
  };

  function miss(method, pathname) {
    unmatched.push(`${method} ${pathname}`);
    return notFound(`fixture: ruta no registrada ${method} ${pathname}`);
  }

  function sessionView(session) {
    const step = structuredClone(session.steps[session.index]);
    step.session_id = session.id;
    step.feedback = session.feedback;
    return step;
  }

  function cicytex(method, pathname, body) {
    if (!pathname.startsWith(CICYTEX)) return null;
    const rest = pathname.slice(CICYTEX.length);
    if (method === "GET" && rest === "/catalog") return ok(load("cicytex/catalog.json"));
    if (method === "GET" && rest === "/provenance") return ok(load("cicytex/provenance.json"));
    const recorded = load("cicytex/session-steps.json");
    if (method === "POST" && rest === "/sessions") {
      const k = recorded.key;
      if (body?.sensor_id !== k.sensor_id || body?.emission_date !== k.emission_date || body?.horizon_days !== k.horizon_days) {
        return ok({ detail: "fixture: sólo está grabada la selección " + JSON.stringify(k) }, 422);
      }
      const id = `fixture-session-${nextSession++}`;
      const session = { id, steps: recorded.steps, index: 0, feedback: null };
      sessions.set(id, session);
      return ok(sessionView(session), 201);
    }
    const match = rest.match(/^\/sessions\/([^/]+)(?:\/(advance|reset|feedback))?$/);
    if (!match) return null;
    const [, id, action] = match;
    const session = sessions.get(id);
    if (!session || mode === "session-404") return notFound("Sesión no encontrada");
    if (method === "GET" && !action) return ok(sessionView(session));
    if (method !== "POST") return null;
    if (action === "advance") {
      if (session.index >= session.steps.length - 1) return ok({ detail: "fixture: no hay más pasos grabados" }, 409);
      session.index += 1;
      return ok(sessionView(session));
    }
    if (action === "reset") {
      session.index = 0;
      session.feedback = null;
      return ok(sessionView(session));
    }
    if (action === "feedback") {
      const ensemble = session.steps[session.index].predictions.find((p) => p.method === "ensemble");
      if (!ensemble || ensemble.outcome === null) return ok({ detail: "La realidad todavía está oculta" }, 409);
      if (!["confirmada", "rechazada"].includes(body?.estado_validacion)) return ok({ detail: "estado_validacion inválido" }, 422);
      session.feedback = { ...load("cicytex/feedback.json"), estado_validacion: body.estado_validacion, observacion: body.observacion ?? null };
      return ok(session.feedback, 201);
    }
    return null;
  }

  function producerProvenance(method, pathname) {
    const match = pathname.match(/^\/api\/v2\/sensors\/([^/]+)\/batches\/([^/]+)\/provenance$/);
    if (!match || method !== "GET") return null;
    const file = load(`${match[1]}/provenance__${match[2]}.json`);
    return file
      ? ok(file)
      : ok({ error: { code: "batch_not_found", message: "La emisión no existe para este sensor." } }, 404);
  }

  function producer(method, pathname, query) {
    const match = pathname.match(/^\/api\/v2\/sensors\/([^/]+)\/historical\/(\d{4}-\d{2}-\d{2})\/(forecasts|readings)$/);
    if (!match || method !== "GET") return null;
    const [, sensor, date, kind] = match;
    if (kind === "forecasts") {
      const revealed = query.get("revealed_through") ?? date;
      const file = load(`${sensor}/forecasts__${date}__${revealed}.json`);
      return file
        ? ok(file)
        : ok({ error: { code: "batch_not_prepared", message: "No hay una emisión preparada para esta fecha." } }, 404);
    }
    const file = load(`${sensor}/readings__${date}.json`);
    return file ? ok(file) : ok({ error: { code: "not_found", message: "Sin lecturas grabadas para esta fecha." } }, 404);
  }

  function lab(method, pathname, body) {
    let m = pathname.match(/^\/sensors\/([^/]+)\/readings$/);
    if (m && method === "POST") {
      const rows = labReadings.get(m[1]) ?? [];
      rows.push(body);
      labReadings.set(m[1], rows);
      return ok({ timestamp: body.timestamp, filas_totales: rows.length });
    }
    m = pathname.match(/^\/quality\/([^/]+)$/);
    if (m && method === "GET") {
      const rows = labReadings.get(m[1]);
      if (!rows) return notFound("Sin datos para este sensor");
      const days = rows.map((r) => r.timestamp.slice(0, 10)).sort();
      const outside = rows
        .filter((r) => r.temperature < TEMPERATURE_RANGE[0] || r.temperature > TEMPERATURE_RANGE[1])
        .map((r) => r.timestamp.slice(0, 10));
      const report = structuredClone(load("lab/quality-template.json"));
      return ok({
        ...report,
        sensor_id: m[1],
        total_rows: rows.length,
        period_start: days[0],
        period_end: days[days.length - 1],
        out_of_range: { ...report.out_of_range, temperature: outside },
      });
    }
    m = pathname.match(/^\/forecast\/([^/]+)\/run$/);
    if (m && method === "POST") {
      const rows = labReadings.get(m[1]);
      if (!rows) return notFound("Sin datos para este sensor");
      const fecha = lastDay(rows);
      const objetivo = addDays(fecha, 3); // horizonte del backend (HORIZON_DAYS = 3)
      labForecasts.set(m[1], { fecha, objetivo });
      const run = structuredClone(load("lab/forecast-run.json"));
      return ok({ ...run, verdicts: run.verdicts.map((v) => ({ ...v, fecha, fecha_objetivo: objetivo })) });
    }
    m = pathname.match(/^\/feedback\/([^/]+)$/);
    if (m && method === "GET") {
      const run = labForecasts.get(m[1]);
      if (!run) return notFound("Sin registros para este sensor");
      const list = structuredClone(load("lab/feedback-list.json"));
      return ok({ ...list, rows: list.rows.map((r) => ({ ...r, fecha: run.fecha, fecha_objetivo: run.objetivo })) });
    }
    m = pathname.match(/^\/models\/([^/]+)\/active$/);
    if (m && method === "GET") {
      if (!labForecasts.has(m[1])) return notFound("Sin predictor para este sensor");
      const active = load("lab/models-active.json");
      return ok({ ...active.body, sensor_id: m[1] });
    }
    return null;
  }

  return api;
}
