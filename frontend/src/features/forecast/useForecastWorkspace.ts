import { userFacingErrorMessage } from "../shared/errorMessage";
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import {
  HttpError,
  confirmAlert,
  listFeedback,
  recalibrate as recalibrateApi,
  rejectAlert,
  runForecast as runForecastApi,
} from "./api";
import type { FeedbackRow, RecalibrationResponse, Verdict } from "./api";

export type HistoryStatus = "loading" | "ready" | "empty" | "error";
export type MutationKind = "forecast" | "recalibrate" | `confirm:${string}` | `reject:${string}`;

export interface ForecastWorkspace {
  historyStatus: HistoryStatus;
  historyError: string | null;
  rows: FeedbackRow[];
  refreshPending: boolean;
  activeMutation: MutationKind | null;
  rowErrors: Record<string, string>;
  actionMessage: string | null;
  runError: string | null;
  recalibrateError: string | null;
  runForecast: () => Promise<void>;
  confirm: (fecha: string) => Promise<boolean>;
  reject: (fecha: string, etiquetaCorregida: 0 | 1, observacion: string) => Promise<boolean>;
  recalibrate: () => Promise<RecalibrationResponse | null>;
  reloadHistory: () => Promise<void>;
  notify: (message: string) => void;
}

function sortDesc(rows: FeedbackRow[]): FeedbackRow[] {
  return [...rows].sort((a, b) => (a.fecha < b.fecha ? 1 : a.fecha > b.fecha ? -1 : 0));
}

/** Resultado de generar un pronóstico, dicho con claridad: hay un pronóstico por día y no se reemplaza el ya emitido. */
function describeRun(verdicts: Verdict[], added: Verdict[]): string {
  const latest = [...verdicts].sort((a, b) => b.fecha.localeCompare(a.fecha))[0];
  if (!latest) return "";
  if (added.length > 0) {
    const day = [...added].sort((a, b) => b.fecha.localeCompare(a.fecha))[0];
    return `Se agregó el pronóstico con datos hasta el ${day.fecha}${day.fecha_objetivo ? ` (para el ${day.fecha_objetivo})` : ""}.`;
  }
  return `Se usó la última fecha con datos (${latest.fecha}) y su pronóstico ya estaba emitido: no se agregaron días nuevos. Para obtener otro hacen falta mediciones más recientes.`;
}

function upsertVerdicts(rows: FeedbackRow[], verdicts: Verdict[]): FeedbackRow[] {
  const byFecha = new Map(rows.map((row) => [row.fecha, row]));
  for (const verdict of verdicts) {
    const existing = byFecha.get(verdict.fecha);
    byFecha.set(verdict.fecha, {
      fecha: verdict.fecha,
      alerta_generada: verdict.alerta ? 1 : 0,
      estado_validacion: existing?.estado_validacion ?? "pendiente",
      etiqueta_corregida: existing?.etiqueta_corregida ?? null,
      observacion: existing?.observacion ?? null,
      y_proba: verdict.probabilidad,
      fecha_objetivo: verdict.fecha_objetivo ?? existing?.fecha_objetivo ?? null,
    });
  }
  return sortDesc(Array.from(byFecha.values()));
}

/**
 * Historial y operaciones compartidos de un sensor (tasks 1.2-1.4 de
 * improve-alerting-ui-decision-workflow): una sola escritura en curso a la
 * vez, descarte de respuestas de un sensor que ya no está activo, y
 * reconciliación por fecha entre un POST exitoso y su GET de refresco.
 */
