import { useEffect, useRef, useState } from "react";
import { useForecastReviews } from "./useForecastReviews";
import {
  DemoWriteLockedError,
  ForecastNotFoundError,
  ReviewIdempotencyConflictError,
  ReviewNotOpenError,
  RevisionConflictError,
  TARGET_OBSERVATION_MESSAGES,
  TargetObservationBlockedError,
  agreementLabel,
  agreementVotesLabel,
  displayForecastDate,
  displayIssuedAt,
  displayProbability,
  familyLabel,
  getForecast,
  newRequestId,
  reviewStatusLabel,
  submitReview,
} from "./forecastsApi";
import type { Forecast, ReviewAction, ReviewBlockedReason, ReviewRequest, ForecastReview } from "./forecastsApi";

const HORIZON_LABELS: Record<1 | 2 | 3, string> = {
  1: "1 día después de la medición",
  2: "2 días después de la medición",
  3: "3 días después de la medición",
};

function reviewActionCopy(forecast: Forecast): Record<ReviewAction, string> {
  return forecast.alert
    ? {
        confirm: "Sí, hubo señales de falta de agua ese día.",
        reject: "No, el suelo no mostró falta de agua ese día.",
      }
    : {
        confirm: "Sí, no hubo falta de agua, tal como indicó el pronóstico.",
        reject: "No, sí hubo falta de agua aunque el pronóstico no alertó.",
      };
}

const ICON = { viewBox: "0 0 20 20", width: 18, height: 18, "aria-hidden": true, focusable: false } as const;
/** Íconos de señal: la señal nunca depende solo del color (alerta = triángulo, sin alerta = anillo). */
function AlertIcon() {
  return <svg {...ICON}><path d="M10 2.5 18.5 17h-17z" fill="currentColor" /><path d="M10 8v4.200M10 14.200v.6" stroke="#fff" strokeWidth="1.800" strokeLinecap="round" /></svg>;
}
function CalmIcon() {
  return <svg {...ICON}><circle cx="10" cy="10" r="7" fill="none" stroke="currentColor" strokeWidth="2.200" /></svg>;
}
function LockIcon() {
  return <svg {...ICON}><rect x="4.500" y="9" width="11" height="8" rx="1.500" fill="currentColor" /><path d="M7 9V6.500a3 3 0 0 1 6 0V9" fill="none" stroke="currentColor" strokeWidth="2" /></svg>;
}

interface Draft {
  action: ReviewAction;
  comment: string;
}

