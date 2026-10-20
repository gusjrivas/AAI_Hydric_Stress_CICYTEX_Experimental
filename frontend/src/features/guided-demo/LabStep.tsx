import { useEffect, useRef, useState } from "react";
import { useForecastWorkspace } from "../forecast/useForecastWorkspace";
import { makeLabSensorId } from "../lab/labSensor";
import { LAB_SEED, useSensorLabScenarios } from "../lab/useSensorLabScenarios";
import { displayForecastDate } from "../producer/forecastsApi";
import { ResultRegion, SourceLine, StepError, TechDetails, Traffic } from "./GuidedParts";

const LAB_ERROR = "No se pudo completar el paso simulado. Verificá la conexión con el servidor y empezá de nuevo con una sesión nueva.";

export function LabStep() {
  const [sensorId, setSensorId] = useState(() => makeLabSensorId());
  const workspace = useForecastWorkspace(sensorId);
  const lab = useSensorLabScenarios(sensorId, { onIngested: () => {}, runForecast: workspace.runForecast });
  const resultRef = useRef<HTMLElement>(null);

  const latest = workspace.rows[0] ?? null;
  const hasScenarioA = ["normal", "injecting-anomaly", "anomaly"].includes(lab.phase);
  const revealedB = lab.phase === "anomaly";
  const failed = lab.phase === "error" || (hasScenarioA && !latest && workspace.runError !== null);

  useEffect(() => {
    if (revealedB) resultRef.current?.focus();
  }, [revealedB]);

  const flagged = (lab.lastQuality?.out_of_range.temperature ?? []).length > 0;
  const generating = lab.phase === "seeding";

  return (
    <>
      <p className="gd-sim-badge" role="note">SIMULACIÓN · datos generados para la demostración · sin sensor físico conectado</p>
      {failed ? (
        <StepError message={LAB_ERROR} onRetry={() => setSensorId(makeLabSensorId())} />
      ) : (
        <>
          <div className="gd-decision" aria-live="polite">
            {hasScenarioA && latest ? (
              <>
                <Traffic alert={latest.alerta_generada === 1} />
                <p className="gd-agree">La comparación entre modelos no está disponible en el laboratorio.</p>
                <p className="gd-target">Escenario A (lecturas normales). Pronóstico con datos hasta el {displayForecastDate(latest.fecha)}.</p>
              </>
            ) : (
              <p className="gd-note">
                {generating
                  ? "Generando lecturas simuladas…"
                  : "Todavía no hay datos. Generá lecturas simuladas normales (escenario A) para ver el semáforo."}
              </p>
            )}
          </div>
          <SourceLine>datos sintéticos generados en el navegador para esta demostración; no hay un sensor físico ni un cultivo medido.</SourceLine>
          <div className="gd-actions">
            {lab.phase === "idle" || generating ? (
              <button type="button" className="gd-btn gd-btn-primary" disabled={lab.busy} onClick={() => void lab.runScenarioA()}>
                Generar datos simulados (escenario A)
              </button>
            ) : null}
            <button
              type="button"
              className="gd-btn gd-btn-primary"
              disabled={lab.phase !== "normal" || lab.busy}
              onClick={() => void lab.runScenarioB()}
            >
              Avanzar un día
            </button>
            {revealedB && <p className="gd-note">Ya se mostró lo que ocurrió. Podés terminar el recorrido.</p>}
          </div>
          {revealedB && (
            <ResultRegion ref={resultRef}>
              <p>
                <strong>Escenario B: anomalía de medición.</strong> Al día simulado siguiente se envió, a propósito, una temperatura
                imposible. {flagged ? "El control de calidad la marcó como fuera de rango." : "El control de calidad no la marcó en esta consulta."}
              </p>
              <p className="gd-outcome">Es un problema de la medición, no es humedad baja ni una alerta de estrés hídrico.</p>
              <p className="gd-note">Aquí no se evalúa la humedad: solo se muestra cómo reacciona el sistema ante un dato defectuoso.</p>
            </ResultRegion>
          )}
        </>
      )}
      <TechDetails>
        <dl>
          <dt>Punto de medición simulado</dt>
          <dd><code>{sensorId}</code></dd>
          <dt>Semilla del generador</dt>
          <dd>{LAB_SEED}</dd>
          <dt>Commit</dt>
          <dd>no disponible en este recorrido</dd>
          <dt>Dataset (SHA-256)</dt>
          <dd>no disponible en este recorrido (datos sintéticos)</dd>
        </dl>
      </TechDetails>
    </>
  );
}
