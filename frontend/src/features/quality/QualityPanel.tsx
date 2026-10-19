import { userFacingErrorMessage } from "../shared/errorMessage";
import { NoReadingsHint } from "../shared/NoReadingsHint";
import { useEffect, useState } from "react";
import "./QualityPanel.css";
import { getQualityReport } from "./api";
import type { QualityReport } from "./api";

type Status = "loading" | "empty" | "error" | "ready";

const VARIABLE_LABELS: Record<string, string> = {
  soil_moisture: "Humedad del suelo",
  temperature: "Temperatura",
  relative_humidity: "Humedad del aire",
  precipitation: "Lluvia",
  solar_radiation: "Radiación solar",
  wind_speed: "Velocidad del viento",
  et0: "Demanda de agua del ambiente (ET₀)",
};

export function QualityPanel({
  sensorId,
  refreshToken = 0,
}: {
  sensorId: string;
  /** Fuerza un nuevo GET sin cambiar de sensor: usado para refrescar la
   * calidad del sensor de demo cuando avanza una fecha confirmada
   * (requerimiento "Refresco por progreso confirmado"). */
  refreshToken?: number;
}) {
  const requestKey = `${sensorId}:${refreshToken}`;
  const [loadedFor, setLoadedFor] = useState(requestKey);
  const [status, setStatus] = useState<Status>("loading");
  const [report, setReport] = useState<QualityReport | null>(null);
  const [error, setError] = useState<string | null>(null);

  if (requestKey !== loadedFor) {
    setLoadedFor(requestKey);
    setStatus("loading");
    setReport(null);
    setError(null);
  }

  useEffect(() => {
    let cancelled = false;
    getQualityReport(sensorId)
      .then((result) => {
        if (cancelled) return;
        if (result === null) {
          setStatus("empty");
          return;
        }
        setReport(result);
        setStatus("ready");
      })
      .catch((err) => {
        if (cancelled) return;
        setError(userFacingErrorMessage(err));
        setStatus("error");
      });
    return () => {
      cancelled = true;
    };
  }, [sensorId, refreshToken]);

  if (status === "loading") {
    return (
      <p role="status" className="qp-status">
        Cargando calidad de datos del sensor…
      </p>
    );
  }

  if (status === "empty") {
    return (
      <>
      <p role="status" className="qp-status">
        Todavía no hay mediciones cargadas para «{sensorId}». Se necesitan datos antes
        de poder generar un pronóstico.
      </p>
      <NoReadingsHint />
      </>
    );
  }

  if (status === "error") {
    return (
      <p role="alert" className="qp-error">
        {error}
      </p>
    );
  }

  const variables = Object.keys(report!.missing_pct);
  const outOfRangeTotal = Object.values(report!.out_of_range).reduce(
    (sum, dates) => sum + dates.length,
    0,
  );

  return (
    <div className="qp-panel">
      <p>Revisá qué datos hay y si faltan mediciones. Un valor inusual puede ser un cambio real del tiempo o del suelo, no necesariamente un error.</p>
      <dl className="qp-summary">
        <div>
          <dt>Período disponible</dt>
          <dd>
            {report!.period_start} → {report!.period_end} ({report!.total_rows} registros)
          </dd>
        </div>
        <div>
          <dt>Fechas repetidas</dt>
          <dd>{report!.duplicate_timestamps.length}</dd>
        </div>
        <div>
          <dt>Valores fuera de los límites esperados</dt>
          <dd>{outOfRangeTotal}</dd>
        </div>
        <div>
          <dt>Registros con valores inusuales</dt>
          <dd>{report!.anomalies_detected}</dd>
        </div>
      </dl>

      <h3 className="qp-subheading">Mediciones que faltan</h3>
      <ul className="qp-bars">
        {variables.map((variable) => {
          const pct = report!.missing_pct[variable];
          return (
            <li key={variable} className="qp-bar-row">
              <span className="qp-bar-label">{VARIABLE_LABELS[variable] ?? variable.replaceAll("_", " ")}</span>
              <span
                className="qp-bar-track"
                role="img"
                aria-label={`${pct.toFixed(1)}% de faltantes en ${VARIABLE_LABELS[variable] ?? variable.replaceAll("_", " ")}`}
              >
                <span className="qp-bar-fill" style={{ width: `${Math.min(pct, 100)}%` }} />
              </span>
              <span className="qp-bar-value">{pct.toFixed(1)}%</span>
            </li>
          );
        })}
      </ul>

      <p className="qp-note">
        <strong>Nota:</strong> un valor inusual puede representar un evento real (una ola de calor,
        una lluvia intensa), no necesariamente un error de sensor.
      </p>
      <details className="app-technical">
        <summary>Cómo se revisaron los datos</summary>
        <p>Método: {report!.anomaly_method}</p>
        <p className="qp-note qp-note--diagnostic">{report!.note}</p>
      </details>
    </div>
  );
}
