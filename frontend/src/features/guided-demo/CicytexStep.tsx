import { useEffect, useRef, useState } from "react";
import {
  advanceCicytexSession, createCicytexSession, getCicytexProvenance,
  type CicytexProvenance, type CicytexSession,
} from "../defense/cicytexApi";
import { ADVANCE_ERROR, Agreement, LOAD_ERROR, ResultRegion, SourceLine, StepError, TechDetails, TechFact, Traffic } from "./GuidedParts";

// Selección fija: la misma emisión congelada que abre por defecto el recorrido de CICYTEX.
const SENSOR = "CP1_S1";
const EMISSION = "2023-07-06";
const HORIZON = 1;

const fmt = (value: number) => value.toLocaleString("es-AR", { maximumFractionDigits: 3 });

type SessionState = { status: "loading" } | { status: "error" } | { status: "ready"; session: CicytexSession };
type ProvenanceState = { status: "loading" } | { status: "failed" } | { status: "ready"; data: CicytexProvenance };

export function CicytexStep() {
  const [state, setState] = useState<SessionState>({ status: "loading" });
  const [retry, setRetry] = useState(0);
  const [provenance, setProvenance] = useState<ProvenanceState>({ status: "loading" });
  const [busy, setBusy] = useState(false);
  const [advanceFailed, setAdvanceFailed] = useState(false);
  const resultRef = useRef<HTMLElement>(null);

  useEffect(() => {
    let cancelled = false;
    createCicytexSession(SENSOR, EMISSION, HORIZON).then(
      (session) => { if (!cancelled) setState({ status: "ready", session }); },
      () => { if (!cancelled) setState({ status: "error" }); },
    );
    return () => { cancelled = true; };
  }, [retry]);

  useEffect(() => {
    // La trazabilidad no bloquea el recorrido: si falla, se declara no disponible.
    let cancelled = false;
    getCicytexProvenance().then(
      (data) => { if (!cancelled) setProvenance({ status: "ready", data }); },
      () => { if (!cancelled) setProvenance({ status: "failed" }); },
    );
    return () => { cancelled = true; };
  }, []);

  const session = state.status === "ready" ? state.session : null;
  const ensemble = session?.predictions.find((p) => p.method === "ensemble");
  const members = session?.predictions.filter((p) => p.method !== "ensemble" && p.method !== "persistence") ?? [];
  const revealed = !!ensemble && ensemble.outcome !== null;

  useEffect(() => {
    if (revealed) resultRef.current?.focus();
  }, [revealed]);

  async function advance() {
    if (!session || busy) return;
    setBusy(true);
    setAdvanceFailed(false);
    try {
      const next = await advanceCicytexSession(session.session_id);
      setState({ status: "ready", session: next });
    } catch {
      setAdvanceFailed(true);
    } finally {
      setBusy(false);
    }
  }

  if (state.status === "error") {
    return <StepError message={LOAD_ERROR} onRetry={() => { setState({ status: "loading" }); setRetry((n) => n + 1); }} />;
  }
  if (!session || !ensemble) return <p role="status" className="gd-loading">Cargando este sitio…</p>;

  const lowMoisture = ensemble.observed_label === 1;
  const matched = ensemble.alert === lowMoisture;
  const provData = provenance.status === "ready" ? provenance.data : null;

  return (
    <>
      <div className="gd-decision" aria-live="polite">
        <Traffic alert={ensemble.alert} />
        <Agreement matching={members.filter((m) => m.alert === ensemble.alert).length} total={members.length} />
        <p className="gd-target">Pronóstico para el {ensemble.target_date}, emitido el {session.emission_date}.</p>
      </div>
      <SourceLine>
        datos externos de CICYTEX (tomate de industria, Talavera la Real), sonda {session.sensor_id}; emisión congelada del{" "}
        {session.emission_date}.
      </SourceLine>
      <div className="gd-actions">
        <button
          type="button"
          className="gd-btn gd-btn-primary"
          disabled={busy || revealed || !session.can_advance}
          onClick={() => void advance()}
        >
          Avanzar un día
        </button>
        {revealed && <p className="gd-note">Ya se mostró lo que ocurrió. Pasá al siguiente sitio.</p>}
      </div>
      {advanceFailed && <StepError message={ADVANCE_ERROR} onRetry={() => void advance()} />}
      {revealed && (
        <ResultRegion ref={resultRef}>
          <p>
            Humedad observada el {ensemble.target_date}:{" "}
            <strong>{ensemble.observed_soil_moisture === null ? "no disponible" : `${fmt(ensemble.observed_soil_moisture)} m³/m³`}</strong>
            {" "}(umbral de humedad baja: {fmt(session.threshold)}).
          </p>
          <p className="gd-outcome">
            <strong>{lowMoisture ? "Sí hubo humedad baja." : "No hubo humedad baja."}</strong>{" "}
            {matched ? "El pronóstico coincidió con lo observado." : "El pronóstico no coincidió con lo observado."}
          </p>
          <p className="gd-note">Es un solo día: sirve para ilustrar el recorrido, no para evaluar la herramienta.</p>
        </ResultRegion>
      )}
      <TechDetails>
        {provenance.status === "loading" ? <p role="status">Cargando trazabilidad…</p> : (
          <dl>
            <TechFact label="Dataset (SHA-256)" value={provData?.dataset_sha256} />
            <TechFact label="Commit de ejecución" value={provData?.git_commit} />
          </dl>
        )}
        <p>Versión del modelo y linaje de recalibración: no disponibles en este recorrido (modelos congelados).</p>
      </TechDetails>
    </>
  );
}
