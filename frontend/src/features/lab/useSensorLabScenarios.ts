import { userFacingErrorMessage } from "../shared/errorMessage";
import { useLayoutEffect, useRef, useState } from "react";
import { getQualityReport } from "../quality/api";
import type { QualityReport } from "../quality/api";
import { addDaysUtc, labBackfillEndDateUtc } from "./labSensor";
import { generateNormalReading, injectRangeAnomaly, mulberry32 } from "./readingGenerator";
import type { LabReadingValues } from "./readingGenerator";
import { ingestLabReading } from "./sensorLabApi";

/** Semilla/configuración fija (escenarios reproducibles, sección 3 del
 * mandato). `LAB_HISTORY_DAYS` reutiliza el mismo tamaño de historial ya
 * verificado end-to-end contra el backend real en
 * `openspec/specs/demo-simulation/spec.md` (`history_days=120`), en vez
 * de adivinar un mínimo nuevo. */
export const LAB_SEED = 42;
export const LAB_HISTORY_DAYS = 120;
export const LAB_GAP_DAYS = 4;

export const LAB_ERROR_NO_LAST_READING =
  "No se pudo determinar la última lectura guardada. La recuperación se detuvo. Iniciá una sesión nueva.";

const LAB_ERROR_NO_QUALITY = "El backend no devolvió el informe de calidad de las lecturas guardadas.";

export type LabPhase =
  | "idle"
  | "seeding"
  | "normal"
  | "injecting-anomaly"
  | "anomaly"
  | "interrupting"
  | "interrupted"
  | "recovering"
  | "recovered"
  | "error";

export interface LabLogEntry {
  id: string;
  scenario: "A" | "B" | "C" | "D";
  message: string;
}

interface UseSensorLabScenariosOptions {
  /** Se dispara tras cada ingesta confirmada, para refrescar paneles de
   * solo lectura (p. ej. `QualityPanel`) sin acoplar este hook a ellos. */
  onIngested: () => void;
  /** Delegado al workspace de pronóstico ya existente
   * (`useForecastWorkspace`); este hook nunca llama al pipeline
   * directamente. */
  runForecast: () => Promise<void>;
}

export interface SensorLabScenarios {
  phase: LabPhase;
  busy: boolean;
  error: string | null;
  log: LabLogEntry[];
  clockDate: string | null;
  lastQuality: QualityReport | null;
  runScenarioA: () => Promise<void>;
  runScenarioB: () => Promise<void>;
  runScenarioC: () => Promise<void>;
  runScenarioD: () => Promise<void>;
}

/** Señal interna: la ejecución dejó de ser vigente (pantalla desmontada
 * o sesión reemplazada). No es un error de escenario y no se muestra. */
class StaleRun extends Error {}

interface RunContext {
  sensorId: string;
  /** Lanza `StaleRun` si la ejecución fue invalidada. Se invoca antes de
   * cada solicitud nueva y después de cada `await`. */
  ensure: () => void;
}

/**
 * Orquestación cliente del laboratorio (tercer modo de la UI de defensa):
 * un `sensor_id` propio por sesión, avance de escenarios A→B→C→D
 * mediante los endpoints reales de `alerting-ui`
 * (`POST /sensors/{id}/readings`, `GET /quality/{id}`,
 * `POST /forecast/{id}/run` vía `runForecast`), nunca un backend
 * paralelo.
 *
 * Ciclo de vida: cada ejecución captura una generación; desmontar la
 * pantalla o cambiar de `sensorId` la invalida. Una ejecución invalidada
 * no inicia solicitudes nuevas ni modifica el estado de la sesión
 * vigente. Cancelar en el cliente no revierte un POST ya enviado: si el
 * servidor lo recibió, sus datos se conservan.
 *
 * Reintentos: una sesión con error no admite nuevos pasos (evita
 * reenviar valores distintos para fechas ya aceptadas); la salida es una
 * sesión nueva con otro `sensor_id`, semilla y calendario reiniciados.
 */
