import { forwardRef, type ReactNode } from "react";

/** Semáforo grande: el estado se dice con texto y forma, nunca solo con color. */
export function Traffic({ alert }: { alert: boolean }) {
  return (
    <div className={`gd-traffic ${alert ? "is-alert" : "is-clear"}`}>
      <span className="gd-traffic-icon" aria-hidden="true">{alert ? "▲" : "●"}</span>
      <strong className="gd-traffic-label">{alert ? "Alerta prevista" : "Sin alerta"}</strong>
    </div>
  );
}

/** «N de 3 modelos coinciden»: cuántos modelos individuales dan el mismo resultado que el mostrado. */
export function Agreement({ matching, total }: { matching: number; total: number }) {
  return <p className="gd-agree">{matching} de {total} modelos coinciden con este resultado</p>;
}

export function SourceLine({ children }: { children: ReactNode }) {
  return <p className="gd-source"><strong>De dónde sale:</strong> {children}</p>;
}

export function TechDetails({ children }: { children: ReactNode }) {
  return (
    <details className="gd-details">
      <summary>Ver detalle técnico</summary>
      <div className="gd-details-body">{children}</div>
    </details>
  );
}

/** Un valor técnico que solo se muestra si existe; si no, se declara. */
export function TechFact({ label, value, missing = "no disponible" }: { label: string; value: string | null | undefined; missing?: string }) {
  return (
    <>
      <dt>{label}</dt>
      <dd>{value ? <code>{value}</code> : missing}</dd>
    </>
  );
}

export function StepError({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div role="alert" className="gd-error">
      <p>{message}</p>
      <button type="button" className="gd-btn gd-btn-secondary" onClick={onRetry}>Reintentar</button>
    </div>
  );
}

/** Región con foco programático: recibe el foco cuando se revela lo que ocurrió. */
export const ResultRegion = forwardRef<HTMLElement, { children: ReactNode }>(function ResultRegion({ children }, ref) {
  return (
    <section ref={ref} tabIndex={-1} aria-label="Qué ocurrió después" className="gd-result">
      <h3>Qué ocurrió después</h3>
      {children}
    </section>
  );
});

export const LOAD_ERROR = "No se pudo cargar este sitio. Verificá la conexión con el servidor y volvé a intentarlo.";
export const ADVANCE_ERROR = "No se pudo avanzar un día. Verificá la conexión con el servidor y volvé a intentarlo.";
