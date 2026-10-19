import { useEffect, useState } from "react";
import { familyLabel } from "./forecastsApi";
import { getBatchProvenance } from "./provenanceApi";
import type { BatchProvenance, CodeIdentity } from "./provenanceApi";

type State =
  | { status: "loading"; key: string }
  | { status: "error"; key: string; message: string }
  | { status: "ready"; key: string; data: BatchProvenance };

const NOT_PERSISTED_LABELS: Record<BatchProvenance["not_persisted"][number], string> = {
  full_config: "Configuración completa",
  mlflow_run: "Corrida de MLflow",
  seed: "Semilla",
};

/** `null` = el bundle no registró `code_identity`: se declara, nunca se infiere del checkout actual. */
function CommitValue({ identity }: { identity: CodeIdentity | null }) {
  if (identity === null) return <>no registrado (el bundle no guardó la identidad del código)</>;
  if (!identity.available || identity.commit === null) return <>no disponible al entrenar (git no estaba accesible)</>;
  return (
    <>
      <code>{identity.commit}</code>
      {identity.dirty === null
        ? " · estado del árbol no registrado"
        : identity.dirty
          ? " · con cambios sin confirmar"
          : " · sin cambios locales"}
    </>
  );
}

/**
 * Procedencia de solo lectura de una emisión v2: sólo la lista blanca de
 * identidad que expone el backend (sha del dataset, referencia del modelo,
 * `code_identity` del entrenamiento). Lo que no se persiste se declara
 * "no disponible"; lo que un bundle antiguo no registró, "no registrado".
 */
export function EmissionProvenancePanel({ sensorId, batchId }: { sensorId: string; batchId: string }) {
  const key = `${sensorId}|${batchId}`;
  const [state, setState] = useState<State>({ status: "loading", key });
  const [retry, setRetry] = useState(0);

  useEffect(() => {
    // Una respuesta tardía de otro lote/intento nunca pisa el estado vigente.
    let cancelled = false;
    getBatchProvenance(sensorId, batchId).then(
      (data) => {
        if (!cancelled) setState({ status: "ready", key, data });
      },
      (error: unknown) => {
        if (!cancelled) {
          setState({ status: "error", key, message: error instanceof Error ? error.message : "Error desconocido." });
        }
      },
    );
    return () => {
      cancelled = true;
    };
  }, [sensorId, batchId, key, retry]);

  if (state.key !== key || state.status === "loading") {
    return <p role="status">Cargando procedencia de la emisión…</p>;
  }
  if (state.status === "error") {
    return (
      <p role="alert">
        No se pudo consultar la procedencia de la emisión: {state.message}{" "}
        <button type="button" onClick={() => { setState({ status: "loading", key }); setRetry((n) => n + 1); }}>Reintentar procedencia</button>
      </p>
    );
  }

  const { data } = state;
  return (
    <section className="historical-trace emission-provenance" role="region" aria-label="Procedencia de la emisión">
      <h3>Procedencia de la emisión</h3>
      <ul>
        <li>SHA-256 del dataset: <code>{data.snapshot_id}</code></li>
        {data.horizons.map((horizon) => (
          <li key={horizon.horizon_days}>
            Horizonte +{horizon.horizon_days}:{" "}
            {horizon.status === "unavailable" || horizon.model_reference === null ? (
              <>sin pronóstico emitido</>
            ) : (
              <ul>
                <li>Versión del modelo: {horizon.model_reference.model_version ?? "no disponible"}</li>
                <li>Entrenado hasta: {horizon.model_reference.trained_through ?? "no disponible"}</li>
                <li>Versión de calibración: {horizon.model_reference.calibration_version ?? "no disponible"}</li>
                {horizon.mode === "ensemble" ? (
                  <>
                    <li>Identidad del ensamble (SHA-256): {horizon.ensemble_identity_sha256 ? <code>{horizon.ensemble_identity_sha256}</code> : "no disponible"}</li>
                    {horizon.components.map((component) => (
                      <li key={component.family}>
                        {familyLabel(component.family)} · Commit: <CommitValue identity={component.code_identity} />
                      </li>
                    ))}
                  </>
                ) : (
                  <li>Commit: <CommitValue identity={horizon.code_identity} /></li>
                )}
              </ul>
            )}
          </li>
        ))}
        {data.not_persisted.map((field) => (
          <li key={field}>{NOT_PERSISTED_LABELS[field]}: no disponible (el backend no la persiste con la emisión)</li>
        ))}
      </ul>
    </section>
  );
}
