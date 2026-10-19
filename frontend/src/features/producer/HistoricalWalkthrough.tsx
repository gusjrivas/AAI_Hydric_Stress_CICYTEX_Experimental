import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import { ForecastCard } from "./ForecastCard";
import { HistoricalMoistureChart } from "./HistoricalMoistureChart";
import { EmissionProvenancePanel } from "./EmissionProvenancePanel";
import { FactsStrip } from "../shared/FactsStrip";
import { getHistoricalForecastBatch, getHistoricalReadings, submitHistoricalReview } from "./historicalApi";
import { agreementLabel, displayForecastDate, familyLabel, type Forecast, type ForecastBatch, type ReviewRequest } from "./forecastsApi";
import { displayDate, formatReadingValue, originLabel } from "./readingsApi";
import type { ReadingRow, ReadingsResult } from "./readingsApi";
import "./HistoricalWalkthrough.css";

type BatchState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; batch: ForecastBatch };

type ReadingsState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; data: ReadingsResult };

/**
 * Reproducción de solo lectura de emisiones ya persistidas. Nunca llama a
 * `emitForecasts` (POST de preparación): solo `GET .../historical/...`.
 *
 * Dos fechas, deliberadamente separadas y nunca fusionadas en una sola
 * etiqueta: `emissionDate` selecciona qué emisión mirar (por su propia
 * fecha de emisión, nunca por `target_date`); `revealedThrough` es el
 * reloj del recorrido -- hasta dónde se revelaron observaciones y hasta
 * dónde llegó la elegibilidad de revisión-- y puede avanzar más allá de
 * `emissionDate` sin cambiar la emisión seleccionada.
 */
const PERGAMINO_DATES = ["2023-06-13", "2023-06-14", "2023-06-15", "2023-06-16", "2023-06-17"];
const PERGAMINO_REVEAL_MAX = "2023-06-20";
const PERGAMINO_PROVENANCE_NOTICE = (
  <p className="historical-provenance">
    <strong>Origen: Pergamino · ERA5-Land/NASA POWER.</strong> Son datos externos, no mediciones de
    un sensor instalado ni observaciones agronómicas directas del cultivo. Hay emisiones del 13 al
    17 de junio de 2023.
  </p>
);
function addDays(iso: string, days: number): string {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, d + days)).toISOString().slice(0, 10);
}

/** «14 – 16 jun 2023» cuando el rango cae en el mismo mes; fechas completas en caso contrario. */
function displayDateRange(start: string, end: string): string {
  if (start.slice(0, 7) === end.slice(0, 7)) {
    const fullEnd = displayForecastDate(end);
    return `${Number(start.slice(8, 10))} – ${fullEnd.replace(/ de /g, " ")}`;
  }
  return `${displayForecastDate(start)} – ${displayForecastDate(end)}`;
}

/** Rótulo corto de la fuente para la franja de contexto: «Datos externos» no se confunde con «Histórico». */
export interface SourceSummary { label: string; detail: string }
const PERGAMINO_SOURCE: SourceSummary = { label: "Datos externos", detail: "ERA5-Land / NASA POWER (reanálisis)" };

const SLOT_UNAVAILABLE_REASONS: Record<string, string> = {
  already_available: "Este horizonte ya tenía un pronóstico emitido.",
  incompatible_environment: "El entorno de este servidor no puede ejecutar este pronóstico.",
  EnsembleManifestMissingError: "Todavía no hay un ensamble configurado para este horizonte.",
  EnsembleManifestInvalidError: "La configuración del ensamble para este horizonte no es válida.",
  EnsembleComponentMissingError: "Falta al menos un modelo del ensamble para este horizonte.",
  EnsembleBundleIncompatible: "Los modelos del ensamble no son compatibles entre sí para este horizonte.",
};

const QUALITY_VARIABLE_LABELS: Record<string, string> = {
  soil_moisture: "Humedad del suelo", temperature: "Temperatura", precipitation: "Precipitación",
  relative_humidity: "Humedad del aire", solar_radiation: "Radiación solar",
  wind_speed: "Velocidad del viento", et0: "Demanda de agua del ambiente (ET₀)",
};

