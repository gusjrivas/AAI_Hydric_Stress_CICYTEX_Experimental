const API = import.meta.env.VITE_API_BASE_URL ?? "";

export interface CicytexCatalog { sensors: string[]; emission_dates_by_horizon: Record<string, string[]>; horizons: number[]; first_legitimate_emission: string; last_observation: string; }
export interface ReplayPrediction { method: string; score: number; alert: boolean; target_date: string; observed_soil_moisture: number | null; observed_label: number | null; outcome: "VP" | "VN" | "FP" | "FN" | null; }
export interface ReplayMetric { n: number; tp: number; tn: number; fp: number; fn: number; mcc: number | null; precision: number | null; recall: number | null; f1: number | null; coverage: number; }
export interface CicytexSession { session_id: string; sensor_id: string; emission_date: string; horizon_days: number; revealed_through: string; threshold: number; proxy_notice: string; predictions: ReplayPrediction[]; readings: { date: string; soil_moisture: number }[]; metrics: Record<string, ReplayMetric>; can_advance: boolean; }

async function json<T>(pending: Promise<Response>): Promise<T> { const response = await pending; if (!response.ok) throw new Error((await response.text()) || `HTTP ${response.status}`); return response.json() as Promise<T>; }
export const getCicytexCatalog = () => json<CicytexCatalog>(fetch(`${API}/api/v2/cicytex/replay/catalog`));
export const createCicytexSession = (sensor_id: string, emission_date: string, horizon_days: number) => json<CicytexSession>(fetch(`${API}/api/v2/cicytex/replay/sessions`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ sensor_id, emission_date, horizon_days }) }));
export const advanceCicytexSession = (id: string) => json<CicytexSession>(fetch(`${API}/api/v2/cicytex/replay/sessions/${id}/advance`, { method: "POST" }));
export const resetCicytexSession = (id: string) => json<CicytexSession>(fetch(`${API}/api/v2/cicytex/replay/sessions/${id}/reset`, { method: "POST" }));
