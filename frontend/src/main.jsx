import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import './style.css';

function App() {
  const [targets, setTargets] = useState([]);
  const [error, setError] = useState('');
  const [updated, setUpdated] = useState(null);
  const [selected, setSelected] = useState('');
  const [history, setHistory] = useState([]);
  const [historyError, setHistoryError] = useState('');
  const [clock, setClock] = useState(Date.now());
  useEffect(() => {
    const controller = new AbortController();
    let stopped = false;
    async function refresh() {
      try {
        const response = await fetch('/api/targets', { signal: AbortSignal.any([controller.signal, AbortSignal.timeout(4000)]) });
        if (!response.ok) throw new Error(`API returned ${response.status}`);
        const data = await response.json();
        if (!stopped) { setTargets(data.targets); setError(''); setUpdated(new Date()); setClock(Date.now()); }
      } catch (e) { if (!stopped) setError(e.message); }
    }
    refresh();
    const clockTimer = setInterval(() => setClock(Date.now()), 1000);
    const timer = setInterval(refresh, 5000);
    return () => { stopped = true; clearInterval(timer); clearInterval(clockTimer); controller.abort(); };
  }, []);
  useEffect(() => {
    if (!selected) { setHistory([]); setHistoryError(''); return; }
    const controller = new AbortController();
    let stopped = false;
    setHistory([]); setHistoryError('');
    async function refresh() {
      try {
        const response = await fetch(`/api/history?target=${encodeURIComponent(selected)}&limit=30`, { signal: AbortSignal.any([controller.signal, AbortSignal.timeout(4000)]) });
        if (!response.ok) throw new Error(`History returned ${response.status}`);
        const data = await response.json();
        if (!stopped) { setHistory(data.history.slice().reverse()); setHistoryError(''); }
      } catch (e) { if (!stopped) setHistoryError(e.message); }
    }
    refresh(); const timer = setInterval(refresh, 5000);
    return () => { stopped = true; clearInterval(timer); controller.abort(); };
  }, [selected]);
  const stale = t => clock - new Date(t.observed_at).getTime() > 30000;
  const healthy = targets.filter(t => t.healthy && !stale(t)).length;
  const max = Math.max(1, ...history.map(t => t.latency_ms));
  return <main>
    <header><div className="brand">N<span>↗</span></div><div><p className="eyebrow">CLOUD OPERATIONS LAB</p><h1>Network health, at a glance.</h1><p className="sub">Live HTTP probes · Python services · Kubernetes deployment</p></div><div className="badge">{error ? 'API unavailable' : 'Polling every 5s'}</div></header>
    {error && <div className="error" role="alert">{error} — showing the last successful response.</div>}
    <section className="stats" aria-label="Summary"><article><label>MONITORED SERVICES</label><strong>{targets.length}</strong></article><article><label>HEALTHY & FRESH</label><strong className="green">{healthy}</strong></article><article><label>NEEDS ATTENTION</label><strong className="amber">{targets.length - healthy}</strong></article><article><label>LAST DASHBOARD REFRESH</label><strong className="time">{updated ? updated.toLocaleTimeString() : 'Waiting…'}</strong></article></section>
    <section className="panel"><div className="panel-head"><h2>Service inventory</h2><span>Measured response times, no simulated data</span></div>
      {targets.length === 0 ? <p className="empty">Waiting for probe observations. Check the worker logs if this persists.</p> : <div className="table-wrap"><table><thead><tr><th>Service</th><th>Health</th><th>Response time</th><th>HTTP status</th><th>Observed</th><th>History</th></tr></thead><tbody>{targets.map(t => <tr key={t.target}><td className="service">{t.target}</td><td><span className={`pill ${stale(t) ? 'warn' : t.healthy ? 'ok' : 'bad'}`}>{stale(t) ? 'Stale' : t.healthy ? 'Healthy' : 'Unhealthy'}</span></td><td>{t.latency_ms.toFixed(2)} ms</td><td>{t.status_code ?? 'Timeout / connection error'}</td><td>{new Date(t.observed_at).toLocaleTimeString()}</td><td><button onClick={() => setSelected(t.target)} aria-pressed={selected === t.target}>View trend →</button></td></tr>)}</tbody></table></div>}
    </section>
    <section className="panel"><div className="panel-head"><h2>{selected ? `${selected} · last 30 observations` : 'Response time trend'}</h2><span>HTTP probes include network + service time</span></div>
      {historyError ? <p className="error" role="alert">{historyError}</p> : history.length ? <div className="chart" role="img" aria-label={`${selected} latency history. Latest ${history.at(-1).latency_ms.toFixed(2)} milliseconds.`}>{history.map(t => <div key={t.id} className={`bar ${t.healthy ? '' : 'failed'}`} style={{height:`${Math.max(3, t.latency_ms/max*100)}%`}} title={`${new Date(t.observed_at).toLocaleTimeString()}: ${t.latency_ms.toFixed(2)} ms, HTTP ${t.status_code ?? 'error'}`} />)}</div> : <p className="empty">Select a service to inspect its response times.</p>}
    </section><footer>NetOps EKS · Single PostgreSQL instance for learning · Data expires after 7 days · Stale after 30s</footer>
  </main>;
}
createRoot(document.getElementById('root')).render(<App />);
