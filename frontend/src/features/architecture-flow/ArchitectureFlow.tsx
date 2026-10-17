import "./ArchitectureFlow.css";

const STAGES = [
  { id: "iot", label: "Datos IoT", anchor: "calidad" },
  { id: "calidad", label: "Calidad", anchor: "calidad" },
  { id: "features", label: "Features", anchor: "prediccion" },
  { id: "prediccion", label: "Predicción", anchor: "prediccion" },
  { id: "alertas", label: "Alertas", anchor: "prediccion" },
  { id: "feedback", label: "Feedback humano", anchor: "prediccion" },
  { id: "recalibracion", label: "Recalibración y linaje", anchor: "linaje" },
];

export function ArchitectureFlow() {
  return (
    <header className="af-header">
      <h2 className="af-title">Demo: arquitectura de IA para estrés hídrico</h2>
      <p className="af-subtitle">
        Recorrido de defensa — datos IoT → calidad → features → predicción → alerta → feedback
        humano → recalibración → linaje. La IA (predicción, alerta y recalibración) es el núcleo;
        los datos IoT son fuente de datos y contexto.
      </p>
      <nav className="af-flow" aria-label="Etapas de la arquitectura, con acceso directo a cada sección">
        <ol>
          {STAGES.map((stage, index) => (
            <li key={stage.id} className="af-stage">
              <a href={`#${stage.anchor}`} className="af-chip">
                {stage.label}
              </a>
              {index < STAGES.length - 1 && (
                <span aria-hidden="true" className="af-arrow">
                  →
                </span>
              )}
            </li>
          ))}
        </ol>
      </nav>
    </header>
  );
}
