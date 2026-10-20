import { useEffect, useRef, useState } from "react";
import { getHistoricalForecastBatch, getHistoricalReadings } from "../producer/historicalApi";
import { displayForecastDate, type Forecast, type ForecastBatch } from "../producer/forecastsApi";
import { formatReadingValue, type ReadingsResult } from "../producer/readingsApi";
import { EmissionProvenancePanel } from "../producer/EmissionProvenancePanel";
import { ADVANCE_ERROR, Agreement, LOAD_ERROR, ResultRegion, SourceLine, StepError, TechDetails, Traffic } from "./GuidedParts";

export interface ProducerSite {
  sensorId: string;
  /** Fecha de emisión guardada que recorre el paso (la primera preparada del sitio). */
  emission: string;
  /** Qué dato se ve y de dónde proviene, dicho en una línea. */
  source: string;
}

type AvailableSlot = Forecast & { status: "available" };
type BatchState = { status: "loading" } | { status: "error" } | { status: "ready"; batch: ForecastBatch };
type ObsState = { status: "idle" } | { status: "loading" } | { status: "error" } | { status: "ready"; data: ReadingsResult };

/** Observación del día objetivo: solo se concluye "hubo / no hubo humedad baja" con una observación independiente. */
function describeObservation(data: ReadingsResult, slot: AvailableSlot): { line: string; verdict: string | null; low: boolean | null } {
  const row = data.rows.find((r) => r.date === slot.target_date);
  const day = displayForecastDate(slot.target_date);
  if (!row || row.soil_moisture === null) {
    return { line: `Sin observación en la fuente para el ${day}.`, verdict: "No se puede decir si hubo humedad baja.", low: null };
  }
  const value = formatReadingValue("soil_moisture", row.soil_moisture, data.units.soil_moisture);
  if (row.imputed_variables.includes("soil_moisture") || row.unverified_variables.includes("soil_moisture")) {
    return {
      line: `Valor registrado el ${day}: ${value}.`,
      verdict: "Ese valor fue completado o no se pudo verificar: no es una observación independiente, así que no se concluye si hubo humedad baja.",
      low: null,
    };
  }
  const threshold = formatReadingValue("soil_moisture", slot.event_threshold.value, slot.event_threshold.unit);
  const low = row.soil_moisture < slot.event_threshold.value;
  return {
    line: `Humedad observada el ${day}: ${value} (umbral de humedad baja: ${threshold}).`,
    verdict: low ? "Sí hubo humedad baja." : "No hubo humedad baja.",
    low,
  };
}

export function ProducerStep({ site }: { site: ProducerSite }) {
  const [state, setState] = useState<BatchState>({ status: "loading" });
  const [retry, setRetry] = useState(0);
  const [obs, setObs] = useState<ObsState>({ status: "idle" });
  const resultRef = useRef<HTMLElement>(null);

  useEffect(() => {
    let cancelled = false;
    getHistoricalForecastBatch(site.sensorId, site.emission).then(
      (batch) => { if (!cancelled) setState({ status: "ready", batch }); },
      () => { if (!cancelled) setState({ status: "error" }); },
    );
    return () => { cancelled = true; };
  }, [site.sensorId, site.emission, retry]);

  const batch = state.status === "ready" ? state.batch : null;
  const slot = batch?.slots.find((s): s is AvailableSlot => s.status === "available" && s.horizon_days === 1) ?? null;
  const targetDate = slot?.target_date ?? null;

  function advance() {
    if (!targetDate || obs.status === "loading") return;
    setObs({ status: "loading" });
    // El reloj avanza hasta el día objetivo: solo entonces se piden las observaciones hasta esa fecha.
    getHistoricalReadings(site.sensorId, targetDate, 10).then(
      (data) => setObs({ status: "ready", data }),
      () => setObs({ status: "error" }),
    );
  }

  const revealed = obs.status === "ready";
  useEffect(() => {
    if (revealed) resultRef.current?.focus();
  }, [revealed]);

  if (state.status === "error") {
    return <StepError message={LOAD_ERROR} onRetry={() => { setState({ status: "loading" }); setRetry((n) => n + 1); }} />;
  }
  if (!batch) return <p role="status" className="gd-loading">Cargando este sitio…</p>;
  if (!slot) {
    return <p className="gd-note">Esta emisión no tiene un pronóstico disponible para el día siguiente, así que no hay nada que mostrar en este paso.</p>;
  }

  const alert = slot.ensemble ? slot.ensemble.combined_alert : slot.alert;
  const components = slot.ensemble?.components ?? [];
  const observation = obs.status === "ready" ? describeObservation(obs.data, slot) : null;

  return (
    <>
      <div className="gd-decision" aria-live="polite">
        <Traffic alert={alert} />
        {components.length > 0
          ? <Agreement matching={components.filter((c) => c.alert === alert).length} total={components.length} />
          : <p className="gd-agree">La comparación entre modelos no está disponible para esta emisión.</p>}
        <p className="gd-target">Pronóstico para el {displayForecastDate(slot.target_date)}, emitido el {displayForecastDate(site.emission)}.</p>
      </div>
      <SourceLine>{site.source} Emisión guardada del {displayForecastDate(site.emission)}.</SourceLine>
      <div className="gd-actions">
        <button type="button" className="gd-btn gd-btn-primary" disabled={obs.status === "loading" || revealed} onClick={advance}>
          Avanzar un día
        </button>
        {obs.status === "loading" && <p role="status" className="gd-note">Buscando lo observado…</p>}
        {revealed && <p className="gd-note">Ya se mostró lo que ocurrió. Pasá al siguiente sitio.</p>}
      </div>
      {obs.status === "error" && <StepError message={ADVANCE_ERROR} onRetry={advance} />}
      {observation && (
        <ResultRegion ref={resultRef}>
          <p>{observation.line}</p>
          <p className="gd-outcome">
            {observation.verdict}
            {observation.low !== null && (alert === observation.low ? " El pronóstico coincidió con lo observado." : " El pronóstico no coincidió con lo observado.")}
          </p>
          <p className="gd-note">Es un solo día: sirve para ilustrar el recorrido, no para evaluar la herramienta.</p>
        </ResultRegion>
      )}
      <TechDetails>
        <EmissionProvenancePanel sensorId={site.sensorId} batchId={batch.batch_id} />
      </TechDetails>
    </>
  );
}
