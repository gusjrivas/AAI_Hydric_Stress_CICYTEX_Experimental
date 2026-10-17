import { useCallback, useEffect, useRef, useState } from "react";
import "./App.css";
import { ArchitectureFlow } from "./features/architecture-flow/ArchitectureFlow";
import { QualityPanel } from "./features/quality/QualityPanel";
import { ForecastPage } from "./features/forecast/ForecastPage";
import { ActivePredictorSummary } from "./features/forecast/ActivePredictorSummary";
import { RecalibrationPanel } from "./features/forecast/RecalibrationPanel";
import { useForecastWorkspace } from "./features/forecast/useForecastWorkspace";
import { LineageChain } from "./features/lineage/LineageChain";
import { EvidencePanel } from "./features/evidence/EvidencePanel";
import { ResumenView } from "./features/summary/ResumenView";
import { ProducerView } from "./features/producer/ProducerView";
import { AppHeader } from "./features/navigation/AppHeader";
import { DestinationNav, SummarySwitch } from "./features/navigation/DestinationNav";
import { DESTINATION_LABELS, ROUTE_GROUP, useHashRoute } from "./features/navigation/useHashRoute";
import type { RouteId } from "./features/navigation/useHashRoute";
import type { NavGroup } from "./features/navigation/useHashRoute";
import { DemoPage } from "./features/demo/DemoPage";
import { useDemoSession } from "./features/demo/useDemoSession";
import { demoGateForSensor } from "./features/demo/lock";
import { HistoricalReplayPage } from "./features/historical-replay/HistoricalReplayPage";
import { PergaminoDefensePage } from "./features/defense/PergaminoDefensePage";
import { MelchorRomeroDefensePage } from "./features/defense/MelchorRomeroDefensePage";
import { CicytexDefensePage } from "./features/defense/CicytexDefensePage";
import { SensorLabPage } from "./features/lab/SensorLabPage";
import { EvidenceResultsPage } from "./features/evidence/EvidenceResultsPage";
import { ModeBadge } from "./features/navigation/ModeBadge";
import { modeForView } from "./features/navigation/viewMode";

const DEFENSE_ROUTES = ["defensa-pergamino", "defensa-melchor-romero", "defensa-cicytex"] as const;
function isDefenseRoute(route: string): route is (typeof DEFENSE_ROUTES)[number] {
  return (DEFENSE_ROUTES as readonly string[]).includes(route);
}

const LAB_ROUTE = "laboratorio-sensores";

const DEMO_HASH = "#demo";
const HISTORICAL_REPLAY_HASH = "#reproduccion-historica";

