import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { SiteHeader } from "./SiteHeader";
import { advanceCicytexSession, createCicytexSession, getCicytexCatalog, resetCicytexSession, submitCicytexFeedback, type CicytexCatalog, type CicytexSession } from "./cicytexApi";
import "./CicytexDefensePage.css";

const LABELS: Record<string,string> = { logistic_regression:"Logistic Regression", random_forest:"Random Forest", hist_gradient_boosting_classifier:"HistGradientBoosting", ensemble:"Ensamble", persistence:"Persistencia" };
const fmt = (value:number|null) => value === null ? "—" : value.toFixed(3);

function MoistureChart({session}:{session:CicytexSession}) {
  const points=session.readings.slice(-30), values=[...points.map(p=>p.soil_moisture),session.threshold];
  const min=Math.min(...values), max=Math.max(...values), range=max-min||1;
  const xy=points.map((p,i)=>`${20+i*(560/Math.max(points.length-1,1))},${180-((p.soil_moisture-min)/range)*140}`).join(" ");
  const thresholdY=180-((session.threshold-min)/range)*140;
  return <div className="cy-chart" aria-label="Humedad revelada hasta el reloj actual"><svg viewBox="0 0 600 210" role="img"><line x1="20" x2="580" y1={thresholdY} y2={thresholdY} className="cy-threshold"/><polyline points={xy} className="cy-moisture"/><text x="24" y={Math.max(16,thresholdY-6)}>P20 {session.threshold.toFixed(3)}</text></svg><p>Solo se dibujan observaciones reveladas hasta <strong>{session.revealed_through}</strong>.</p></div>;
}

type FeedbackDraft = { sessionId: string | null; choice: "confirmada" | "rechazada"; note: string };
const EMPTY_DRAFT: FeedbackDraft = { sessionId: null, choice: "confirmada", note: "" };

function messageOf(reason: unknown): string {
  return reason instanceof Error ? reason.message : String(reason);
}