export function useForecastWorkspace(sensorId: string): ForecastWorkspace {
  const sensorRef = useRef(sensorId);
  const activeMutationRef = useRef<MutationKind | null>(null);

  const [trackedSensorId, setTrackedSensorId] = useState(sensorId);
  const [historyStatus, setHistoryStatus] = useState<HistoryStatus>("loading");
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [rows, setRows] = useState<FeedbackRow[]>([]);
  const rowsRef = useRef<FeedbackRow[]>([]);
  useEffect(() => {
    rowsRef.current = rows;
  }, [rows]);
  const [refreshPending, setRefreshPending] = useState(false);
  const [activeMutation, setActiveMutation] = useState<MutationKind | null>(null);
  const [rowErrors, setRowErrors] = useState<Record<string, string>>({});
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [runError, setRunError] = useState<string | null>(null);
  const [recalibrateError, setRecalibrateError] = useState<string | null>(null);

  if (sensorId !== trackedSensorId) {
    setTrackedSensorId(sensorId);
    setActiveMutation(null);
    setRows([]);
    setRowErrors({});
    setActionMessage(null);
    setRunError(null);
    setRecalibrateError(null);
    setRefreshPending(false);
    setHistoryStatus("loading");
    setHistoryError(null);
  }

  // Los refs (no reactivos) se sincronizan aparte del estado, para no
  // mutarlos durante el render.
  useLayoutEffect(() => {
    sensorRef.current = sensorId;
    activeMutationRef.current = null;
  }, [sensorId]);

  const performReload = useCallback(
    async (targetSensorId: string, opts: { silent?: boolean } = {}) => {
      try {
        const result = await listFeedback(targetSensorId);
        if (sensorRef.current !== targetSensorId) return;
        const sorted = sortDesc(result.rows);
        setRows(sorted);
        setHistoryStatus(sorted.length === 0 ? "empty" : "ready");
        setRefreshPending(false);
      } catch (err) {
        if (sensorRef.current !== targetSensorId) return;
        if (err instanceof HttpError && err.status === 404) {
          if (!opts.silent) {
            setRows([]);
            setHistoryStatus("empty");
          }
          return;
        }
        if (!opts.silent) {
          setHistoryStatus("error");
          setHistoryError(userFacingErrorMessage(err));
        }
        throw err;
      }
    },
    [],
  );

  useEffect(() => {
    listFeedback(sensorId)
      .then((result) => {
        if (sensorRef.current !== sensorId) return;
        const sorted = sortDesc(result.rows);
        setRows(sorted);
        setHistoryStatus(sorted.length === 0 ? "empty" : "ready");
        setRefreshPending(false);
      })
      .catch((err) => {
        if (sensorRef.current !== sensorId) return;
        if (err instanceof HttpError && err.status === 404) {
          setRows([]);
          setHistoryStatus("empty");
          return;
        }
        setHistoryStatus("error");
        setHistoryError(userFacingErrorMessage(err));
      });
  }, [sensorId]);

  function tryLock(kind: MutationKind): boolean {
    if (activeMutationRef.current !== null) return false;
    activeMutationRef.current = kind;
    setActiveMutation(kind);
    return true;
  }

  function unlock(sensorAtCall: string) {
    if (sensorRef.current !== sensorAtCall) return;
    activeMutationRef.current = null;
    setActiveMutation(null);
  }

  const runForecast = useCallback(async () => {
    const sensorAtCall = sensorId;
    if (!tryLock("forecast")) return;
    setRunError(null);
    try {
      const result = await runForecastApi(sensorAtCall);
      if (sensorRef.current !== sensorAtCall) return;
      const knownDates = new Set(rowsRef.current.map((row) => row.fecha));
      const added = result.verdicts.filter((verdict) => !knownDates.has(verdict.fecha));
      setRows((prev) => upsertVerdicts(prev, result.verdicts));
      setHistoryStatus("ready");
      setActionMessage(
        [describeRun(result.verdicts, added), result.selection_warning].filter(Boolean).join(" ") || null,
      );
      try {
        await performReload(sensorAtCall, { silent: true });
      } catch {
        if (sensorRef.current === sensorAtCall) setRefreshPending(true);
      }
    } catch (err) {
      if (sensorRef.current !== sensorAtCall) return;
      if (err instanceof HttpError) {
        setRunError(err.message);
      } else {
        setRunError(
          "No se pudo confirmar si el pronóstico se ejecutó. Consultá el historial antes de repetir la operación.",
        );
        setRefreshPending(true);
      }
    } finally {
      unlock(sensorAtCall);
    }
  }, [sensorId, performReload]);

  const confirm = useCallback(
    async (fecha: string): Promise<boolean> => {
      const sensorAtCall = sensorId;
      if (!tryLock(`confirm:${fecha}`)) return false;
      setRowErrors((prev) => {
        if (!(fecha in prev)) return prev;
        const next = { ...prev };
        delete next[fecha];
        return next;
      });
      try {
        const updated = await confirmAlert(sensorAtCall, fecha);
        if (sensorRef.current !== sensorAtCall) return false;
        setRows((prev) => prev.map((row) => (row.fecha === fecha ? updated : row)));
        setActionMessage(`Validación guardada del ${fecha} — los próximos pronósticos todavía no usan esta observación.`);
        return true;
      } catch (err) {
        if (sensorRef.current !== sensorAtCall) return false;
        setRowErrors((prev) => ({ ...prev, [fecha]: userFacingErrorMessage(err) }));
        return false;
      } finally {
        unlock(sensorAtCall);
      }
    },
    [sensorId],
  );

  const reject = useCallback(
    async (fecha: string, etiquetaCorregida: 0 | 1, observacion: string): Promise<boolean> => {
      const sensorAtCall = sensorId;
      if (!tryLock(`reject:${fecha}`)) return false;
      setRowErrors((prev) => {
        if (!(fecha in prev)) return prev;
        const next = { ...prev };
        delete next[fecha];
        return next;
      });
      try {
        const updated = await rejectAlert(sensorAtCall, fecha, etiquetaCorregida, observacion);
        if (sensorRef.current !== sensorAtCall) return false;
        setRows((prev) => prev.map((row) => (row.fecha === fecha ? updated : row)));
        setActionMessage(`Validación guardada del ${fecha} — los próximos pronósticos todavía no usan esta observación.`);
        return true;
      } catch (err) {
        if (sensorRef.current !== sensorAtCall) return false;
        setRowErrors((prev) => ({ ...prev, [fecha]: userFacingErrorMessage(err) }));
        return false;
      } finally {
        unlock(sensorAtCall);
      }
    },
    [sensorId],
  );

  const recalibrate = useCallback(async (): Promise<RecalibrationResponse | null> => {
    const sensorAtCall = sensorId;
    if (!tryLock("recalibrate")) return null;
    setRecalibrateError(null);
    try {
      const result = await recalibrateApi(sensorAtCall);
      if (sensorRef.current !== sensorAtCall) return null;
      return result;
    } catch (err) {
      if (sensorRef.current === sensorAtCall) {
        setRecalibrateError(userFacingErrorMessage(err));
      }
      return null;
    } finally {
      unlock(sensorAtCall);
    }
  }, [sensorId]);

  const reloadHistory = useCallback(async () => {
    setHistoryStatus("loading");
    setHistoryError(null);
    try {
      await performReload(sensorRef.current, { silent: false });
    } catch {
      // el estado de error ya quedó reflejado por performReload
    }
  }, [performReload]);

  const notify = useCallback((message: string) => setActionMessage(message), []);

  return {
    historyStatus,
    historyError,
    rows,
    refreshPending,
    activeMutation,
    rowErrors,
    actionMessage,
    runError,
    recalibrateError,
    runForecast,
    confirm,
    reject,
    recalibrate,
    reloadHistory,
    notify,
  };
}
