import type { CicytexProvenance, CicytexSession } from "./cicytexApi";

const METHODS: Array<[keyof CicytexProvenance["horizons"][string]["component_mlflow_runs"], string]> = [
  ["logistic_regression", "Logistic Regression"],
  ["random_forest", "Random Forest"],
  ["hist_gradient_boosting_classifier", "HistGradientBoosting"],
];

type Props = {
  session: CicytexSession;
  // `null` = aún sin respuesta o no disponible; nunca se inventan valores.
  provenance: CicytexProvenance | null;
  provenanceFailed: boolean;
};

/**
 * Trazabilidad de una predicción concreta: sólo hechos de la sesión (fuente,
 * emisión, objetivo) y del paquete archivado (identidad, corridas de modelos
 * congelados, particiones). No muestra métricas ni resultados, y declara
 * explícitamente lo que no existe (versión del modelo, linaje de recalibración).
 */
export function CicytexTraceability({ session, provenance, provenanceFailed }: Props) {
  const target = session.predictions.find((p) => p.method === "ensemble")?.target_date;
  const horizon = provenance?.horizons[String(session.horizon_days)];
  return (
    <section className="cy-panel cy-trace" aria-label="Trazabilidad de esta predicción">
      <h2>Trazabilidad de esta predicción</h2>
      <dl>
        <dt>Origen de los datos</dt>
        <dd>CICYTEX (datos externos), sonda {session.sensor_id}</dd>
        <dt>Emisión y objetivo</dt>
        <dd>
          Emitida el {session.emission_date} para el {target ?? "—"} (+{session.horizon_days} día
          {session.horizon_days > 1 ? "s" : ""})
        </dd>
      </dl>
      <details>
        <summary>Identidad del paquete y de los modelos</summary>
        {provenance && horizon ? (
          <dl>
            <dt>Dataset (SHA-256)</dt>
            <dd>
              <code>{provenance.dataset_sha256}</code>
            </dd>
            <dt>Commit de ejecución</dt>
            <dd>
              <code>{provenance.git_commit}</code> · semilla {provenance.seed}
            </dd>
            <dt>Política del ensamble</dt>
            <dd>{provenance.ensemble_policy}</dd>
            <dt>Particiones (hasta)</dt>
            <dd>
              entrenamiento {horizon.split.train_end} · calibración {horizon.split.calibration_end} · validación{" "}
              {horizon.split.validation_end}
            </dd>
            <dt>Corridas de modelos congelados (MLflow)</dt>
            <dd>
              <ul>
                {METHODS.map(([key, label]) => (
                  <li key={key}>
                    {label}: <code>{horizon.component_mlflow_runs[key]}</code>
                  </li>
                ))}
              </ul>
            </dd>
          </dl>
        ) : (
          <p role="status">
            {provenanceFailed
              ? "Trazabilidad del paquete no disponible."
              : provenance
                ? "Trazabilidad del paquete no disponible para este horizonte."
                : "Cargando trazabilidad del paquete…"}
          </p>
        )}
        <p>Versión del modelo: no disponible (los modelos están congelados por corrida).</p>
        <p>Linaje de recalibración: no disponible en este recorrido (no hay recalibración sobre modelos congelados).</p>
      </details>
    </section>
  );
}
