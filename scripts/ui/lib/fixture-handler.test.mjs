import assert from "node:assert/strict";
import { test } from "node:test";
import { createFixtureHandler } from "./fixture-handler.mjs";

const steps = [0, 1, 2].map((i) => ({
  session_id: "recorded",
  revealed_through: `2023-07-0${6 + i}`,
  can_advance: i < 2,
  predictions: [{ method: "ensemble", outcome: i === 0 ? null : "VN" }],
  feedback: null,
}));
const files = {
  "cicytex/catalog.json": { sensors: ["CP1_S1"], emission_dates_by_horizon: { 1: ["2023-07-06"] } },
  "cicytex/provenance.json": { ok: true },
  "cicytex/session-steps.json": { key: { sensor_id: "CP1_S1", emission_date: "2023-07-06", horizon_days: 1 }, steps },
  "cicytex/feedback.json": { registered_at: "2023-07-07T00:00:00Z" },
  "pergamino-ensemble-demo/forecasts__2023-06-13__2023-06-13.json": { slots: [] },
  "pergamino-ensemble-demo/readings__2023-06-13.json": { rows: [] },
  "pergamino-ensemble-demo/provenance__batch_abc.json": { batch_id: "batch_abc", horizons: [] },
  "lab/quality-template.json": { sensor_id: "x", total_rows: 0, period_start: null, period_end: null, out_of_range: {}, duplicate_timestamps: [] },
  "lab/forecast-run.json": { verdicts: [{ alerta: false, fecha: "x", fecha_objetivo: "y", probabilidad: 0 }] },
  "lab/feedback-list.json": { rows: [{ fecha: "x", fecha_objetivo: "y", estado_validacion: "pendiente" }] },
  "lab/models-active.json": { status: 200, body: { sensor_id: "x", version: "1" } },
};
const make = () => createFixtureHandler({ load: (path) => files[path] });
const call = (h, method, path, body) => h.handle({ method, path, body });
const C = "/api/v2/cicytex/replay";

test("catálogo y trazabilidad salen de las fixtures", () => {
  const h = make();
  assert.equal(call(h, "GET", `${C}/catalog`).status, 200);
  assert.deepEqual(call(h, "GET", `${C}/provenance`).body, { ok: true });
});

test("sesión CICYTEX: crear, avanzar, reiniciar son deterministas y en memoria", () => {
  const h = make();
  const created = call(h, "POST", `${C}/sessions`, { sensor_id: "CP1_S1", emission_date: "2023-07-06", horizon_days: 1 });
  assert.equal(created.status, 201);
  const id = created.body.session_id;
  assert.equal(id, "fixture-session-1");
  assert.equal(call(h, "POST", `${C}/sessions/${id}/advance`).body.revealed_through, "2023-07-07");
  assert.equal(call(h, "GET", `${C}/sessions/${id}`).body.revealed_through, "2023-07-07");
  assert.equal(call(h, "POST", `${C}/sessions/${id}/reset`).body.revealed_through, "2023-07-06");
  const again = make();
  assert.equal(call(again, "POST", `${C}/sessions`, { sensor_id: "CP1_S1", emission_date: "2023-07-06", horizon_days: 1 }).body.session_id, "fixture-session-1");
});

test("avanzar más allá del último paso grabado es 409, no inventa datos", () => {
  const h = make();
  const id = call(h, "POST", `${C}/sessions`, { sensor_id: "CP1_S1", emission_date: "2023-07-06", horizon_days: 1 }).body.session_id;
  call(h, "POST", `${C}/sessions/${id}/advance`);
  call(h, "POST", `${C}/sessions/${id}/advance`);
  assert.equal(call(h, "POST", `${C}/sessions/${id}/advance`).status, 409);
});

test("crear una sesión fuera de lo grabado es 422", () => {
  assert.equal(call(make(), "POST", `${C}/sessions`, { sensor_id: "OTRA", emission_date: "2023-07-06", horizon_days: 1 }).status, 422);
});

test("feedback exige realidad revelada y un estado explícito", () => {
  const h = make();
  const id = call(h, "POST", `${C}/sessions`, { sensor_id: "CP1_S1", emission_date: "2023-07-06", horizon_days: 1 }).body.session_id;
  assert.equal(call(h, "POST", `${C}/sessions/${id}/feedback`, { estado_validacion: "confirmada" }).status, 409);
  call(h, "POST", `${C}/sessions/${id}/advance`);
  assert.equal(call(h, "POST", `${C}/sessions/${id}/feedback`, {}).status, 422);
  const ok = call(h, "POST", `${C}/sessions/${id}/feedback`, { estado_validacion: "rechazada", observacion: "n" });
  assert.equal(ok.status, 201);
  assert.equal(call(h, "GET", `${C}/sessions/${id}`).body.feedback.estado_validacion, "rechazada");
});