export function useSensorLabScenarios(
  sensorId: string,
  options: UseSensorLabScenariosOptions,
): SensorLabScenarios {
  const generationRef = useRef(0);
  const runningRef = useRef(false);
  const phaseRef = useRef<LabPhase>("idle");
  const clockRef = useRef<string | null>(null);
  const rngRef = useRef(mulberry32(LAB_SEED));
  const prevValuesRef = useRef<LabReadingValues | null>(null);
  const optionsRef = useRef(options);
  useLayoutEffect(() => {
    optionsRef.current = options;
  });

  const [trackedSensorId, setTrackedSensorId] = useState(sensorId);
  const [phase, setPhaseState] = useState<LabPhase>("idle");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [log, setLog] = useState<LabLogEntry[]>([]);
  const [clockDate, setClockState] = useState<string | null>(null);
  const [lastQuality, setLastQuality] = useState<QualityReport | null>(null);

  if (sensorId !== trackedSensorId) {
    setTrackedSensorId(sensorId);
    setPhaseState("idle");
    setBusy(false);
    setError(null);
    setLog([]);
    setClockState(null);
    setLastQuality(null);
  }

  // Inicio de ciclo de vida (montaje o nuevo sensor): reinicia el estado
  // sincrónico. La limpieza (desmontaje o cambio de sensor) invalida toda
  // ejecución en curso. Bajo StrictMode, montaje→limpieza→montaje deja una
  // generación nueva y vigente antes de cualquier acción de la persona.
  useLayoutEffect(() => {
    generationRef.current += 1;
    runningRef.current = false;
    phaseRef.current = "idle";
    clockRef.current = null;
    rngRef.current = mulberry32(LAB_SEED);
    prevValuesRef.current = null;
    return () => {
      generationRef.current += 1;
      runningRef.current = false;
    };
  }, [sensorId]);

  function setPhase(next: LabPhase) {
    phaseRef.current = next;
    setPhaseState(next);
  }

  function setClock(next: string) {
    clockRef.current = next;
    setClockState(next);
  }

  function appendLog(scenario: LabLogEntry["scenario"], message: string) {
    setLog((prev) => [...prev, { id: `${scenario}-${prev.length}-${Date.now()}`, scenario, message }]);
  }

  async function withStep(
    required: LabPhase,
    nextPhase: LabPhase,
    action: (ctx: RunContext) => Promise<void>,
  ) {
    // Bloqueo síncrono (no depende del estado React `busy`) y orden A→B→C→D.
    if (runningRef.current || phaseRef.current !== required) return;
    runningRef.current = true;
    const generation = generationRef.current;
    const ctx: RunContext = {
      sensorId,
      ensure: () => {
        if (generationRef.current !== generation) throw new StaleRun();
      },
    };
    setBusy(true);
    setPhase(nextPhase);
    setError(null);
    try {
      await action(ctx);
    } catch (err) {
      if (!(err instanceof StaleRun) && generationRef.current === generation) {
        setError(userFacingErrorMessage(err));
        setPhase("error");
      }
    } finally {
      if (generationRef.current === generation) {
        runningRef.current = false;
        setBusy(false);
      }
    }
  }

  async function refreshQuality(ctx: RunContext, missingMessage = LAB_ERROR_NO_QUALITY): Promise<QualityReport> {
    ctx.ensure();
    const report = await getQualityReport(ctx.sensorId);
    ctx.ensure();
    if (report === null) throw new Error(missingMessage);
    setLastQuality(report);
    return report;
  }

  async function ingest(ctx: RunContext, isoDate: string, reading: LabReadingValues) {
    ctx.ensure();
    await ingestLabReading(ctx.sensorId, isoDate, reading);
    ctx.ensure();
    prevValuesRef.current = reading;
  }

  async function forecast(ctx: RunContext) {
    ctx.ensure();
    await optionsRef.current.runForecast();
    ctx.ensure();
  }

  async function runScenarioA() {
    await withStep("idle", "seeding", async (ctx) => {
      const endDate = labBackfillEndDateUtc();
      const startDate = addDaysUtc(endDate, -(LAB_HISTORY_DAYS - 1));
      let cursor = startDate;
      for (let i = 0; i < LAB_HISTORY_DAYS; i += 1) {
        const reading = generateNormalReading(prevValuesRef.current, rngRef.current);
        await ingest(ctx, cursor, reading);
        cursor = addDaysUtc(cursor, 1);
      }
      setClock(endDate);
      const report = await refreshQuality(ctx);
      optionsRef.current.onIngested();
      appendLog(
        "A",
        `Historial sintético cargado: ${report.total_rows} lecturas normales, del ${startDate} al ${endDate} (confirmado por GET /quality).`,
      );
      await forecast(ctx);
      setPhase("normal");
    });
  }

  async function runScenarioB() {
    await withStep("normal", "injecting-anomaly", async (ctx) => {
      const anomalyDate = addDaysUtc(clockRef.current as string, 1);
      const base = generateNormalReading(prevValuesRef.current, rngRef.current);
      const reading = injectRangeAnomaly(base);
      await ingest(ctx, anomalyDate, reading);
      setClock(anomalyDate);
      const report = await refreshQuality(ctx);
      optionsRef.current.onIngested();
      const flagged = report.out_of_range.temperature ?? [];
      const wasFlagged = flagged.some((d) => d.startsWith(anomalyDate));
      appendLog(
        "B",
        wasFlagged
          ? `Lectura del ${anomalyDate} marcada por el control de calidad: temperatura ${reading.temperature.toFixed(1)} °C fuera del rango físico esperado (motivo real: out_of_range.temperature de GET /quality). Es una anomalía de medición, no una alerta de estrés hídrico.`
          : `Lectura del ${anomalyDate} ingerida (temperatura ${reading.temperature.toFixed(1)} °C); el control de calidad no la marcó fuera de rango en esta consulta -- se muestra el resultado real devuelto, no el esperado.`,
      );
      await forecast(ctx);
      setPhase("anomaly");
    });
  }

  async function runScenarioC() {
    await withStep("anomaly", "interrupting", async (ctx) => {
      const interruptedThrough = addDaysUtc(clockRef.current as string, LAB_GAP_DAYS);
      setClock(interruptedThrough);
      const report = await refreshQuality(ctx);
      appendLog(
        "C",
        `Interrupción simulada: el generador dejó de enviar lecturas durante ${LAB_GAP_DAYS} días simulados (no se desconectó ningún dispositivo físico). El reloj simulado avanzó al ${interruptedThrough}, pero la última lectura guardada sigue siendo del ${report.period_end ?? "sin dato"} (${report.total_rows} filas totales, sin cambio). No se vuelve a pedir un pronóstico: no hay datos nuevos que lo sustenten.`,
      );
      setPhase("interrupted");
    });
  }

  async function runScenarioD() {
    await withStep("interrupted", "recovering", async (ctx) => {
      const before = await refreshQuality(ctx, LAB_ERROR_NO_LAST_READING);
      const lastConfirmed = before.period_end;
      if (!lastConfirmed) throw new Error(LAB_ERROR_NO_LAST_READING);
      let cursor = addDaysUtc(lastConfirmed, 1);
      const recoveryEnd = clockRef.current as string;
      while (cursor <= recoveryEnd) {
        const reading = generateNormalReading(prevValuesRef.current, rngRef.current);
        await ingest(ctx, cursor, reading);
        cursor = addDaysUtc(cursor, 1);
      }
      const report = await refreshQuality(ctx);
      optionsRef.current.onIngested();
      appendLog(
        "D",
        `Se generaron y enviaron lecturas sintéticas para las fechas pendientes hasta el ${report.period_end ?? "?"} (${report.total_rows} filas totales, confirmado por el backend).`,
      );
      await forecast(ctx);
      appendLog(
        "D",
        "Se solicitó un nuevo pronóstico; su resultado, o el motivo real si no pudo emitirse, se muestra más abajo.",
      );
      setPhase("recovered");
    });
  }

  return {
    phase,
    busy,
    error,
    log,
    clockDate,
    lastQuality,
    runScenarioA,
    runScenarioB,
    runScenarioC,
    runScenarioD,
  };
}
