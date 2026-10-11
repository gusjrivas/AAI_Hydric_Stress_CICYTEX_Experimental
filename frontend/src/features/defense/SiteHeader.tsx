export type DefenseSite = "pergamino" | "melchor" | "cicytex";

const SITES: Record<DefenseSite, { route: string; name: string; chips: { label: string; className: string }[]; period: string }> = {
  pergamino: {
    route: "defensa-pergamino",
    name: "Pergamino",
    chips: [
      { label: "Datos externos", className: "site-chip--external" },
      { label: "Histórico", className: "site-chip--historical" },
    ],
    period: "Pergamino · emisiones persistidas del 13 al 17 de junio de 2023.",
  },
  melchor: {
    route: "defensa-melchor-romero",
    name: "Melchor Romero",
    chips: [{ label: "Histórico", className: "site-chip--historical" }],
    period: "Melchor Romero · emisiones persistidas del 20 al 24 de octubre de 2024.",
  },
  cicytex: {
    route: "defensa-cicytex",
    name: "CICYTEX",
    chips: [
      { label: "Datos externos", className: "site-chip--external" },
      { label: "Replay causal", className: "site-chip--historical" },
    ],
    period: "Talavera la Real · tomate de industria · emisiones legítimas desde el 6 de julio de 2023.",
  },
};

/**
 * Encabezado común de las pantallas de seguimiento histórico. Pergamino y
 * Melchor Romero comparten estructura, no contenido: cada sitio conserva su
 * procedencia, su período y sus límites propios.
 */
export function SiteHeader({ site }: { site: DefenseSite }) {
  const info = SITES[site];
  return (
    <header className="site-header">
      <div className="site-header-row">
        <div className="site-header-title">
          <p className="producer-eyebrow">Seguimiento histórico · recorrido histórico</p>
          <h1 id={`${info.route}-heading`} tabIndex={-1}>{info.name}</h1>
          <div className="site-chips">
            {info.chips.map((chip) => <span key={chip.label} className={`site-chip ${chip.className}`}>{chip.label}</span>)}
          </div>
        </div>
        <nav className="site-switch" aria-label="Localidad">
          <a href="#defensa-pergamino" aria-current={site === "pergamino" ? "page" : undefined}>Pergamino</a>
          <a href="#defensa-melchor-romero" aria-current={site === "melchor" ? "page" : undefined}>Melchor Romero</a>
          <a href="#defensa-cicytex" aria-current={site === "cicytex" ? "page" : undefined}>CICYTEX</a>
        </nav>
      </div>
      <p className="site-period">{info.period}</p>
    </header>
  );
}