test("modo session-404 hace que toda sesión conocida responda 404; reset lo limpia", () => {
  const h = make();
  const id = call(h, "POST", `${C}/sessions`, { sensor_id: "CP1_S1", emission_date: "2023-07-06", horizon_days: 1 }).body.session_id;
  h.setMode("session-404");
  assert.equal(call(h, "GET", `${C}/sessions/${id}`).status, 404);
  assert.equal(call(h, "GET", `${C}/catalog`).status, 200);
  h.reset();
  assert.equal(call(h, "GET", `${C}/sessions/${id}`).status, 404);
  assert.equal(h.mode, "normal");
});

test("modo disconnected corta toda ruta de API", () => {
  const h = make();
  h.setMode("disconnected");
  assert.deepEqual(call(h, "GET", `${C}/catalog`), { drop: true });
  assert.throws(() => h.setMode("otro"), /modo/);
});

test("histórico productor: sirve la fixture o 404 batch_not_prepared", () => {
  const h = make();
  const base = "/api/v2/sensors/pergamino-ensemble-demo/historical";
  assert.equal(call(h, "GET", `${base}/2023-06-13/forecasts`).status, 200);
  assert.equal(call(h, "GET", `${base}/2023-06-13/forecasts?revealed_through=2023-06-13`).status, 200);
  const missing = call(h, "GET", `${base}/2023-06-13/forecasts?revealed_through=2023-06-14`);
  assert.equal(missing.status, 404);
  assert.equal(missing.body.error.code, "batch_not_prepared");
  assert.equal(call(h, "GET", `${base}/2023-06-13/readings?days=10`).status, 200);
  assert.equal(call(h, "GET", `${base}/2023-06-19/readings?days=10`).status, 404);
});

test("procedencia productor: sirve la fixture grabada por batch_id o 404 batch_not_found", () => {
  const h = make();
  const base = "/api/v2/sensors/pergamino-ensemble-demo/batches";
  const found = call(h, "GET", `${base}/batch_abc/provenance`);
  assert.equal(found.status, 200);
  assert.equal(found.body.batch_id, "batch_abc");
  const missing = call(h, "GET", `${base}/batch_otro/provenance`);
  assert.equal(missing.status, 404);
  assert.equal(missing.body.error.code, "batch_not_found");
  assert.equal(call(h, "POST", `${base}/batch_abc/provenance`).status, 404);
  assert.deepEqual(h.unmatched, ["POST /api/v2/sensors/pergamino-ensemble-demo/batches/batch_abc/provenance"]);
});

test("laboratorio: la calidad se deriva de las lecturas ingeridas", () => {
  const h = make();
  assert.equal(call(h, "GET", "/quality/lab-1").status, 404);
  const r = call(h, "POST", "/sensors/lab-1/readings", { timestamp: "2026-01-01T00:00:00Z", temperature: 20 });
  assert.equal(r.body.filas_totales, 1);
  call(h, "POST", "/sensors/lab-1/readings", { timestamp: "2026-01-02T00:00:00Z", temperature: 85 });
  const q = call(h, "GET", "/quality/lab-1").body;
  assert.equal(q.total_rows, 2);
  assert.equal(q.period_end, "2026-01-02");
  assert.deepEqual(q.out_of_range.temperature, ["2026-01-02"]);
});

test("laboratorio: pronóstico, historial y modelo dependen de que haya datos y de la última lectura", () => {
  const h = make();
  assert.equal(call(h, "POST", "/forecast/lab-2/run").status, 404);
  assert.equal(call(h, "GET", "/feedback/lab-2").status, 404);
  assert.equal(call(h, "GET", "/models/lab-2/active").status, 404);
  call(h, "POST", "/sensors/lab-2/readings", { timestamp: "2026-01-10T00:00:00Z", temperature: 20 });
  const run = call(h, "POST", "/forecast/lab-2/run").body;
  assert.equal(run.verdicts[0].fecha, "2026-01-10");
  assert.equal(run.verdicts[0].fecha_objetivo, "2026-01-13");
  const rows = call(h, "GET", "/feedback/lab-2").body.rows;
  assert.deepEqual([rows[0].fecha, rows[0].fecha_objetivo], ["2026-01-10", "2026-01-13"]);
  assert.equal(call(h, "GET", "/models/lab-2/active").body.sensor_id, "lab-2");
});

test("rutas no registradas responden 404 y quedan anotadas", () => {
  const h = make();
  assert.equal(call(h, "GET", "/api/v2/nada").status, 404);
  assert.deepEqual(h.unmatched, ["GET /api/v2/nada"]);
});
