import { useState } from "react";
import "./ArchitectureFlow.css";
import { ARCHITECTURE_NODES } from "./architectureCatalog";

const STAGES = ARCHITECTURE_NODES.filter((node) => node.kind === "stage");
const ADAPTERS = ARCHITECTURE_NODES.filter((node) => node.kind === "adapter");

export function ArchitectureFlow() {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const selected = ARCHITECTURE_NODES.find((node) => node.id === selectedId) ?? null;

  return (
    <header className="af-header">
      <h2 className="af-title">Demo: arquitectura de IA para estrés hídrico</h2>
      <p className="af-subtitle">
        Recorrido de defensa — datos IoT → calidad → features → predicción → alerta → feedback
        humano → recalibración → linaje. La IA (predicción, alerta y recalibración) es el núcleo;
        los datos IoT son fuente de datos y contexto.
      </p>
      <p className="af-category">
        <strong>Diseño documentado</strong> · mapa estático y versionado: no es monitoreo en vivo y
        no refleja el estado en vivo de ningún componente.
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

      <div className="af-details">
        <p className="af-details-intro">Elegí un componente para ver su ficha:</p>
        <ul className="af-detail-buttons">
          {[...STAGES, ...ADAPTERS].map((node) => (
            <li key={node.id}>
              <button
                type="button"
                aria-pressed={selectedId === node.id}
                onClick={() => setSelectedId(node.id)}
              >
                {node.label}
              </button>
            </li>
          ))}
        </ul>
        {selected && (
          <section className="af-sheet" aria-label={`Ficha de ${selected.label}`} aria-live="polite">
            <h3>{selected.label}</h3>
            <dl>
              <dt>Estado</dt>
              <dd>{selected.status === "desactivado" ? "Desactivado por defecto" : "Diseño documentado"}</dd>
              <dt>Responsabilidad</dt>
              <dd>{selected.responsibility}</dd>
              <dt>Entrada</dt>
              <dd>{selected.input}</dd>
              <dt>Salida</dt>
              <dd>{selected.output}</dd>
              <dt>Frontera</dt>
              <dd>{selected.boundary}</dd>
              <dt>Evidencia</dt>
              <dd>
                <ul>
                  {selected.evidence.map((path) => (
                    <li key={path}>
                      <code>{path}</code>
                    </li>
                  ))}
                </ul>
              </dd>
              <dt>Límites</dt>
              <dd>{selected.limits}</dd>
            </dl>
          </section>
        )}
      </div>

      <table className="af-table">
        <caption>Componentes de la arquitectura (alternativa textual del mapa)</caption>
        <thead>
          <tr>
            <th scope="col">Componente</th>
            <th scope="col">Tipo</th>
            <th scope="col">Estado</th>
            <th scope="col">Límites</th>
          </tr>
        </thead>
        <tbody>
          {ARCHITECTURE_NODES.map((node) => (
            <tr key={node.id}>
              <th scope="row">{node.label}</th>
              <td>{node.kind === "stage" ? "Etapa" : "Adaptador consultivo"}</td>
              <td>{node.status === "desactivado" ? "Desactivado por defecto" : "Documentado"}</td>
              <td>{node.limits}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </header>
  );
}
