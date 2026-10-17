import type { ViewMode } from "./viewMode";
import "./ModeBadge.css";

const MODE_TEXT: Record<ViewMode, { label: string; detail: string }> = {
  operacion: { label: "Operación", detail: "Vista de trabajo; si el punto de medición es de laboratorio, sus datos son simulados." },
  replay: { label: "Replay histórico", detail: "Datos pasados reproducidos; no es el estado actual del cultivo." },
  laboratorio: { label: "Laboratorio sintético", detail: "Datos simulados; no representan un cultivo real." },
  diseno: { label: "Documentación de diseño", detail: "Descripción versionada; no es monitoreo en vivo." },
};

export function ModeBadge({ mode }: { mode: ViewMode }) {
  const { label, detail } = MODE_TEXT[mode];
  return (
    <p className={`mode-badge mode-badge--${mode}`} role="note">
      <strong>{label}</strong>
      <span> · {detail}</span>
    </p>
  );
}
