import { useEffect, useRef, useState, type ReactNode } from "react";
import { LabStep } from "./LabStep";
import { ProducerStep, type ProducerSite } from "./ProducerStep";
import "./GuidedDemoPage.css";

const PERGAMINO: ProducerSite = {
  sensorId: "pergamino-ensemble-demo",
  emission: "2023-06-13",
  source: "datos externos ERA5-Land y NASA POWER (reanálisis), no un sensor instalado.",
};
const MELCHOR: ProducerSite = {
  sensorId: "melchor-romero-demo",
  emission: "2024-10-20",
  source: "datos externos ESA CCI (humedad del suelo) y NASA POWER (clima), no un sensor instalado.",
};

const STEPS: { id: string; title: string; render: () => ReactNode }[] = [
  { id: "pergamino", title: "Pergamino", render: () => <ProducerStep site={PERGAMINO} /> },
  { id: "melchor", title: "Melchor Romero", render: () => <ProducerStep site={MELCHOR} /> },
  { id: "laboratorio", title: "Sensores simulados (laboratorio)", render: () => <LabStep /> },
];

/**
 * Recorrido guiado de dos sitios y laboratorio para presentar la herramienta. Reutiliza los clientes y hooks existentes de cada
 * pantalla y no agrega ningún endpoint. Cada paso se monta al llegar y se descarta al salir: volver a un paso lo reinicia.
 */
export function GuidedDemoPage() {
  const [step, setStep] = useState(0);
  const headingRef = useRef<HTMLHeadingElement>(null);
  const first = useRef(true);

  useEffect(() => {
    if (first.current) {
      first.current = false;
      return;
    }
    headingRef.current?.focus();
  }, [step]);

  const current = STEPS[step];
  const upcoming = STEPS[step + 1];

  return (
    <div className="guided-demo">
      <header className="gd-header">
        <p className="producer-eyebrow">Demostración · apoyo a la decisión</p>
        <h1 id="demo-guiada-heading" tabIndex={-1}>Recorrido guiado: dos sitios y laboratorio</h1>
        <p role="note" aria-label="Alcance del recorrido" className="gd-scope">
          Esto es un recorrido, no una evaluación de la herramienta. Es un apoyo a la decisión: no riega ni decide cuánto regar.
          Cada sitio usa sus propios datos y lo que se ve en uno no se aplica a otro.
        </p>
        <div className="gd-progress">
          <p className="gd-progress-label">Paso {step + 1} de {STEPS.length}</p>
          <progress aria-label="Progreso del recorrido" value={step + 1} max={STEPS.length} />
        </div>
      </header>

      <section key={current.id} aria-labelledby={`gd-step-${current.id}`} className="gd-step">
        <h2 id={`gd-step-${current.id}`} ref={headingRef} tabIndex={-1}>{current.title}</h2>
        {current.render()}
      </section>

      <nav className="gd-nav" aria-label="Cambiar de sitio">
        <button type="button" className="gd-btn gd-btn-secondary" disabled={step === 0} onClick={() => setStep(step - 1)}>
          Sitio anterior
        </button>
        {upcoming ? (
          <button type="button" className="gd-btn gd-btn-primary" onClick={() => setStep(step + 1)}>
            Siguiente sitio: {upcoming.title}
          </button>
        ) : (
          <p className="gd-note">Fin del recorrido.</p>
        )}
      </nav>
    </div>
  );
}