const NO_SOURCE_OBSERVATION_LABEL = "Sin observación en la fuente";
const IMPUTED_VALUE_SUFFIX = "Valor imputado (completado a partir del último dato disponible, sin dato propio en la fuente para esta fecha). No es una observación independiente para contrastar con el pronóstico.";
const UNVERIFIED_VALUE_SUFFIX = "Procedencia del valor no verificada (no se pudo confirmar si es una observación real o un valor imputado). No es una observación independiente para contrastar con el pronóstico.";

/**
 * Humedad del suelo de una fila de lecturas, distinguiendo cuatro casos: sin
 * observación en la fuente (nunca se muestra un valor), observación real,
 * imputación (un valor SÍ se muestra, pero identificado explícitamente y
 * nunca presentado como una observación independiente contra la que
 * contrastar un pronóstico -- ver F01, `data_quality.imputation`), y
 * procedencia no verificada (un valor SÍ se muestra -- no se oculta que el
 * dato existe -- pero, al no poder confirmarse si es real o imputado, se
 * identifica explícitamente como no verificado y tampoco se cuenta como
 * observación independiente).
 */
function describeSoilMoistureObservation(row: ReadingRow | undefined, unit: string | undefined): string {
  if (!row || row.soil_moisture === null) return `${NO_SOURCE_OBSERVATION_LABEL}.`;
  const formatted = formatReadingValue("soil_moisture", row.soil_moisture, unit);
  if (row.imputed_variables.includes("soil_moisture")) {
    return `${formatted} · ${IMPUTED_VALUE_SUFFIX}`;
  }
  if (row.unverified_variables.includes("soil_moisture")) {
    return `${formatted} · ${UNVERIFIED_VALUE_SUFFIX}`;
  }
  return `${formatted} · ${originLabel(row.origin)}`;
}

/**
 * `availableDates`/`revealMax`/`provenanceNotice` generalize this component
 * to a second real historical-demonstration site (Melchor Romero) without
 * changing Pergamino's behavior: each defaults to Pergamino's own original
 * values, so any existing call site that omits them (as
 * `PergaminoDefensePage` still does) renders byte-identical output to
 * before this change.
 */
