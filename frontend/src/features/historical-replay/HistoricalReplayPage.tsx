import { useEffect, useRef, useState } from "react";
import "./HistoricalReplayPage.css";
import {
  ReplayNotFoundError,
  ReplayNotYetRevealedError,
  createFeedback,
  getCandidate,
  getFeedback,
  getHistory,
  getPrediction,
  listOrigins,
  type EstadoValidacion,
  type ReplayCandidateInfo,
  type ReplayFeedbackEntry,
  type ReplayHistoryRow,
  type ReplayPredictionResponse,
} from "./api";
import { addDaysIso, clampIso, compareIso } from "./dateUtils";
import { classLabel } from "./labelRule";
import { MoistureHistoryChart } from "./MoistureHistoryChart";
import { ReplayEvidenceCard } from "./ReplayEvidenceCard";
import { ReplayFeedbackForm } from "./ReplayFeedbackForm";
import { taggedFor, visibleFor, type ForSelection } from "./selectionScope";

type PageStatus = "loading" | "unavailable" | "error" | "ready";

type PredictionState =
  | { status: "loading" }
  | { status: "hidden-before-origin" }
  | { status: "unknown-origin" }
  | { status: "error"; message: string }
  | { status: "ready"; data: ReplayPredictionResponse };

type HistoryState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; rows: ReplayHistoryRow[] };

type FeedbackState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; entries: ReplayFeedbackEntry[] };

const LOADING_PREDICTION: PredictionState = { status: "loading" };
const LOADING_HISTORY: HistoryState = { status: "loading" };
const LOADING_FEEDBACK: FeedbackState = { status: "loading" };

/**
 * Pantalla "Reproducción histórica" (Paso 4, corregida en Paso 4.1, cierre
 * en Paso 4.1.1). Consume exclusivamente las respuestas ya filtradas del
 * backend — nunca descarga el paquete completo ni el dataset entero.
 *
 * Aislamiento de estado (Paso 4.1 §1, corregido en el cierre): cada
 * resultado (predicción, historial, feedback) se guarda etiquetado con el
 * `(origen, fecha simulada)` para el que se pidió (`selectionScope.ts`,
 * `taggedFor`). En el render, `visibleFor` decide si ese resultado
 * corresponde a la selección vigente — si no, se muestra el estado
 * `loading` en su lugar. Esta es la garantía real: es una comparación pura
 * hecha en cada render a partir del estado ya comprometido, **no depende de
 * que ningún `useEffect` haya corrido todavía**. El primer render posterior
 * a un cambio de selección (antes de que el efecto llegue a ejecutarse)
 * también queda cubierto, porque el resultado guardado de la selección
 * anterior no coincide con la selección ya vigente en ese mismo render.
 *
 * Aparte, un contador de generación (`generationRef`) sigue resolviendo la
 * carrera asincrónica entre promesas (p. ej. A→B→A, donde dos resultados
 * distintos podrían llegar etiquetados para el mismo `(origen, fecha)`):
 * solo la promesa iniciada en la generación todavía vigente puede escribir
 * estado al resolver.
 */