function useIsDemoRoute(): boolean {
  const [isDemo, setIsDemo] = useState(() => window.location.hash === DEMO_HASH);
  useEffect(() => {
    function onHashChange() {
      setIsDemo(window.location.hash === DEMO_HASH);
    }
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, []);
  return isDemo;
}

function useIsHistoricalReplayRoute(): boolean {
  const [isReplay, setIsReplay] = useState(
    () => window.location.hash === HISTORICAL_REPLAY_HASH,
  );
  useEffect(() => {
    function onHashChange() {
      setIsReplay(window.location.hash === HISTORICAL_REPLAY_HASH);
    }
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, []);
  return isReplay;
}

const SENSOR_ID_PATTERN = /^[a-zA-Z0-9_-]{1,64}$/;
const INITIAL_SENSOR_ID = "sensor-a";
const APP_TITLE = "Seguimiento del agua en el cultivo";

function App() {
  const [draftSensorId, setDraftSensorId] = useState(INITIAL_SENSOR_ID);
  const [activeSensorId, setActiveSensorId] = useState(INITIAL_SENSOR_ID);
  const [sensorError, setSensorError] = useState<string | null>(null);
  // Último sensor de una sesión del Laboratorio que ya tiene datos: evita copiar su id a mano.
  const [labSensorId, setLabSensorId] = useState<string | null>(null);
  const workspace = useForecastWorkspace(activeSensorId);
  const forecastBusy = workspace.activeMutation !== null;
  const [predictorRefreshToken, setPredictorRefreshToken] = useState(0);
  const [lineageRefreshToken, setLineageRefreshToken] = useState(0);

  const handleRecalibrated = useCallback(() => {
    setPredictorRefreshToken((token) => token + 1);
    setLineageRefreshToken((token) => token + 1);
  }, []);

  const demo = useDemoSession();
  const demoGate = demoGateForSensor(demo.session, activeSensorId);
  const isViewingDemoSensor = demo.session !== null && demo.session.sensor_id === activeSensorId;
  const [demoQualityRefreshToken, setDemoQualityRefreshToken] = useState(0);
  const lastAppliedProgressTokenRef = useRef(0);

  useEffect(() => {
    if (!isViewingDemoSensor) return;
    if (demo.progressToken === lastAppliedProgressTokenRef.current) return;
    lastAppliedProgressTokenRef.current = demo.progressToken;
    void workspace.reloadHistory();
    setDemoQualityRefreshToken((token) => token + 1);
  }, [isViewingDemoSensor, demo.progressToken, workspace]);

  const route = useHashRoute();
  const isDemoRoute = useIsDemoRoute();
  const isHistoricalReplayRoute = useIsHistoricalReplayRoute();
  const isFirstRouteRender = useRef(true);

  const activeGroup: NavGroup = isDemoRoute || isHistoricalReplayRoute ? "herramientas" : ROUTE_GROUP[route];
  const inTools = activeGroup === "herramientas";

  // `#demo` y `#reproduccion-historica` se resuelven como la ruta «resumen» (no tienen ruta propia), así que `route`
  // no cambia entre Resumen, Demostración y Reproducción histórica: el título y el foco dependen de la VISTA abierta.
  const viewKey: RouteId | "demo" | "reproduccion-historica" = isDemoRoute
    ? "demo"
    : isHistoricalReplayRoute
      ? "reproduccion-historica"
      : route;

  useEffect(() => {
    const label = viewKey === "demo" ? "Demostración" : viewKey === "reproduccion-historica" ? "Reproducción histórica" : DESTINATION_LABELS[viewKey];
    document.title = `${APP_TITLE} — ${label}`;
    if (isFirstRouteRender.current) {
      isFirstRouteRender.current = false;
      return;
    }
    document.getElementById(`${viewKey}-heading`)?.focus();
  }, [viewKey]);

  function selectSensor(sensorId: string) {
    setDraftSensorId(sensorId);
    setActiveSensorId(sensorId);
    setSensorError(null);
  }
  function openLabSensorInTools(sensorId: string) {
    selectSensor(sensorId);
    window.location.hash = "#resumen";
  }

  function applySensor() {
    const candidate = draftSensorId.trim();
    if (!SENSOR_ID_PATTERN.test(candidate)) {
      setSensorError("Ingresá un identificador válido: letras, números, guiones o guiones bajos, hasta 64 caracteres.");
      return;
    }
    setSensorError(null);
    setActiveSensorId(candidate);
  }

  return (
    <div className={`app-page ${route === "productor" ? "app-producer" : ""} ${isDefenseRoute(route) ? "app-defense" : ""} ${route === LAB_ROUTE ? "app-lab" : ""}`}>
      <a href="#main-content" className="skip-link" onClick={(event) => {
        event.preventDefault();
        document.getElementById("main-content")?.focus();
      }}>
        Saltar al contenido
      </a>
      <AppHeader activeGroup={activeGroup} />
      <div className="app-body">
      {inTools && (
        <>
          <header className="app-sensor-header app-tools-intro">
            <div className="app-tools-top">
              <div className="app-tools-title">
                <p className="eyebrow">Herramientas técnicas</p>
                <h1>Seguimiento del agua en el cultivo</h1>
                <p className="app-intro">
                  Consultá el pronóstico y registrá lo que observaste en el cultivo. Herramienta en evaluación: ayuda a
                  revisar la situación; no indica cuánto ni cuándo regar.
                </p>
              </div>
              {route !== "productor" && !isHistoricalReplayRoute && !isDemoRoute && (
                <div className="app-tools-sensor">
                  <form
                    className="app-sensor-form"
                    onSubmit={(event) => {
                      event.preventDefault();
                      applySensor();
                    }}
                  >
                    <label htmlFor="sensor-draft-input">Punto de medición (sensor)</label>
                    <input
                      id="sensor-draft-input"
                      value={draftSensorId}
                      onChange={(event) => setDraftSensorId(event.target.value)}
                      aria-invalid={sensorError ? true : undefined}
                      aria-describedby={sensorError ? "sensor-error" : undefined}
                    />
                    <button type="submit" disabled={forecastBusy}>
                      Aplicar
                    </button>
                  </form>
                  <p className="app-sensor-active" aria-live="polite">
                    Sensor activo: <strong>{activeSensorId}</strong>
                  </p>
                  {sensorError && (
                    <p id="sensor-error" role="alert" className="app-sensor-error">
                      {sensorError}
                    </p>
                  )}
                  {labSensorId && labSensorId !== activeSensorId && (
                    <p className="app-lab-sensor">
                      El Laboratorio tiene un sensor con datos: <strong>{labSensorId}</strong>{" "}
                      <button type="button" onClick={() => selectSensor(labSensorId)} disabled={forecastBusy}>
                        Usar este sensor
                      </button>
                    </p>
                  )}
                </div>
              )}
            </div>
          </header>
          <DestinationNav
            active={route}
            extra={
              <>
                {demo.configured && (
                  <li>
                    <a href={DEMO_HASH} className="dn-link" aria-current={isDemoRoute ? "page" : undefined}>
                      Demostración
                    </a>
                  </li>
                )}
                <li>
                  <a
                    href={HISTORICAL_REPLAY_HASH}
                    className="dn-link"
                    aria-current={isHistoricalReplayRoute ? "page" : undefined}
                  >
                    Reproducción histórica
                  </a>
                </li>
              </>
            }
          />
        </>
      )}

      <main id="main-content" className="app-sections" tabIndex={-1}>
        <ModeBadge mode={modeForView(viewKey)} />
        {!isDemoRoute && route === "arquitectura" && (
          <section aria-labelledby="arquitectura-heading">
            <h1 id="arquitectura-heading" className="app-section-heading" tabIndex={-1}>
              Arquitectura del sistema
            </h1>
            <ArchitectureFlow />
          </section>
        )}
        {!isDemoRoute && route === "defensa-pergamino" && <PergaminoDefensePage />}
        {!isDemoRoute && route === "defensa-melchor-romero" && <MelchorRomeroDefensePage />}
        {!isDemoRoute && route === "defensa-cicytex" && <CicytexDefensePage />}
        {!isDemoRoute && route === LAB_ROUTE && <SensorLabPage onSensorWithData={setLabSensorId} onOpenInTools={openLabSensorInTools} />}
        {!isDemoRoute && route === "evidencia-resultados" && <EvidenceResultsPage />}
        {isHistoricalReplayRoute && (
          <section aria-labelledby="reproduccion-historica-heading">
            <h2 id="reproduccion-historica-heading" className="app-section-heading" tabIndex={-1}>
              Reproducción histórica
            </h2>
            <HistoricalReplayPage />
          </section>
        )}

        {isDemoRoute && (
          <section aria-labelledby="demo-heading">
            <h2 id="demo-heading" className="app-section-heading" tabIndex={-1}>
              Demostración
            </h2>
            <DemoPage demo={demo} />
          </section>
        )}

        {!isDemoRoute && !isHistoricalReplayRoute && (route === "resumen" || route === "prediccion") && <SummarySwitch active={route} />}

        {!isDemoRoute && !isHistoricalReplayRoute && route === "resumen" && (
          <section aria-labelledby="resumen-heading">
            <h2 id="resumen-heading" className="app-section-heading" tabIndex={-1}>
              Resumen
            </h2>
            <ResumenView
              sensorId={activeSensorId}
              workspace={workspace}
              demoGate={demoGate}
              refreshToken={demoQualityRefreshToken}
            />
          </section>
        )}

        {!isDemoRoute && route === "productor" && <ProducerView />}

        {!isDemoRoute && route === "prediccion" && (
          <section aria-labelledby="prediccion-heading">
            <h2 id="prediccion-heading" className="app-section-heading" tabIndex={-1}>
              Historial y observaciones
            </h2>
            <ForecastPage sensorId={activeSensorId} workspace={workspace} demoGate={demoGate} />
          </section>
        )}

        {!isDemoRoute && route === "calidad" && (
          <section aria-labelledby="calidad-heading">
            <h2 id="calidad-heading" className="app-section-heading" tabIndex={-1}>
              Datos disponibles
            </h2>
            <QualityPanel sensorId={activeSensorId} refreshToken={demoQualityRefreshToken} />
          </section>
        )}

        {!isDemoRoute && route === "linaje" && (
          <section aria-labelledby="linaje-heading">
            <h2 id="linaje-heading" className="app-section-heading" tabIndex={-1}>
              Ajustar próximos pronósticos
            </h2>
            <RecalibrationPanel
              sensorId={activeSensorId}
              workspace={workspace}
              refreshToken={predictorRefreshToken}
              onRecalibrated={handleRecalibrated}
              demoGate={demoGate}
            />
            <details className="app-technical">
              <summary>Información técnica de los ajustes</summary>
              <ActivePredictorSummary sensorId={activeSensorId} refreshToken={predictorRefreshToken} />
              <LineageChain sensorId={activeSensorId} refreshToken={lineageRefreshToken} />
            </details>
          </section>
        )}

        {!isDemoRoute && route === "evidencia" && (
          <section aria-labelledby="evidencia-heading">
            <h2 id="evidencia-heading" className="app-section-heading" tabIndex={-1}>
              Acerca de esta herramienta
            </h2>
            <p>Esta herramienta usa las mediciones disponibles para estimar si puede haber una alerta en una fecha posterior. Podés consultar los resultados guardados y registrar si coinciden con lo observado.</p>
            <p>Fue desarrollada como parte de un trabajo de investigación. Sus resultados no garantizan el estado del cultivo ni reemplazan la revisión en el lugar.</p>
            <details className="app-technical">
              <summary>Ver el estudio y la documentación técnica</summary>
              <p>
                El mapa de la arquitectura está en <a href="#arquitectura">Arquitectura del sistema</a>.
              </p>
              <EvidencePanel />
            </details>
          </section>
        )}
      </main>
      </div>
    </div>
  );
}

export default App;