export function CicytexDefensePage() {
  const [catalog, setCatalog] = useState<CicytexCatalog | null>(null);
  const [catalogLoading, setCatalogLoading] = useState(true);
  const [sensor, setSensor] = useState("CP1_S1");
  const [horizon, setHorizon] = useState(1);
  const [emission, setEmission] = useState("2023-07-06");
  const [session, setSession] = useState<CicytexSession | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  // El borrador pertenece a una sesión: se liga a su id y se descarta al
  // cambiar la selección, abrir otra sesión o reiniciar la actual.
  const [draft, setDraft] = useState<FeedbackDraft>(EMPTY_DRAFT);
  const currentDraft = session && draft.sessionId === session.session_id ? draft : EMPTY_DRAFT;
  const feedbackChoice = currentDraft.choice;
  const feedbackNote = currentDraft.note;
  const editDraft = (patch: Partial<Pick<FeedbackDraft, "choice" | "note">>) =>
    session && setDraft({ ...currentDraft, ...patch, sessionId: session.session_id });
  // Cada cambio de selección invalida las respuestas en vuelo: una respuesta
  // tardía de otra sonda/fecha no debe pisar la vista actual.
  const generation = useRef(0);
  const inFlight = useRef(false);

  const fetchCatalog = useCallback(
    () =>
      getCicytexCatalog()
        .then(setCatalog)
        .catch((reason) => setError(`No se pudo cargar el catálogo: ${messageOf(reason)}`))
        .finally(() => setCatalogLoading(false)),
    [],
  );
  useEffect(() => {
    void fetchCatalog();
  }, [fetchCatalog]);
  function retryCatalog() {
    setCatalogLoading(true);
    setError(null);
    void fetchCatalog();
  }

  const dates = catalog?.emission_dates_by_horizon[String(horizon)] ?? [];
  // La fecha efectiva se deriva: si la elegida no existe para el horizonte, rige la primera.
  const effectiveEmission = dates.includes(emission) ? emission : (dates[0] ?? emission);

  function changeSelection(apply: () => void) {
    generation.current += 1;
    inFlight.current = false;
    setBusy(false);
    setSession(null);
    setDraft(EMPTY_DRAFT);
    apply();
  }

  const ensemble = session?.predictions.find((p) => p.method === "ensemble");
  const agreement = useMemo(() => {
    const members = session?.predictions.filter((p) => !["ensemble", "persistence"].includes(p.method)) ?? [];
    return members.length ? `${members.filter((p) => p.alert).length}/3 alertan` : "—";
  }, [session]);

  async function run<T>(request: () => Promise<T>, apply: (result: T) => void) {
    if (inFlight.current) return;
    const mine = generation.current;
    inFlight.current = true;
    setBusy(true);
    setError(null);
    try {
      const result = await request();
      if (mine === generation.current) apply(result);
    } catch (reason) {
      if (mine === generation.current) setError(messageOf(reason));
    } finally {
      if (mine === generation.current) {
        inFlight.current = false;
        setBusy(false);
      }
    }
  }

  // Abrir o reiniciar una sesión descarta el borrador del contexto anterior.
  const act = (action: () => Promise<CicytexSession>, options: { clearDraft?: boolean } = {}) =>
    run(action, (next) => {
      if (options.clearDraft) setDraft(EMPTY_DRAFT);
      setSession(next);
    });

  function submitFeedback() {
    if (!session) return;
    const id = session.session_id;
    void run(
      () =>
        submitCicytexFeedback(id, {
          estado_validacion: feedbackChoice,
          observacion: feedbackNote.trim() || undefined,
        }),
      (feedback) =>
        setSession((current) => (current && current.session_id === id ? { ...current, feedback } : current)),
    );
  }

  return (
    <div className="cicytex-defense">
      <SiteHeader site="cicytex" />
      <section className="cy-intro">
        <p>
          <strong>Prueba retrospectiva causal.</strong> Tomate de industria, Talavera la Real, campaña 2023; 21
          sondas a 20 cm. Las familias fueron congeladas después de validar hasta el 05/07/2023.
        </p>
        <p>
          El evento es humedad volumétrica inferior al P20 de entrenamiento. No equivale a estrés hídrico
          fisiológico observado.
        </p>
      </section>
      <section className="cy-controls" aria-label="Seleccionar reproducción CICYTEX">
        <label>
          Sonda
          <select value={sensor} onChange={(e) => changeSelection(() => setSensor(e.target.value))}>
            {catalog?.sensors.map((item) => (
              <option key={item}>{item}</option>
            ))}
          </select>
        </label>
        <label>
          Horizonte
          <select value={horizon} onChange={(e) => changeSelection(() => setHorizon(Number(e.target.value)))}>
            {[1, 2, 3].map((item) => (
              <option value={item} key={item}>
                +{item} día{item > 1 ? "s" : ""}
              </option>
            ))}
          </select>
        </label>
        <label>
          Fecha de emisión
          <select value={effectiveEmission} onChange={(e) => changeSelection(() => setEmission(e.target.value))}>
            {dates.map((item) => (
              <option key={item}>{item}</option>
            ))}
          </select>
        </label>
        <button
          disabled={!catalog || busy}
          onClick={() => void act(() => createCicytexSession(sensor, effectiveEmission, horizon), { clearDraft: true })}
        >
          Abrir emisión congelada
        </button>
      </section>
      {catalogLoading && <p role="status">Cargando catálogo…</p>}
      {error && (
        <p role="alert" className="cy-error">
          {error}
          {!catalog && !catalogLoading && (
            <>
              {" "}
              <button type="button" onClick={retryCatalog}>
                Reintentar
              </button>
            </>
          )}
        </p>
      )}
      {session && (
        <>
          <section className="cy-clock">
            <div>
              <span>Emisión</span>
              <strong>{session.emission_date}</strong>
            </div>
            <div>
              <span>Reloj revelado</span>
              <strong>{session.revealed_through}</strong>
            </div>
            <div>
              <span>Objetivo</span>
              <strong>{ensemble?.target_date}</strong>
            </div>
            <button
              disabled={busy || !session.can_advance}
              onClick={() => void act(() => advanceCicytexSession(session.session_id))}
            >
              Día siguiente
            </button>
            <button disabled={busy} onClick={() => void act(() => resetCicytexSession(session.session_id), { clearDraft: true })}>
              Reiniciar
            </button>
          </section>
          {ensemble && (
            <section className={`cy-verdict ${ensemble.alert ? "is-alert" : "is-clear"}`} aria-live="polite">
              <p className="cy-verdict-kicker">Decisión de la arquitectura</p>
              <h2>{ensemble.alert ? "ALERTA DE HUMEDAD BAJA" : "SIN ALERTA DE HUMEDAD BAJA"}</h2>
              <p>
                Ensamble {ensemble.score.toFixed(3)} · objetivo {ensemble.target_date} · acuerdo {agreement}.
              </p>
              {ensemble.outcome === null ? (
                <p className="cy-future-lock">
                  La realidad permanece oculta hasta que el reloj alcance la fecha objetivo.
                </p>
              ) : (
                <p className={ensemble.outcome === "VP" || ensemble.outcome === "VN" ? "cy-truth-match" : "cy-truth-miss"}>
                  <strong>Realidad revelada:</strong>{" "}
                  {ensemble.observed_label === 1 ? "hubo humedad baja" : "no hubo humedad baja"} · resultado{" "}
                  <strong>{ensemble.outcome}</strong>.
                </p>
              )}
            </section>
          )}
          <section className="cy-panel">
            <h2>
              Predicción archivada · +{session.horizon_days} día{session.horizon_days > 1 ? "s" : ""}
            </h2>
            <p>
              Acuerdo: <strong>{agreement}</strong> · decisión 0,5 · P20 {session.threshold.toFixed(4)} m³/m³.
            </p>
            <div className="cy-table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Método</th>
                    <th>Score</th>
                    <th>Alerta</th>
                    <th>Observado</th>
                    <th>Resultado</th>
                  </tr>
                </thead>
                <tbody>
                  {session.predictions.map((p) => (
                    <tr key={p.method} className={p.method === "ensemble" ? "is-ensemble" : ""}>
                      <th>{LABELS[p.method]}</th>
                      <td>{p.score.toFixed(3)}</td>
                      <td>{p.alert ? "Sí" : "No"}</td>
                      <td>
                        {p.observed_soil_moisture === null
                          ? "Oculto hasta avanzar"
                          : `${p.observed_soil_moisture.toFixed(4)} m³/m³`}
                      </td>
                      <td>{p.outcome ?? "Pendiente"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
          <MoistureChart session={session} />
          <section className="cy-panel">
            <h2>Comparación acumulada revelada</h2>
            <div className="cy-table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Método</th>
                    <th>n</th>
                    <th>VP</th>
                    <th>VN</th>
                    <th>FP</th>
                    <th>FN</th>
                    <th>MCC</th>
                    <th>Prec.</th>
                    <th>Recall</th>
                    <th>F1</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(session.metrics).map(
                    ([method, m]) =>
                      m && (
                        <tr key={method}>
                          <th>{LABELS[method]}</th>
                          <td>{m.n}</td>
                          <td>{m.tp}</td>
                          <td>{m.tn}</td>
                          <td>{m.fp}</td>
                          <td>{m.fn}</td>
                          <td>{fmt(m.mcc)}</td>
                          <td>{fmt(m.precision)}</td>
                          <td>{fmt(m.recall)}</td>
                          <td>{fmt(m.f1)}</td>
                        </tr>
                      ),
                  )}
                </tbody>
              </table>
            </div>
            <p>Solo se usan objetivos cuya fecha ya reveló esta sesión.</p>
          </section>
          {ensemble?.outcome !== null && (
            <section className="cy-panel cy-feedback">
              <h2>Feedback humano de demostración</h2>
              <p>
                Se habilita recién después de revelar la realidad. Queda aislado: no recalibra ni reentrena
                modelos.
              </p>
              {session.feedback ? (
                <div role="status" className="cy-feedback-saved">
                  <strong>Feedback registrado: {session.feedback.estado_validacion}.</strong>
                  {session.feedback.observacion && <p>“{session.feedback.observacion}”</p>}
                  <small>{session.feedback.registered_at}</small>
                </div>
              ) : (
                <form
                  onSubmit={(event) => {
                    event.preventDefault();
                    submitFeedback();
                  }}
                >
                  <fieldset>
                    <legend>¿La decisión del ensamble representa correctamente lo observado?</legend>
                    <label>
                      <input
                        type="radio"
                        name="cicytex-feedback"
                        checked={feedbackChoice === "confirmada"}
                        onChange={() => editDraft({ choice: "confirmada" })}
                      />{" "}
                      Sí, coincide
                    </label>
                    <label>
                      <input
                        type="radio"
                        name="cicytex-feedback"
                        checked={feedbackChoice === "rechazada"}
                        onChange={() => editDraft({ choice: "rechazada" })}
                      />{" "}
                      No coincide
                    </label>
                  </fieldset>
                  <label>
                    Observación opcional
                    <textarea rows={3} value={feedbackNote} onChange={(event) => editDraft({ note: event.target.value })} />
                  </label>
                  <button disabled={busy} type="submit">
                    {busy ? "Registrando…" : "Registrar feedback"}
                  </button>
                </form>
              )}
            </section>
          )}
        </>
      )}
    </div>
  );
}