export function HistoricalWalkthrough({
  sensorId,
  defense = false,
  availableDates = PERGAMINO_DATES,
  revealMax = PERGAMINO_REVEAL_MAX,
  provenanceNotice = PERGAMINO_PROVENANCE_NOTICE,
  sourceSummary = PERGAMINO_SOURCE,
}: {
  sensorId: string;
  defense?: boolean;
  availableDates?: string[];
  revealMax?: string;
  provenanceNotice?: ReactNode;
  sourceSummary?: SourceSummary;
}) {
  const [emissionDate, setEmissionDate] = useState(defense ? availableDates[0] : "");
  const [revealedThrough, setRevealedThrough] = useState("");
  const effectiveReveal = revealedThrough || emissionDate;
  // Borrador del campo: mientras la persona edita por segmentos el navegador emite '' y el campo no debe saltar de vuelta
  // a la emisión; el borrador deja de valer apenas cambia el reloj efectivo.
  const [clockDraft, setClockDraft] = useState<{ value: string; base: string } | null>(null);
  // Un borrador obsoleto se descarta en cuanto el reloj efectivo cambia, para que A -> B -> A no lo reviva.
  if (clockDraft && clockDraft.base !== effectiveReveal) setClockDraft(null);
  const clockFieldValue = clockDraft && clockDraft.base === effectiveReveal ? clockDraft.value : effectiveReveal;
  const endNoteId = useId();
  const endNoteRef = useRef<HTMLParagraphElement | null>(null);
  const atEnd = effectiveReveal >= revealMax;
  // El botón primario se deshabilita al llegar al final y pierde el foco: se lo lleva a la nota que explica por qué.
  const wasAtEnd = useRef(atEnd);
  useEffect(() => {
    if (atEnd && !wasAtEnd.current) endNoteRef.current?.focus();
    wasAtEnd.current = atEnd;
  }, [atEnd]);

  // Cambiar de sensor (o de sitio) invalida cualquier selección anterior:
  // una fecha "preparada" para un sensor/sitio no significa nada para otro.
  useEffect(() => {
    setEmissionDate(defense ? availableDates[0] : "");
    setRevealedThrough("");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sensorId, defense, availableDates[0]]);

  const [batchState, setBatchState] = useState<BatchState & { context?: string }>({ status: "idle" });
  const [batchRetry, setBatchRetry] = useState(0);
  const batchSeq = useRef(0);
  const context = `${sensorId}|${emissionDate}|${effectiveReveal}`;
  useEffect(() => {
    // Se incrementa siempre, incluso al vaciar la selección: una
    // respuesta tardía de la selección anterior nunca debe poder
    // reemplazar el estado "idle" que corresponde a no tener nada
    // seleccionado.
    const seq = ++batchSeq.current;
    if (!emissionDate) {
      setBatchState({ status: "idle" });
      return;
    }
    setBatchState({ status: "loading", context });
    getHistoricalForecastBatch(sensorId, emissionDate, revealedThrough || undefined).then(
      (batch) => {
        if (batchSeq.current !== seq) return;
        setBatchState({ status: "ready", batch, context });
      },
      (error: Error) => {
        if (batchSeq.current !== seq) return;
        setBatchState({ status: "error", message: error.message, context });
      },
    );
  }, [sensorId, emissionDate, revealedThrough, context, batchRetry]);

  const [readingsState, setReadingsState] = useState<ReadingsState & { context?: string }>({ status: "idle" });
  const [readingsRetry, setReadingsRetry] = useState(0);
  const readingsSeq = useRef(0);
  useEffect(() => {
    const seq = ++readingsSeq.current;
    if (!effectiveReveal) {
      setReadingsState({ status: "idle" });
      return;
    }
    setReadingsState({ status: "loading", context });
    getHistoricalReadings(sensorId, effectiveReveal, 10).then(
      (data) => {
        if (readingsSeq.current !== seq) return;
        setReadingsState({ status: "ready", data, context });
      },
      (error: Error) => {
        if (readingsSeq.current !== seq) return;
        setReadingsState({ status: "error", message: error.message, context });
      },
    );
  }, [sensorId, effectiveReveal, context, readingsRetry]);

  // Generación del contexto vigente en este render: sensor, emisión y
  // reloj efectivo del recorrido, resumidos en el mismo contador que ya
  // invalida el lote (`batchSeq`) -- se incrementa ante cualquier cambio
  // de esos tres valores, incluida la selección vacía. Capturarlo aquí
  // (no adentro de `reviewed`) fija el valor vigente en el momento en que
  // se crean `reviewed`/`submitReviewFn`/`refetchFn` para las tarjetas
  // que se están mostrando ahora; si el usuario cambia de contexto
  // (incluso conservando la misma emisión, solo con otro reloj de
  // recorrido) antes de que una operación en curso resuelva, `batchSeq`
  // ya avanzó y esta generación queda obsoleta. Comparar únicamente
  // `forecast_id` no alcanza: una respuesta tardía sobre la *misma*
  // emisión pero bajo un reloj anterior lleva un `reviewable` calculado
  // para el reloj viejo, no para el vigente.
  const renderGeneration = batchSeq.current;

  function reviewed(updated: Forecast) {
    setBatchState((current) => {
      // La generación que originó esta actualización ya no es la
      // vigente: descartar el resultado de la pantalla, sin revertir lo
      // que ya se persistió en el backend (esto solo decide qué se
      // muestra, nunca deshace una escritura).
      if (batchSeq.current !== renderGeneration) return current;
      if (current.status !== "ready") return current;
      const stillDisplayed = current.batch.slots.some(
        (slot) => slot.status === "available" && slot.forecast_id === updated.forecast_id,
      );
      if (!stillDisplayed) return current;
      return {
        status: "ready",
        batch: {
          ...current.batch,
          slots: current.batch.slots.map((slot) =>
            slot.status === "available" && slot.forecast_id === updated.forecast_id
              ? { ...updated, status: "available" }
              : slot,
          ),
        },
      };
    });
  }

  const submitReviewFn = (sid: string, forecastId: string, request: ReviewRequest) =>
    submitHistoricalReview(sid, effectiveReveal, forecastId, request);

  // No hay una ruta histórica de "un solo pronóstico": ante un conflicto de
  // revisión se vuelve a pedir el lote completo y se toma el mismo
  // forecast_id, en vez de inventar una llamada que no existe.
  const refetchFn = async (sid: string, forecastId: string): Promise<Forecast> => {
    const fresh = await getHistoricalForecastBatch(sid, emissionDate, revealedThrough || undefined);
    const match = fresh.slots.find((slot) => slot.status === "available" && slot.forecast_id === forecastId);
    if (!match || match.status !== "available") throw new Error("No se pudo recuperar esta emisión histórica.");
    return match;
  };

  // Bajo el h1 de la pantalla de seguimiento el recorrido es un h2 (sin saltar niveles); fuera de él conserva h3/h4.
  const HeadingTop = defense ? "h2" : "h3";
  const HeadingSub = defense ? "h3" : "h4";
  const currentBatch = batchState.status === "ready" && batchState.context === context ? batchState.batch : null;
  const availableCount = currentBatch?.slots.filter((slot) => slot.status === "available").length ?? 0;
  const alertCount = currentBatch?.slots.filter((slot) => slot.status === "available" && slot.alert).length ?? 0;
  const currentReadings = readingsState.status === "ready" && readingsState.context === context ? readingsState.data : null;
  const variablesWithoutData = currentReadings?.variable_coverage.filter((item) => item.observed_days === 0).length ?? 0;
  const firstForecast = currentBatch?.slots.find((slot) => slot.status === "available");
  const emissionReading = currentReadings?.rows.find((row) => row.date === emissionDate);

  return (
    <section className="historical-walkthrough" aria-labelledby="historical-walkthrough-title">
      <HeadingTop id="historical-walkthrough-title">Recorrido histórico</HeadingTop>
      <p>Elegí una emisión guardada y avanzá el reloj para ver las observaciones posteriores y registrar tu revisión. Solo hay cinco emisiones preparadas; este recorrido no genera pronósticos nuevos.</p>

      {defense && emissionDate && (
        <FactsStrip facts={[
          { label: "Datos que se ven", value: sourceSummary.label, sub: sourceSummary.detail },
          { label: "Pronóstico emitido", value: displayForecastDate(emissionDate), sub: `con datos hasta el ${displayForecastDate(emissionDate)}` },
          { label: "Aplica para", value: displayDateRange(addDays(emissionDate, 1), addDays(emissionDate, 3)), sub: "horizontes +1, +2 y +3 días" },
          { label: "Reloj del recorrido", value: displayForecastDate(effectiveReveal), sub: "se revelan datos hasta esta fecha" },
        ]} />
      )}
      <div className="historical-walkthrough-controls">
        {defense && provenanceNotice}
        <label>
          Emisión seleccionada (cuándo se hizo el pronóstico)
          {defense ? <select value={emissionDate} onChange={(event) => { setEmissionDate(event.target.value); setRevealedThrough(""); }}>
            {availableDates.map((date) => <option key={date} value={date}>{displayForecastDate(date)}</option>)}
          </select> : <input
            type="date"
            value={emissionDate}
            onChange={(event) => {
              setEmissionDate(event.target.value);
              if (revealedThrough && revealedThrough < event.target.value) setRevealedThrough("");
            }}
          />}
        </label>
        <label>
          Recorrido hasta (qué observaciones y revisiones se revelan)
          <input
            type="date"
            value={clockFieldValue}
            min={emissionDate || undefined}
            max={defense ? revealMax : undefined}
            disabled={!emissionDate}
            onChange={(event) => {
              const value = event.target.value;
              if (defense && value && (value < emissionDate || value > revealMax)) return;
              setClockDraft({ value, base: value || emissionDate });
              setRevealedThrough(value);
            }}
          />
        </label>
      </div>
      {defense && emissionDate && (
        <div className="historical-clock-steps" role="group" aria-label="Avanzar el reloj del recorrido">
          <button type="button" className="historical-step-secondary" disabled={effectiveReveal <= emissionDate} onClick={() => { const next = addDays(effectiveReveal, -1); setRevealedThrough(next <= emissionDate ? "" : next); }}>‹ Día anterior</button>
          <button type="button" className="historical-step-primary" disabled={effectiveReveal >= revealMax} aria-describedby={atEnd ? endNoteId : undefined} onClick={() => setRevealedThrough(addDays(effectiveReveal, 1))}>Día siguiente ›</button>
          {atEnd && <p id={endNoteId} ref={endNoteRef} role="status" tabIndex={-1} className="historical-step-end-note">No quedan días por revelar en esta emisión.</p>}
        </div>
      )}
      {emissionDate && (
        <p className="historical-walkthrough-clock">
          Viendo la emisión del <strong>{displayForecastDate(emissionDate)}</strong>
          {" · "}Recorrido avanzado hasta el <strong>{displayForecastDate(effectiveReveal)}</strong>
        </p>
      )}
      {defense && <div className="historical-quality" aria-label="Procedencia y calidad de datos">
        <HeadingSub>1 · Procedencia y calidad de datos</HeadingSub>
        {readingsState.status === "ready" && readingsState.context === context
          ? <>
            <p>Fuente: <strong>{readingsState.data.provenance === "external_reanalysis" ? "ERA5-Land/NASA POWER (datos externos)" : readingsState.data.provenance}</strong>. Ventana: {displayDate(readingsState.data.window.start_date)} a {displayDate(readingsState.data.window.end_date)}.</p>
            <p><strong>{readingsState.data.window.expected_days} días esperados</strong> · <strong>{readingsState.data.missing_dates.length} {readingsState.data.missing_dates.length === 1 ? "fecha" : "fechas"} sin datos</strong> · <strong>{variablesWithoutData} {variablesWithoutData === 1 ? "variable" : "variables"} sin ningún dato en la ventana</strong>. Una fecha o variable faltante no se interpreta como ausencia de alerta.</p>
            {(() => {
              const soil = readingsState.data.variable_coverage.find((item) => item.variable === "soil_moisture");
              if (!soil) return null;
              const total = Math.max(1, soil.observed_days + soil.imputed_days + soil.unverified_days + soil.missing_days);
              return <div className="historical-coverage" role="group" aria-label="Cobertura de la humedad del suelo">
                <div className="historical-coverage-bar" aria-hidden="true">
                  <span className="is-observed" style={{ width: `${(soil.observed_days / total) * 100}%` }} />
                  <span className="is-imputed" style={{ width: `${(soil.imputed_days / total) * 100}%` }} />
                  <span className="is-unverified" style={{ width: `${(soil.unverified_days / total) * 100}%` }} />
                  <span className="is-missing" style={{ width: `${(soil.missing_days / total) * 100}%` }} />
                </div>
                <p className="historical-coverage-nums">Humedad del suelo en la ventana: <strong>{soil.observed_days} con dato</strong> · <strong>{soil.imputed_days} imputado{soil.imputed_days === 1 ? "" : "s"}</strong> · <strong>{soil.unverified_days} sin verificar</strong> · <strong>{soil.missing_days} sin dato</strong>.</p>
              </div>;
            })()}
            <details><summary>Ver disponibilidad por variable</summary><ul>{readingsState.data.variable_coverage.map((item) => <li key={item.variable}>{QUALITY_VARIABLE_LABELS[item.variable] ?? item.variable}: {item.observed_days} días con dato, {item.missing_days} sin dato{item.imputed_days > 0 ? `, ${item.imputed_days} imputado${item.imputed_days === 1 ? "" : "s"} (no cuenta como observación)` : ""}{item.unverified_days > 0 ? `, ${item.unverified_days} de procedencia no verificada (no cuenta como observación)` : ""}</li>)}</ul></details>
          </>
          : readingsState.status === "error" && readingsState.context === context
            ? <p role="alert">No se pudo consultar la disponibilidad: {readingsState.message} <button type="button" onClick={() => setReadingsRetry((n) => n + 1)}>Reintentar lecturas</button></p>
            : <p role="status">Cargando disponibilidad…</p>}
      </div>}

      {(batchState.status === "loading" || (emissionDate && batchState.context !== context)) && <p role="status">Cargando emisión histórica…</p>}
      {batchState.status === "error" && batchState.context === context && <p role="alert">No se pudo consultar la emisión: {batchState.message} <button type="button" onClick={() => setBatchRetry((n) => n + 1)}>Reintentar emisión</button></p>}
      {defense && currentBatch && <div className={`historical-decision-summary ${alertCount > 0 ? "is-alert" : ""}`}>
        <p className="producer-eyebrow">2 · Pronóstico de la emisión seleccionada</p>
        <strong>{availableCount === 0 ? "No hay pronósticos disponibles" : alertCount === 0 ? `Sin alerta prevista en ${availableCount} horizonte${availableCount === 1 ? "" : "s"} disponible${availableCount === 1 ? "" : "s"}` : `${alertCount} de ${availableCount} horizonte${availableCount === 1 ? "" : "s"} disponible${availableCount === 1 ? "" : "s"} con alerta prevista`}</strong>
        {firstForecast?.status === "available" && firstForecast.event_threshold.variable === "soil_moisture" && <p className="historical-humidity-context">
          Objetivo del protocolo: humedad del suelo inferior a <strong>{formatReadingValue("soil_moisture", firstForecast.event_threshold.value, firstForecast.event_threshold.unit)}</strong>.
          {currentReadings && <> Dato externo al emitir ({displayDate(emissionDate)}): <strong>{emissionReading?.soil_moisture == null ? "no disponible" : formatReadingValue("soil_moisture", emissionReading.soil_moisture, currentReadings.units.soil_moisture)}</strong>{emissionReading?.imputed_variables.includes("soil_moisture") ? " (imputado, sin dato propio en la fuente para esta fecha)" : emissionReading?.unverified_variables.includes("soil_moisture") ? " (procedencia no verificada)" : ""}.</>}
          {" "}El dato de humedad y los scores de los modelos son valores distintos.
        </p>}
        <p>Son decisiones entregadas por el backend para el objetivo de humedad del protocolo. “Sin alerta” no garantiza ausencia de estrés en el cultivo.</p>
      </div>}
      {defense && currentBatch && firstForecast?.status === "available" && firstForecast.ensemble && (() => {
        const ens = firstForecast.ensemble;
        const target = firstForecast.target_date;
        const revealed = target <= effectiveReveal;
        const targetRow = currentReadings?.rows.find((item) => item.date === target);
        return <>
          <div className={`historical-verdict ${ens.combined_alert ? "is-alert" : "is-clear"}`} role="group" aria-label="Veredicto del ensamble" aria-live="polite">
            <p className="historical-verdict-label">{ens.combined_alert ? "ALERTA DE HUMEDAD BAJA" : "SIN ALERTA DE HUMEDAD BAJA"}</p>
            <p>Horizonte +{firstForecast.horizon_days} · fecha objetivo: <strong>{displayForecastDate(target)}</strong></p>
            <p>Acuerdo entre modelos: {agreementLabel(ens)}</p>
            <p className="historical-verdict-reality">{revealed
              ? <><strong>Realidad revelada:</strong> {currentReadings ? describeSoilMoistureObservation(targetRow, currentReadings.units.soil_moisture) : "Cargando dato posterior…"}</>
              : "Realidad: todavía no disponible según el reloj del recorrido."}</p>
          </div>
          <section className="historical-trace" role="region" aria-label="Trazabilidad de la predicción mostrada">
            <HeadingSub>Trazabilidad de la predicción mostrada</HeadingSub>
            <ul>
              <li>Emisión: {displayForecastDate(firstForecast.as_of_date)} · Objetivo: {displayForecastDate(target)}</li>
              <li>Fuente de datos: {sourceSummary.label} · {sourceSummary.detail}</li>
              <li>Versión del modelo: {firstForecast.model_reference.model_version ?? "no disponible"}</li>
              <li>Entrenado hasta: {firstForecast.model_reference.trained_through ?? "no disponible"}</li>
              <li>Versión de calibración: {firstForecast.model_reference.calibration_version ?? "no disponible"} · calibrado hasta {ens.calibrated_through}</li>
              <li>Referencia de evaluación: {firstForecast.model_reference.assessment_reference ?? "no disponible"}</li>
              <li>Política del ensamble: {ens.policy_version}</li>
              <li>Identidad del ensamble (SHA-256): <code>{ens.ensemble_identity_sha256}</code></li>
              <li>Pesos: {Object.entries(ens.weights).map(([family, weight]) => `${family} ${weight}`).join(" · ")}</li>
              {ens.components.map((component) => (
                <li key={component.family}>{familyLabel(component.family)}: versión {component.model_reference.model_version ?? "no disponible"}, entrenado hasta {component.model_reference.trained_through ?? "no disponible"}, calibración {component.model_reference.calibration_version ?? "no disponible"}, evaluación {component.model_reference.assessment_reference ?? "no disponible"}</li>
              ))}
            </ul>
            <p>No disponible en este recorrido (el backend no lo expone):</p>
            <ul>
              <li>Particiones: no disponible</li>
              <li>Linaje de recalibración: no disponible</li>
            </ul>
          </section>
          <EmissionProvenancePanel sensorId={sensorId} batchId={firstForecast.batch_id} />
        </>;
      })()}
      {batchState.status === "ready" && batchState.context === context && (
        <ul className="forecast-list forecast-outlook-grid">
          {batchState.batch.slots.map((slot) => (
            <li key={`${context}|${slot.horizon_days}`}>
              {slot.status === "available" ? (
                <ForecastCard
                  sensorId={sensorId}
                  forecast={slot}
                  onChanged={reviewed}
                  submitReviewFn={submitReviewFn}
                  refetchFn={refetchFn}
                  historicalNotice="Revisión de prueba técnica en modo histórico: queda aislada del historial operativo real, no se incorpora a reentrenamiento ni recalibración."
                />
              ) : (
                <article className="forecast-card">
                  <HeadingSub>+{slot.horizon_days} · {slot.target_date ? displayForecastDate(slot.target_date) : "Fecha objetivo no disponible"}</HeadingSub>
                  <p><strong>Sin pronóstico disponible</strong></p>
                  <p>Motivo: {SLOT_UNAVAILABLE_REASONS[slot.reason_code.split(":")[0]] ?? "No se pudo usar el pronóstico de este día. Es necesario revisar su configuración."}</p>
                </article>
              )}
              {slot.target_date && <p className="historical-target-observation"><strong>Observación posterior:</strong> {slot.target_date > effectiveReveal
                ? "Todavía no disponible según el reloj del recorrido."
                : readingsState.status === "ready" && readingsState.context === context
                  ? describeSoilMoistureObservation(readingsState.data.rows.find((item) => item.date === slot.target_date), readingsState.data.units.soil_moisture)
                  : readingsState.status === "error" && readingsState.context === context
                    ? "No se pudo consultar la observación; reintentá las lecturas."
                    : "Cargando dato posterior…"}</p>}
            </li>
          ))}
        </ul>
      )}

      {effectiveReveal && (
        <div className="historical-walkthrough-observations">
          {defense && currentReadings && currentReadings.status === "ready" && (
            <HistoricalMoistureChart
              readings={currentReadings}
              emissionDate={emissionDate}
              revealedThrough={effectiveReveal}
              threshold={firstForecast?.status === "available" && firstForecast.event_threshold.variable === "soil_moisture" && firstForecast.event_threshold.unit === currentReadings.units.soil_moisture ? firstForecast.event_threshold.value : null}
            />
          )}
          <HeadingSub>Observaciones reveladas hasta el {displayForecastDate(effectiveReveal)}</HeadingSub>
          {(readingsState.status === "loading" || readingsState.context !== context) && <p role="status">Cargando observaciones…</p>}
          {readingsState.status === "error" && readingsState.context === context && <p role="alert">No se pudieron consultar las observaciones: {readingsState.message} <button type="button" onClick={() => setReadingsRetry((n) => n + 1)}>Reintentar lecturas</button></p>}
          {readingsState.status === "ready" && readingsState.context === context && (
            readingsState.data.status === "no_readings" ? (
              <p role="status">No hay observaciones reveladas hasta esta fecha.</p>
            ) : (
              <table>
                <thead><tr><th scope="col">Fecha</th><th scope="col">Humedad del suelo</th><th scope="col">Origen</th></tr></thead>
                <tbody>
                  {readingsState.data.rows.filter((row) => row.date <= effectiveReveal).map((row) => (
                    <tr key={row.date}>
                      <th scope="row">{displayDate(row.date)}</th>
                      <td>{row.soil_moisture === null ? NO_SOURCE_OBSERVATION_LABEL : formatReadingValue("soil_moisture", row.soil_moisture, readingsState.data.units.soil_moisture)}</td>
                      <td>{row.soil_moisture === null ? "—" : row.imputed_variables.includes("soil_moisture") ? `${originLabel(row.origin)} · Imputado (sin dato propio este día)` : row.unverified_variables.includes("soil_moisture") ? "Procedencia no verificada" : originLabel(row.origin)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )
          )}
          <p className="historical-walkthrough-note">
            Nunca se revelan observaciones posteriores a esta fecha, incluso si ya existen guardadas.
          </p>
        </div>
      )}
    </section>
  );
}