export function ForecastCard({
  sensorId,
  forecast: initialForecast,
  onChanged,
  submitReviewFn = submitReview,
  refetchFn = getForecast,
  historicalNotice,
}: {
  sensorId: string;
  forecast: Forecast;
  onChanged?: (forecast: Forecast) => void;
  /** Punto de extensión para el modo histórico: mismo componente, mismo
   * formulario y misma semántica confirmar/rechazar, pero dirigido a las
   * rutas `/historical/...` gateadas por el reloj del recorrido en vez del
   * reloj real de las rutas en vivo. */
  submitReviewFn?: (sensorId: string, forecastId: string, request: ReviewRequest) => Promise<ForecastReview>;
  refetchFn?: (sensorId: string, forecastId: string) => Promise<Forecast>;
  /** Mensaje fijo para modo histórico (p. ej. aclarar que la revisión queda
   * aislada de los procesos operativos), mostrado además del resto de los
   * mensajes de estado. */
  historicalNotice?: string;
}) {
  const [localForecast, setForecast] = useState(initialForecast);
  const { updates, publish } = useForecastReviews();
  const shared = updates[initialForecast.forecast_id];
  const candidates = [localForecast, initialForecast, ...(shared ? [shared] : [])];
  const forecast = candidates.reduce((latest, value) => value.review.revision >= latest.review.revision ? value : latest);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [requestId, setRequestId] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  // Rechazo 409 real del backend (el estado cambió entre la consulta y el POST):
  // bloquea esta revisión hasta que llegue un estado nuevo del pronóstico.
  // Guardia síncrona contra doble envío (el estado de React se actualiza luego del clic).
  const submittingRef = useRef(false);
  // Destino estable del foco cuando el control activo se deshabilita o desaparece.
  const [focusRequest, setFocusRequest] = useState<{ target: "pending" | "notice" | "prompt"; n: number } | null>(null);
  const pendingRef = useRef<HTMLParagraphElement>(null);
  const noticeRef = useRef<HTMLParagraphElement>(null);
  const promptRef = useRef<HTMLParagraphElement>(null);
  const [serverBlock, setServerBlock] = useState<{ reason: ReviewBlockedReason; review: ForecastReview } | null>(null);

  const review = forecast.review;
  const activeServerBlock = serverBlock !== null && serverBlock.review === review ? serverBlock.reason : null;
  const blockedReason: ReviewBlockedReason | null =
    activeServerBlock ?? (review.reviewable ? null : (review.blocked_reason ?? "review_not_open"));
  const reviewable = blockedReason === null;
  const observationMessage = blockedReason ? (TARGET_OBSERVATION_MESSAGES[blockedReason] ?? null) : null;
  const choiceHelpId = `review-choice-help-${initialForecast.forecast_id}`;
  const isCorrecting = review.status !== "pending";
  const frozen = submitting || formError !== null;

  function requestFocus(target: "pending" | "notice" | "prompt") {
    setFocusRequest((previous) => ({ target, n: (previous?.n ?? 0) + 1 }));
  }

  useEffect(() => {
    if (!focusRequest) return;
    const element = { pending: pendingRef, notice: noticeRef, prompt: promptRef }[focusRequest.target].current;
    element?.focus();
  }, [focusRequest]);

  function openForm(action: ReviewAction) {
    setNotice(null);
    setDraft({ action, comment: review.latest_review?.comment ?? "" });
    setRequestId(newRequestId());
    setFormError(null);
  }

  function cancel() {
    setDraft(null);
    setRequestId(null);
    setFormError(null);
    requestFocus("prompt");
  }

  async function submit() {
    // Se vuelve a comprobar aquí: no se confía solo en el atributo disabled.
    if (!draft || !requestId || submitting || submittingRef.current || !reviewable) return;
    submittingRef.current = true;
    setSubmitting(true);
    setFormError(null);
    requestFocus("pending");
    try {
      const updatedReview = await submitReviewFn(sensorId, forecast.forecast_id, {
        requestId,
        expectedRevision: review.revision,
        action: draft.action,
        comment: draft.comment.trim() ? draft.comment.trim() : null,
      });
      const updated = { ...forecast, review: updatedReview };
      setForecast(updated);
      setDraft(null);
      setRequestId(null);
      setSubmitting(false);
      setNotice(
        "Tu opinión quedó guardada. El pronóstico original se conserva. Los próximos resultados no cambian automáticamente.",
      );
      publish(updated);
      onChanged?.(updated);
      requestFocus("notice");
      return;
    } catch (error) {
      setSubmitting(false);
      if (error instanceof RevisionConflictError) {
        setDraft(null);
        setRequestId(null);
        setNotice("Se registró otra opinión mientras completabas este formulario.");
        try {
          const fresh = await refetchFn(sensorId, forecast.forecast_id);
          setForecast(fresh);
          setNotice("Se registró otra opinión. Ya estás viendo el resultado actualizado.");
          publish(fresh);
          onChanged?.(fresh);
        } catch {
          setNotice("No pudimos recuperar la última opinión. Recargá la página antes de volver a revisar este resultado.");
        }
        return;
      }
      if (error instanceof ReviewIdempotencyConflictError) {
        setDraft(null);
        setRequestId(null);
        setNotice("Ese envío ya se había usado con otro contenido. Iniciá la revisión de nuevo si hace falta.");
        return;
      }
      if (error instanceof TargetObservationBlockedError) {
        setRequestId(null);
        setFormError(null);
        setServerBlock({ reason: error.reason, review });
        return;
      }
      if (error instanceof DemoWriteLockedError) {
        setDraft(null);
        setRequestId(null);
        setNotice(error.message);
        return;
      }
      if (error instanceof ReviewNotOpenError) {
        setDraft(null);
        setRequestId(null);
        setNotice("Todavía no se puede revisar este resultado.");
        return;
      }
      if (error instanceof ForecastNotFoundError) {
        setDraft(null);
        setRequestId(null);
        setNotice(error.message);
        return;
      }
      // Error recuperable (red, servidor no disponible): se conserva el
      // formulario y el mismo request_id para no duplicar el envío al reintentar.
      setFormError(error instanceof Error ? error.message : "No se pudo enviar la revisión.");
    } finally {
      submittingRef.current = false;
    }
  }

  return (
    <article className={`forecast-card ${forecast.alert ? "forecast-card-alert" : "forecast-card-clear"}`} aria-label={`Pronóstico para el ${displayForecastDate(forecast.target_date)}`}>
      <header className="forecast-card-header">
        <div>
          <p className="forecast-card-target">{historicalNotice ? `+${forecast.horizon_days} · Objetivo: ${displayForecastDate(forecast.target_date)}` : displayForecastDate(forecast.target_date)}</p>
          <details className="forecast-card-details"><summary>Ver de cuándo son los datos</summary><p className="forecast-card-meta">
            {HORIZON_LABELS[forecast.horizon_days]} · Emitido el {displayIssuedAt(forecast.issued_at)} a partir de
            datos del {displayForecastDate(forecast.as_of_date)}
          </p></details>
        </div>
        <span className={`forecast-card-badge ${forecast.alert ? "is-alert" : "is-clear"}`}>
          {forecast.alert ? <AlertIcon /> : <CalmIcon />}
          {historicalNotice ? (forecast.alert ? "Alerta prevista" : "Sin alerta prevista") : (forecast.alert ? "Alerta" : "Sin alerta")}
        </span>
      </header>

      <p className="forecast-card-guidance">{forecast.alert ? "Puede haber falta de agua. Revisá cómo está el cultivo." : "No se anticipa una alerta para esta fecha. Seguí observando el cultivo."}</p>
      {historicalNotice && <p className="forecast-card-historical-notice">El resultado refiere al objetivo de baja humedad del protocolo; no es un diagnóstico agronómico validado. La ausencia de alerta no garantiza ausencia de estrés. La falta de datos tampoco equivale a ausencia de alerta.</p>}
      <p className="forecast-probability">{forecast.probability_status === "not_qualified" || forecast.display_probability === null ? "Probabilidad no disponible: todavía no hay un porcentaje respaldado para mostrar." : `Posibilidad de alerta: ${displayProbability(forecast)}`}</p>
      {forecast.ensemble && (
        <div className="forecast-card-agreement">
          <span className="forecast-pips" aria-hidden="true">
            {[0, 1, 2].map((index) => {
              const component = forecast.ensemble?.components[index];
              return <span key={index} className={`forecast-pip ${component === undefined ? "is-missing" : component.alert ? "is-on" : ""}`} />;
            })}
          </span>
          <p><strong>Acuerdo entre modelos:</strong> {forecast.ensemble.components.length === 3
            ? `${agreementLabel(forecast.ensemble)} (${agreementVotesLabel(forecast.ensemble)}).`
            : `${forecast.ensemble.components.length} de 3 modelos disponibles; el faltante no cuenta como voto negativo.`}</p>
          <details>
            <summary>Ver detalle por modelo</summary>
            <ul>
              {forecast.ensemble.components.map((component) => (
                <li key={component.family}>
                  {familyLabel(component.family)}: score {component.score.toFixed(3)} · {component.alert ? "indica alerta" : "no indica alerta"}
                </li>
              ))}
            </ul>
            {forecast.ensemble.components.length < 3 && <p>No disponibles: {(["logistic_regression", "random_forest", "hist_gradient_boosting_classifier"] as const)
              .filter((family) => !forecast.ensemble?.components.some((component) => component.family === family))
              .map(familyLabel).join(", ")}.</p>}
          </details>
        </div>
      )}
      {historicalNotice && !forecast.ensemble && <p>Detalle de los tres modelos no disponible en esta emisión.</p>}
      <p className={`forecast-card-review-status is-${review.status}`}>Revisión: {reviewStatusLabel(review.status)}</p>
      {historicalNotice && <p className="forecast-card-historical-notice">{historicalNotice}</p>}

      {review.latest_review && (
        <p className="forecast-card-latest-review">
          Registraste «{review.latest_review.action === "confirm" ? "Confirmar" : "Rechazar"}» el{" "}
          {displayIssuedAt(review.latest_review.reviewed_at)}
          {review.latest_review.comment ? `: "${review.latest_review.comment}"` : "."}
        </p>
      )}

      {notice && <p role="status" tabIndex={-1} ref={noticeRef}>{notice}</p>}

      {!reviewable && observationMessage && (
        <p className="forecast-card-blocked" role="status">
          <LockIcon />
          {observationMessage}
        </p>
      )}
      {!reviewable && !observationMessage && (
        <p className="forecast-card-blocked">
          <LockIcon />
          {review.blocked_reason === "review_not_open"
            ? `Vas a poder revisar este resultado a partir del ${displayIssuedAt(review.review_open_at)}.`
            : "Todavía no se puede revisar este resultado."}
        </p>
      )}

      {reviewable && !draft && (
        <div className="forecast-card-actions">
          <p ref={promptRef} tabIndex={-1}>¿Coincidió con lo que observaste?</p>
          <p className="forecast-card-hint" id={choiceHelpId}>
            Elegí una opción para continuar: Confirmar resultado indica que coincidió con lo que observaste; Rechazar
            resultado indica que no coincidió. Antes de guardar vas a poder revisar tu elección y agregar un comentario.
          </p>
          <div className="forecast-card-buttons">
            <button type="button" className="forecast-card-choice" aria-describedby={choiceHelpId} onClick={() => openForm("confirm")}>
              Confirmar resultado
            </button>
            <button type="button" className="forecast-card-choice" aria-describedby={choiceHelpId} onClick={() => openForm("reject")}>
              Rechazar resultado
            </button>
          </div>
          {isCorrecting && <p className="forecast-card-hint">Podés corregir tu opinión cuando quieras: no vence.</p>}
        </div>
      )}

      {draft && (
        <form
          className="forecast-card-form"
          onSubmit={(event) => {
            event.preventDefault();
            void submit();
          }}
        >
          <p>{historicalNotice
            ? (draft.action === "confirm" ? "Confirmo la decisión mostrada para este objetivo de humedad." : "Rechazo la decisión mostrada para este objetivo de humedad.")
            : reviewActionCopy(forecast)[draft.action]}</p>
          <label>
            Comentario (opcional)
            <textarea
              value={draft.comment}
              maxLength={2000}
              disabled={frozen}
              onChange={(event) => setDraft({ ...draft, comment: event.target.value })}
            />
          </label>
          <p role="status" tabIndex={-1} ref={pendingRef} className="forecast-card-pending">{submitting ? "Guardando tu opinión…" : ""}</p>
          {formError && (
            <p role="alert">
              {formError} El envío no se duplicará: al reintentar se usa la misma solicitud.
            </p>
          )}
          <div className="forecast-card-buttons">
            {formError ? (
              <button type="button" onClick={() => void submit()} disabled={submitting || !reviewable}>
                Reintentar
              </button>
            ) : (
              <button type="submit" disabled={submitting || !reviewable}>
                {submitting ? "Guardando…" : "Guardar opinión"}
              </button>
            )}
            <button type="button" onClick={cancel} disabled={submitting}>
              Cancelar
            </button>
          </div>
        </form>
      )}
    </article>
  );
}