export function HistoricalReplayPage() {
  const [pageStatus, setPageStatus] = useState<PageStatus>("loading");
  const [pageError, setPageError] = useState<string | null>(null);
  const [candidate, setCandidate] = useState<ReplayCandidateInfo | null>(null);
  const [origins, setOrigins] = useState<string[]>([]);
  const [selectedOrigin, setSelectedOrigin] = useState<string>("");
  const [simulatedDate, setSimulatedDate] = useState<string>("");

  const [predictionState, setPredictionState] = useState<ForSelection<PredictionState>>(
    taggedFor("", "", LOADING_PREDICTION),
  );
  const [historyState, setHistoryState] = useState<ForSelection<HistoryState>>(
    taggedFor("", "", LOADING_HISTORY),
  );
  const [feedbackState, setFeedbackState] = useState<ForSelection<FeedbackState>>(
    taggedFor("", "", LOADING_FEEDBACK),
  );

  const [feedbackSubmitting, setFeedbackSubmitting] = useState(false);
  const [feedbackSubmitError, setFeedbackSubmitError] = useState<string | null>(null);

  // Contador monotónico de generación: resuelve la carrera asincrónica
  // entre promesas para el mismo `(origen, fecha)` (p. ej. A→B→A). Solo la
  // respuesta cuya generación sigue siendo la vigente al llegar puede
  // escribir estado (Paso 4.1 §1). La ausencia de datos obsoletos en el
  // render, en cambio, la garantiza el etiquetado de selección de arriba,
  // no este contador.
  const generationRef = useRef(0);
  // Evita escribir estado tras desmontar (limpieza al desmontar, Paso 4.1.1
  // §1). Se reafirma en `true` en cada montaje del efecto, no solo en el
  // `useRef` inicial: bajo `StrictMode` (activo en este proyecto,
  // `main.tsx`) React invoca montaje→limpieza→montaje una segunda vez en
  // desarrollo para detectar exactamente este tipo de error, y una versión
  // anterior de esta guarda que solo ponía `mountedRef.current = false` en
  // la limpieza quedaba permanentemente en `false` tras ese doble montaje
  // — bloqueando para siempre cualquier actualización de estado real.
  // Encontrado verificando el arranque en un navegador real, no solo con
  // los tests (que no usan `StrictMode`).
  const mountedRef = useRef(true);
  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    Promise.all([getCandidate(), listOrigins()])
      .then(([candidateInfo, originsResponse]) => {
        if (cancelled) return;
        const sortedOrigins = originsResponse.origins
          .map((o) => o.timestamp_origen)
          .sort(compareIso);
        setCandidate(candidateInfo);
        setOrigins(sortedOrigins);
        setSelectedOrigin(sortedOrigins[0] ?? "");
        setSimulatedDate(sortedOrigins[0] ?? candidateInfo.periodo_inicio);
        setPageStatus("ready");
      })
      .catch((error) => {
        if (cancelled) return;
        if (error instanceof ReplayNotFoundError) {
          setPageStatus("unavailable");
        } else {
          setPageError((error as Error).message);
          setPageStatus("error");
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!selectedOrigin || !simulatedDate) return;
    // Nueva generación: solo protege contra respuestas de promesas que
    // lleguen fuera de orden para el mismo (origen, fecha) — la ausencia de
    // datos obsoletos en el render la garantiza el etiquetado de selección,
    // no esta línea (ver comentario de la función).
    const myGeneration = ++generationRef.current;
    const origin = selectedOrigin;
    const clock = simulatedDate;
    const stillCurrent = () => mountedRef.current && generationRef.current === myGeneration;

    setPredictionState(taggedFor(origin, clock, LOADING_PREDICTION));
    setHistoryState(taggedFor(origin, clock, LOADING_HISTORY));
    setFeedbackState(taggedFor(origin, clock, LOADING_FEEDBACK));
    setFeedbackSubmitError(null);
    // Un envío de feedback en vuelo pertenece a la selección anterior: no
    // debe seguir bloqueando el formulario de la nueva selección, aunque su
    // respuesta (ya ignorada por generación) todavía no haya llegado.
    setFeedbackSubmitting(false);

    getPrediction(origin, clock)
      .then((result) => {
        if (!stillCurrent()) return;
        setPredictionState(taggedFor(origin, clock, { status: "ready", data: result }));
      })
      .catch((error) => {
        if (!stillCurrent()) return;
        if (error instanceof ReplayNotFoundError) {
          setPredictionState(
            taggedFor(origin, clock, {
              status: compareIso(clock, origin) < 0 ? "hidden-before-origin" : "unknown-origin",
            }),
          );
        } else {
          setPredictionState(
            taggedFor(origin, clock, { status: "error", message: (error as Error).message }),
          );
        }
      });

    getHistory(clock)
      .then((result) => {
        if (!stillCurrent()) return;
        setHistoryState(taggedFor(origin, clock, { status: "ready", rows: result.rows }));
      })
      .catch((error) => {
        if (!stillCurrent()) return;
        setHistoryState(
          taggedFor(origin, clock, { status: "error", message: (error as Error).message }),
        );
      });

    getFeedback(origin, clock)
      .then((result) => {
        if (!stillCurrent()) return;
        setFeedbackState(taggedFor(origin, clock, { status: "ready", entries: result.feedback }));
      })
      .catch((error) => {
        if (!stillCurrent()) return;
        setFeedbackState(
          taggedFor(origin, clock, { status: "error", message: (error as Error).message }),
        );
      });
  }, [selectedOrigin, simulatedDate]);

  function moveClock(days: number) {
    if (!candidate) return;
    setSimulatedDate((current) =>
      clampIso(addDaysIso(current, days), candidate.periodo_inicio, candidate.periodo_fin),
    );
  }

  function resetClock() {
    if (!origins.length || !candidate) return;
    setSelectedOrigin(origins[0]);
    setSimulatedDate(origins[0]);
  }

  function handleFeedbackSubmit(input: {
    estado_validacion: EstadoValidacion;
    etiqueta_corregida?: 0 | 1 | null;
    observacion?: string | null;
  }) {
    // Captura el origen/fecha/generación vigentes en el momento del envío:
    // si el usuario navega a otra selección antes de que responda el POST,
    // esa respuesta no debe poblar la pantalla de la nueva selección
    // (Paso 4.1 §1).
    const origin = selectedOrigin;
    const clock = simulatedDate;
    const myGeneration = generationRef.current;
    const stillCurrent = () => mountedRef.current && generationRef.current === myGeneration;

    setFeedbackSubmitting(true);
    setFeedbackSubmitError(null);
    createFeedback(origin, { simulated_date: clock, ...input })
      .then((entry) => {
        if (!stillCurrent()) return;
        setFeedbackState(taggedFor(origin, clock, { status: "ready", entries: [entry] }));
      })
      .catch((error) => {
        if (!stillCurrent()) return;
        if (error instanceof ReplayNotYetRevealedError) {
          setFeedbackSubmitError("La observación todavía no fue revelada en esta fecha simulada.");
        } else {
          setFeedbackSubmitError((error as Error).message);
        }
      })
      .finally(() => {
        if (stillCurrent()) setFeedbackSubmitting(false);
      });
  }

  if (pageStatus === "loading") {
    return (
      <p role="status" className="hr-status">
        Cargando la reproducción histórica…
      </p>
    );
  }

  if (pageStatus === "unavailable") {
    return (
      <p role="status" className="hr-status">
        La reproducción histórica no está habilitada en este backend.
      </p>
    );
  }

  if (pageStatus === "error" || !candidate) {
    return (
      <p role="alert" className="hr-error">
        No se pudo cargar la reproducción histórica: {pageError}
      </p>
    );
  }

  // Filtro de selección vigente (Paso 4.1, cierre §1): si el resultado
  // guardado no corresponde a `(selectedOrigin, simulatedDate)` — por
  // ejemplo, es el de la selección anterior y el efecto todavía no corrió
  // para la nueva — se usa el estado `loading` en su lugar. Esto es cierto
  // en todo render, incluido el primero posterior a un cambio de selección.
  const predictionVisible = visibleFor(predictionState, selectedOrigin, simulatedDate, LOADING_PREDICTION);
  const historyVisible = visibleFor(historyState, selectedOrigin, simulatedDate, LOADING_HISTORY);
  const feedbackVisible = visibleFor(feedbackState, selectedOrigin, simulatedDate, LOADING_FEEDBACK);

  const prediction = predictionVisible.status === "ready" ? predictionVisible.data : null;
  // RH-07: el formulario solo se habilita cuando la observación fue
  // efectivamente revelada (target_observed === true) — no simplemente
  // cuando el estado ya no es undefined, lo que también incluiría
  // target_observed === false (objetivo que nunca maduró en este run).
  const revealed = prediction?.target_observed === true;

  return (
    <div className="hr-page">
      <p className="hr-badge" role="note">
        Reproducción histórica retrospectiva — no son emisiones de un sistema en producción.
      </p>
      <p className="hr-disclaimer">
        Se reproduce un backtest sobre datos reales del experimento {candidate.experiment_id}{" "}
        (dataset <strong>{candidate.evidencia.dataset_name}</strong>), no alertas emitidas
        históricamente por un sistema desplegado. La clase mostrada es un
        <strong> proxy estadístico relativo</strong>, no un diagnóstico agronómico; su utilidad
        agronómica no fue demostrada.
      </p>

      <ReplayEvidenceCard candidate={candidate} />

      <section className="hr-controls" aria-label="Selección y reloj simulado">
        <label>
          Origen de la predicción
          <select
            value={selectedOrigin}
            onChange={(event) => setSelectedOrigin(event.target.value)}
          >
            {origins.map((origin) => (
              <option key={origin} value={origin}>
                {origin}
              </option>
            ))}
          </select>
        </label>

        <p className="hr-clock" aria-live="polite">
          Fecha simulada: <strong>{simulatedDate}</strong>
        </p>

        <div className="hr-clock-controls">
          <button type="button" onClick={() => moveClock(-1)} disabled={simulatedDate === candidate.periodo_inicio}>
            ◀ Retroceder
          </button>
          <button type="button" onClick={() => moveClock(1)} disabled={simulatedDate === candidate.periodo_fin}>
            Avanzar ▶
          </button>
          <button type="button" onClick={resetClock}>
            Reiniciar
          </button>
        </div>
      </section>

      <section aria-label="Historial de humedad" className="hr-history">
        <h3>Historial de humedad (hasta el reloj simulado)</h3>
        {historyVisible.status === "loading" && <p role="status">Cargando historial…</p>}
        {historyVisible.status === "error" && (
          <p role="alert" className="hr-error">
            Error al consultar el historial: {historyVisible.message}
          </p>
        )}
        {historyVisible.status === "ready" && <MoistureHistoryChart rows={historyVisible.rows} />}
      </section>

      <section aria-label="Predicción archivada" className="hr-prediction">
        <h3>Predicción archivada (+{candidate.horizon_days} días)</h3>
        {predictionVisible.status === "loading" && <p role="status">Cargando predicción…</p>}
        {predictionVisible.status === "hidden-before-origin" && (
          <p role="status" className="hr-status">
            La fecha simulada es anterior al origen de esta predicción: todavía no fue "emitida".
          </p>
        )}
        {predictionVisible.status === "unknown-origin" && (
          <p role="alert" className="hr-error">
            No hay ninguna predicción archivada para este origen.
          </p>
        )}
        {predictionVisible.status === "error" && (
          <p role="alert" className="hr-error">
            Error al consultar la predicción: {predictionVisible.message}
          </p>
        )}
        {prediction && (
          <div className="hr-prediction-card">
            <dl>
              <div>
                <dt>Origen</dt>
                <dd>{prediction.timestamp_origen}</dd>
              </div>
              <div>
                <dt>Fecha objetivo</dt>
                <dd>{prediction.target_timestamp}</dd>
              </div>
              <div>
                <dt>Clase predicha (proxy estadístico relativo)</dt>
                <dd className="hr-class-badge" data-class={prediction.y_pred}>
                  {classLabel(prediction.y_pred as 0 | 1, candidate.regla_etiqueta)}
                </dd>
              </div>
            </dl>

            {prediction.target_observed == null && (
              <p role="status" className="hr-status">
                Observación posterior: todavía no revelada en la fecha simulada.
              </p>
            )}
            {prediction.target_observed === false && (
              <p role="status" className="hr-status">
                Observación no disponible: el objetivo no maduró en este run.
              </p>
            )}
            {prediction.target_observed === true && (
              <div className="hr-observation">
                <dl>
                  <div>
                    <dt>Observación revelada</dt>
                    <dd>{classLabel(prediction.y_true as 0 | 1, candidate.regla_etiqueta)}</dd>
                  </div>
                  <div>
                    <dt>Coincidencia con la predicción</dt>
                    <dd className={prediction.coincide ? "hr-match" : "hr-mismatch"}>
                      {prediction.coincide ? "Coincide" : "Discrepa"}
                    </dd>
                  </div>
                  {prediction.medicion_original && (
                    <div>
                      <dt>Medición original</dt>
                      <dd>
                        {prediction.medicion_original.estado}
                        {prediction.medicion_original.valor !== null &&
                          ` (${prediction.medicion_original.valor.toFixed(3)} m³/m³)`}
                      </dd>
                    </div>
                  )}
                </dl>
              </div>
            )}
          </div>
        )}
      </section>

      {revealed && (
        <section aria-label="Feedback de demostración" className="hr-feedback-section">
          <h3>Feedback de demostración</h3>
          {feedbackVisible.status === "loading" && <p role="status">Cargando feedback…</p>}
          {feedbackVisible.status === "error" && (
            <p role="alert" className="hr-error">
              No se pudo consultar el feedback existente: {feedbackVisible.message}. No se habilita
              un nuevo registro hasta poder confirmar que no existe uno previo.
            </p>
          )}
          {feedbackVisible.status === "ready" && (
            <ReplayFeedbackForm
              // Remonta el formulario (y su estado interno de borrador) al
              // cambiar de predicción — nunca conserva un borrador de otra
              // selección (Paso 4.1 §1).
              key={`${selectedOrigin}|${simulatedDate}`}
              existing={feedbackVisible.entries}
              submitting={feedbackSubmitting}
              error={feedbackSubmitError}
              labelRule={candidate.regla_etiqueta}
              onSubmit={handleFeedbackSubmit}
            />
          )}
        </section>
      )}
    </div>
  );
}
