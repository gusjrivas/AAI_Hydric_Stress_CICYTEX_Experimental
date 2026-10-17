import type { RouteId } from "../navigation/useHashRoute";

/**
 * Catálogo versionado de la arquitectura: DISEÑO DOCUMENTADO, no descubrimiento
 * en vivo. Cada nodo cita rutas del repositorio (verificadas por
 * `architectureCatalog.test.ts`). Las limitaciones se declaran; ningún campo
 * simula salud, métricas ni trazas.
 */
export interface ArchitectureNode {
  id: string;
  label: string;
  kind: "stage" | "adapter";
  anchor: RouteId;
  status: "documentado" | "desactivado";
  responsibility: string;
  input: string;
  output: string;
  boundary: string;
  evidence: readonly string[];
  limits: string;
}

export const ARCHITECTURE_NODES: readonly ArchitectureNode[] = [
  {
    id: "iot",
    label: "Datos IoT",
    kind: "stage",
    anchor: "calidad",
    status: "documentado",
    responsibility: "Persistir lecturas de sensores como fuente de datos.",
    input: "Lecturas por sensor (reales, de replay o simuladas).",
    output: "Series persistidas con escritura atómica.",
    boundary: "Almacenamiento de datos; sin lógica de predicción.",
    evidence: ["src/data_ingestion/storage.py", "src/data_ingestion/mock_sensor.py"],
    limits: "Los sensores son fuente de datos, no la contribución central del trabajo.",
  },
  {
    id: "calidad",
    label: "Calidad",
    kind: "stage",
    anchor: "calidad",
    status: "documentado",
    responsibility: "Evaluar la calidad de los datos antes de modelar.",
    input: "Series persistidas.",
    output: "Informe de calidad.",
    boundary: "Módulo de dominio src/data_quality, expuesto por un router delgado; el informe es consultivo y no es una compuerta del pipeline operativo.",
    evidence: ["src/data_quality/quality_report.py", "backend/app/routers/quality.py"],
    limits: "Un informe de calidad no certifica el estado del cultivo.",
  },
  {
    id: "features",
    label: "Features",
    kind: "stage",
    anchor: "prediccion",
    status: "documentado",
    responsibility: "Construir variables predictoras respetando la causalidad temporal.",
    input: "Series con calidad evaluada.",
    output: "Matriz de variables para el modelo.",
    boundary: "Dominio de modelado; no accede a la interfaz.",
    evidence: ["src/predictive_modeling/feature_engineering.py"],
    limits: "Diseñadas para respetar la causalidad temporal; la garantía depende del protocolo de cada recorrido.",
  },
  {
    id: "prediccion",
    label: "Predicción",
    kind: "stage",
    anchor: "prediccion",
    status: "documentado",
    responsibility: "Estimar una señal predictiva relativa con el modelo del recorrido.",
    input: "Matriz de variables.",
    output: "Señal predictiva por fecha objetivo.",
    boundary: "Pipeline de integración sobre módulos de dominio.",
    evidence: ["src/architecture_integration/pipeline.py", "src/predictive_modeling/models.py"],
    limits: "No es una probabilidad agronómicamente calibrada ni indica cuánto o cuándo regar.",
  },
  {
    id: "alertas",
    label: "Alertas",
    kind: "stage",
    anchor: "prediccion",
    status: "documentado",
    responsibility: "Traducir la señal en una alerta para revisión humana.",
    input: "Señal predictiva por fecha.",
    output: "Alerta sí/no por fecha objetivo.",
    boundary: "Regla de dominio en src/predictive_modeling; la interfaz no la reimplementa.",
    evidence: ["src/predictive_modeling/alerts.py"],
    limits: "Apoyo a la decisión; no automatiza el riego.",
  },
  {
    id: "feedback",
    label: "Feedback humano",
    kind: "stage",
    anchor: "prediccion",
    status: "documentado",
    responsibility: "Registrar la confirmación o corrección de una persona sobre una alerta.",
    input: "Alerta y observación humana.",
    output: "Registro de feedback persistido.",
    boundary: "El feedback histórico (SQLite) se mantiene separado del registro operativo; ver backend/app/config.py.",
    evidence: ["src/human_feedback/registry.py", "backend/app/routers/feedback.py", "backend/app/config.py"],
    limits: "Una confirmación o corrección humana es un registro; no ajusta el modelo por sí sola.",
  },
  {
    id: "recalibracion",
    label: "Recalibración y linaje",
    kind: "stage",
    anchor: "linaje",
    status: "documentado",
    responsibility: "Reajustar el predictor para próximos pronósticos y registrar su linaje.",
    input: "Correcciones humanas elegibles según la spec de recalibración.",
    output: "Predictor activo y cadena de linaje.",
    boundary: "Operación explícita iniciada por la persona; cambiar de vista no la ejecuta.",
    evidence: [
      "backend/app/routers/recalibration.py",
      "backend/app/routers/lineage.py",
      "src/human_feedback/recalibration.py",
      "src/human_feedback/lineage.py",
    ],
    limits: "Un fallo de integridad del linaje se muestra explícito.",
  },
  {
    id: "laya",
    label: "Laya",
    kind: "adapter",
    anchor: "evidencia",
    status: "desactivado",
    responsibility: "Adaptador consultivo opcional para triaje de comentarios.",
    input: "Comentario de feedback (sólo si se configura el adaptador).",
    output: "Sugerencia consultiva; sin efecto automático.",
    boundary: "Puerto en human_feedback con adaptador deshabilitado por defecto (ADR-0014).",
    evidence: [
      "src/human_feedback/ports.py",
      "src/human_feedback/adapters/disabled.py",
      "src/human_feedback/adapters/laya_http.py",
      "docs/adr/0014-arquitectura-multisitio-y-laya-consultiva.md",
    ],
    limits: "Desactivado por defecto y sin sugerencias reales en esta configuración; su utilidad no está evaluada.",
  },
];
