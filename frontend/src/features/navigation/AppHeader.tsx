import { useLayoutEffect, useRef, type ReactNode } from "react";
import "./AppHeader.css";
import type { NavGroup } from "./useHashRoute";

interface PrimaryItem {
  group: NavGroup;
  href: string;
  label: string;
  /** Etiqueta breve para la barra inferior de pantallas muy angostas (el nombre accesible es `label`). */
  shortLabel: string;
  icon: ReactNode;
  secondary?: boolean;
}

const ICON_PROPS = { viewBox: "0 0 24 24", width: 22, height: 22, "aria-hidden": true, focusable: false } as const;

const PRIMARY_ITEMS: PrimaryItem[] = [
  {
    group: "seguimiento",
    href: "#defensa-pergamino",
    label: "Seguimiento histórico",
    shortLabel: "Histórico",
    icon: (
      <svg {...ICON_PROPS}>
        <path d="M12 3C8.500 9 6 11.500 6 15a6 6 0 0 0 12 0c0-3.500-2.500-6-6-12z" fill="none" stroke="currentColor" strokeWidth="2" />
      </svg>
    ),
  },
  {
    group: "cultivo",
    href: "#productor",
    label: "Mi cultivo",
    shortLabel: "Cultivo",
    icon: (
      <svg {...ICON_PROPS}>
        <path d="M12 21V11M12 11c0-3 2-5 5-5 0 3-2 5-5 5zM12 14c0-2.500-1.800-4.200-4.500-4.200 0 2.500 1.800 4.200 4.500 4.200z" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    ),
  },
  {
    group: "laboratorio",
    href: "#laboratorio-sensores",
    label: "Laboratorio",
    shortLabel: "Lab.",
    icon: (
      <svg {...ICON_PROPS}>
        <path d="M9 3h6M10 3v6l-5 9a2 2 0 0 0 2 3h10a2 2 0 0 0 2-3l-5-9V3" fill="none" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" />
      </svg>
    ),
  },
  {
    group: "evidencia",
    href: "#evidencia-resultados",
    label: "Evidencia",
    shortLabel: "Evidencia",
    icon: (
      <svg {...ICON_PROPS}>
        <path d="M4 20V4M4 20h16M8 16v-5M12 16V8M16 16v-8" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
      </svg>
    ),
  },
  {
    group: "arquitectura",
    href: "#arquitectura",
    label: "Arquitectura",
    shortLabel: "Mapa",
    icon: (
      <svg {...ICON_PROPS}>
        <path d="M4 5h6v5H4zM14 5h6v5h-6zM9 14h6v5H9zM7 10v2h10v-2M12 12v2" fill="none" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
      </svg>
    ),
  },
  {
    group: "herramientas",
    href: "#resumen",
    label: "Herramientas técnicas",
    shortLabel: "Técnicas",
    secondary: true,
    icon: (
      <svg {...ICON_PROPS}>
        <path d="M14.500 6.500a4 4 0 0 0 5 5L10 21a2.100 2.100 0 0 1-3-3zM8 8 5 5 3 7l3 3" fill="none" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
      </svg>
    ),
  },
];

/**
 * Encabezado de marca y navegación principal. Un único `<nav>`: en pantallas
 * anchas son píldoras dentro del encabezado; en móvil el mismo elemento pasa a
 * ser una barra inferior fija (solo CSS), sin duplicar enlaces en el DOM.
 */
export function AppHeader({ activeGroup }: { activeGroup: NavGroup }) {
  const headerRef = useRef<HTMLElement>(null);
  // Publica la altura real del encabezado para elementos pegajosos debajo de él
  // (p. ej. la banda permanente «Simulación» del laboratorio).
  useLayoutEffect(() => {
    const publish = () => {
      document.documentElement.style.setProperty("--app-header-h", `${headerRef.current?.offsetHeight ?? 72}px`);
    };
    publish();
    window.addEventListener("resize", publish);
    return () => window.removeEventListener("resize", publish);
  }, []);
  return (
    <header className="app-header" ref={headerRef}>
      <div className="app-header-inner">
        <a className="app-brand" href="#productor" aria-label="Seguimiento del agua en el cultivo, ir a Mi cultivo">
          <svg viewBox="0 0 32 32" width="28" height="28" aria-hidden="true" focusable="false">
            <path d="M16 3C11 11 7 15 7 20a9 9 0 0 0 18 0c0-5-4-9-9-17z" fill="currentColor" />
          </svg>
          <span className="app-brand-text">
            <span className="app-brand-name">Seguimiento del agua</span>
            <span className="app-brand-sub">en el cultivo · apoyo a la decisión</span>
          </span>
        </a>
        <nav className="app-primary-nav" aria-label="Secciones principales">
          <ul>
            {PRIMARY_ITEMS.map((item) => (
              <li key={item.group}>
                <a
                  href={item.href}
                  className={item.secondary ? "is-secondary" : undefined}
                  aria-current={activeGroup === item.group ? "page" : undefined}
                >
                  {item.icon}
                  <span className="nav-full">{item.label}</span>
                  <span className="nav-short" aria-hidden="true">{item.shortLabel}</span>
                </a>
              </li>
            ))}
          </ul>
        </nav>
      </div>
    </header>
  );
}
