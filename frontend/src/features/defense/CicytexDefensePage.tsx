import { useEffect, useMemo, useState } from "react";
import { SiteHeader } from "./SiteHeader";
import { advanceCicytexSession, createCicytexSession, getCicytexCatalog, resetCicytexSession, type CicytexCatalog, type CicytexSession } from "./cicytexApi";
import "./CicytexDefensePage.css";

const LABELS: Record<string,string> = { logistic_regression:"Logistic Regression", random_forest:"Random Forest", hist_gradient_boosting_classifier:"HistGradientBoosting", ensemble:"Ensamble", persistence:"Persistencia" };
const fmt = (value:number|null) => value === null ? "—" : value.toFixed(3);

function MoistureChart({session}:{session:CicytexSession}) {
  const points=session.readings.slice(-30), values=[...points.map(p=>p.soil_moisture),session.threshold];
  const min=Math.min(...values), max=Math.max(...values), range=max-min||1;
  const xy=points.map((p,i)=>`${20+i*(560/Math.max(points.length-1,1))},${180-((p.soil_moisture-min)/range)*140}`).join(" ");
  const thresholdY=180-((session.threshold-min)/range)*140;
  return <div className="cy-chart" aria-label="Humedad revelada hasta el reloj actual"><svg viewBox="0 0 600 210" role="img"><line x1="20" x2="580" y1={thresholdY} y2={thresholdY} className="cy-threshold"/><polyline points={xy} className="cy-moisture"/><text x="24" y={Math.max(16,thresholdY-6)}>P20 {session.threshold.toFixed(3)}</text></svg><p>Solo se dibujan observaciones reveladas hasta <strong>{session.revealed_through}</strong>.</p></div>;
}

export function CicytexDefensePage() {
  const [catalog,setCatalog]=useState<CicytexCatalog|null>(null), [sensor,setSensor]=useState("CP1_S1"), [horizon,setHorizon]=useState(1), [emission,setEmission]=useState("2023-07-06");
  const [session,setSession]=useState<CicytexSession|null>(null), [error,setError]=useState<string|null>(null), [busy,setBusy]=useState(false);
  useEffect(()=>{getCicytexCatalog().then(setCatalog).catch(reason=>setError(String(reason)))},[]);
  const dates=catalog?.emission_dates_by_horizon[String(horizon)]??[];
  useEffect(()=>{if(dates.length&&!dates.includes(emission))setEmission(dates[0])},[dates,emission]);
  const ensemble=session?.predictions.find(p=>p.method==="ensemble");
  const agreement=useMemo(()=>{const c=session?.predictions.filter(p=>!["ensemble","persistence"].includes(p.method))??[];return c.length?`${c.filter(p=>p.alert).length}/3 alertan`:"—"},[session]);
  async function act(action:()=>Promise<CicytexSession>){setBusy(true);setError(null);try{setSession(await action())}catch(reason){setError(String(reason))}finally{setBusy(false)}}
  return <div className="cicytex-defense"><SiteHeader site="cicytex"/>
    <section className="cy-intro"><p><strong>Prueba retrospectiva causal.</strong> Tomate de industria, Talavera la Real, campaña 2023; 21 sondas a 20 cm. Las familias fueron congeladas después de validar hasta el 05/07/2023.</p><p>El evento es humedad volumétrica inferior al P20 de entrenamiento. No equivale a estrés hídrico fisiológico observado.</p></section>
    <section className="cy-controls" aria-label="Seleccionar reproducción CICYTEX"><label>Sonda<select value={sensor} onChange={e=>{setSensor(e.target.value);setSession(null)}}>{catalog?.sensors.map(item=><option key={item}>{item}</option>)}</select></label><label>Horizonte<select value={horizon} onChange={e=>{setHorizon(Number(e.target.value));setSession(null)}}>{[1,2,3].map(item=><option value={item} key={item}>+{item} día{item>1?"s":""}</option>)}</select></label><label>Fecha de emisión<select value={emission} onChange={e=>{setEmission(e.target.value);setSession(null)}}>{dates.map(item=><option key={item}>{item}</option>)}</select></label><button disabled={!catalog||busy} onClick={()=>void act(()=>createCicytexSession(sensor,emission,horizon))}>Abrir emisión congelada</button></section>
    {error&&<p role="alert" className="cy-error">{error}</p>}
    {session&&<><section className="cy-clock"><div><span>Emisión</span><strong>{session.emission_date}</strong></div><div><span>Reloj revelado</span><strong>{session.revealed_through}</strong></div><div><span>Objetivo</span><strong>{ensemble?.target_date}</strong></div><button disabled={busy||!session.can_advance} onClick={()=>void act(()=>advanceCicytexSession(session.session_id))}>Día siguiente</button><button disabled={busy} onClick={()=>void act(()=>resetCicytexSession(session.session_id))}>Reiniciar</button></section>
      <section className="cy-panel"><h2>Predicción archivada · +{session.horizon_days} día{session.horizon_days>1?"s":""}</h2><p>Acuerdo: <strong>{agreement}</strong> · decisión 0,5 · P20 {session.threshold.toFixed(4)} m³/m³.</p><div className="cy-table-wrap"><table><thead><tr><th>Método</th><th>Score</th><th>Alerta</th><th>Observado</th><th>Resultado</th></tr></thead><tbody>{session.predictions.map(p=><tr key={p.method} className={p.method==="ensemble"?"is-ensemble":""}><th>{LABELS[p.method]}</th><td>{p.score.toFixed(3)}</td><td>{p.alert?"Sí":"No"}</td><td>{p.observed_soil_moisture===null?"Oculto hasta avanzar":`${p.observed_soil_moisture.toFixed(4)} m³/m³`}</td><td>{p.outcome??"Pendiente"}</td></tr>)}</tbody></table></div></section>
      <MoistureChart session={session}/><section className="cy-panel"><h2>Comparación acumulada revelada</h2><div className="cy-table-wrap"><table><thead><tr><th>Método</th><th>n</th><th>VP</th><th>VN</th><th>FP</th><th>FN</th><th>MCC</th><th>Prec.</th><th>Recall</th><th>F1</th></tr></thead><tbody>{Object.entries(session.metrics).map(([method,m])=><tr key={method}><th>{LABELS[method]}</th><td>{m.n}</td><td>{m.tp}</td><td>{m.tn}</td><td>{m.fp}</td><td>{m.fn}</td><td>{fmt(m.mcc)}</td><td>{fmt(m.precision)}</td><td>{fmt(m.recall)}</td><td>{fmt(m.f1)}</td></tr>)}</tbody></table></div><p>Solo se usan objetivos cuya fecha ya reveló esta sesión.</p></section>
    </>}</div>;
}
