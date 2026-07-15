"""Built-in analytics dashboard.

A single self-contained HTML page (React + Chart.js from CDN, no build step)
served by the web-api at ``/``. It calls the JSON endpoints and renders the
prioritised roadmap, topic clusters, feature-area breakdown and routed alerts —
the same views a Next.js frontend (see ``frontend/``) renders in production.
"""

from __future__ import annotations

DASHBOARD_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>VibeCheck-AI — Product Analytics</title>
<script crossorigin src="https://unpkg.com/react@18/umd/react.production.min.js"></script>
<script crossorigin src="https://unpkg.com/react-dom@18/umd/react-dom.production.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
<style>
  :root { --bg:#0b1020; --panel:#141b2e; --panel2:#1b2440; --text:#e8ecf6; --muted:#93a0bd;
          --accent:#6c8cff; --good:#39d98a; --warn:#ffb020; --bad:#ff5c72; --line:#25304d; }
  * { box-sizing:border-box; }
  body { margin:0; font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;
         background:linear-gradient(180deg,#0b1020,#0d1226); color:var(--text); }
  header { padding:20px 28px; border-bottom:1px solid var(--line); display:flex;
           align-items:center; gap:14px; }
  header h1 { font-size:19px; margin:0; letter-spacing:.3px; }
  .badge { font-size:11px; color:var(--muted); border:1px solid var(--line); padding:3px 8px; border-radius:20px; }
  .wrap { padding:22px 28px; max-width:1240px; margin:0 auto; }
  .kpis { display:grid; grid-template-columns:repeat(5,1fr); gap:14px; margin-bottom:22px; }
  .kpi { background:var(--panel); border:1px solid var(--line); border-radius:14px; padding:16px; }
  .kpi .n { font-size:26px; font-weight:700; }
  .kpi .l { font-size:12px; color:var(--muted); margin-top:4px; }
  .grid { display:grid; grid-template-columns:1.4fr 1fr; gap:18px; }
  .card { background:var(--panel); border:1px solid var(--line); border-radius:14px; padding:18px; margin-bottom:18px; }
  .card h2 { font-size:14px; margin:0 0 14px; color:var(--muted); text-transform:uppercase; letter-spacing:.6px; }
  .row { display:flex; align-items:center; gap:12px; padding:10px 0; border-bottom:1px solid var(--line); }
  .row:last-child { border-bottom:none; }
  .rank { width:26px; height:26px; border-radius:8px; background:var(--panel2); display:flex;
          align-items:center; justify-content:center; font-size:12px; color:var(--muted); }
  .grow { flex:1; min-width:0; }
  .title { font-weight:600; font-size:14px; }
  .sub { font-size:12px; color:var(--muted); margin-top:2px; }
  .score { font-variant-numeric:tabular-nums; font-weight:700; }
  .pill { font-size:11px; padding:2px 8px; border-radius:20px; border:1px solid var(--line); }
  .pill.emerging { color:var(--warn); border-color:#5a4620; background:#241d10; }
  .sev { height:6px; border-radius:4px; background:var(--panel2); overflow:hidden; margin-top:8px; }
  .sev > i { display:block; height:100%; background:linear-gradient(90deg,var(--good),var(--warn),var(--bad)); }
  .alert { display:flex; gap:10px; padding:10px 0; border-bottom:1px solid var(--line); font-size:13px; }
  .chan { font-size:10px; text-transform:uppercase; letter-spacing:.5px; padding:2px 7px; border-radius:6px;
          background:var(--panel2); color:var(--accent); align-self:flex-start; }
  .muted { color:var(--muted); }
  button.reload { margin-left:auto; background:var(--accent); color:#0b1020; border:none; font-weight:600;
                  padding:8px 14px; border-radius:9px; cursor:pointer; }
  @media (max-width:900px){ .grid{grid-template-columns:1fr;} .kpis{grid-template-columns:repeat(2,1fr);} }
</style>
</head>
<body>
<div id="root"></div>
<script>
const {useState,useEffect} = React;
const e = React.createElement;
const api = (p)=>fetch(p).then(r=>r.json());

function Kpi({n,l}){ return e('div',{className:'kpi'}, e('div',{className:'n'},n), e('div',{className:'l'},l)); }

function App(){
  const [stats,setStats]=useState(null);
  const [roadmap,setRoadmap]=useState([]);
  const [areas,setAreas]=useState([]);
  const [alerts,setAlerts]=useState([]);
  const [loading,setLoading]=useState(true);

  async function load(){
    setLoading(true);
    try { await api('/analyze'); } catch(e){}
    const [s,r,a,al] = await Promise.all([
      api('/stats'), api('/roadmap?top=12'), api('/feature-areas'), api('/alerts?limit=12')
    ]);
    setStats(s); setRoadmap(r); setAreas(a); setAlerts(al); setLoading(false);
  }
  useEffect(()=>{ load(); },[]);
  useEffect(()=>{
    if(!areas.length) return;
    const ctx=document.getElementById('areaChart'); if(!ctx) return;
    if(window._chart) window._chart.destroy();
    window._chart=new Chart(ctx,{type:'bar',data:{labels:areas.map(a=>a.feature_area),
      datasets:[{label:'tickets',data:areas.map(a=>a.count),backgroundColor:'#6c8cff'}]},
      options:{plugins:{legend:{display:false}},scales:{x:{ticks:{color:'#93a0bd'},grid:{display:false}},
      y:{ticks:{color:'#93a0bd'},grid:{color:'#25304d'}}}}});
  },[areas]);

  const cache = stats && stats.cache ? Math.round(stats.cache.hit_rate*100)+'%' : '—';
  return e('div',null,
    e('header',null,
      e('h1',null,'VibeCheck-AI'),
      e('span',{className:'badge'},'customer feedback → roadmap'),
      e('button',{className:'reload',onClick:load}, loading?'Loading…':'Refresh')
    ),
    e('div',{className:'wrap'},
      e('div',{className:'kpis'},
        e(Kpi,{n:stats?stats.total_tickets:'—',l:'tickets ingested'}),
        e(Kpi,{n:stats?stats.noise_filtered:'—',l:'noise filtered'}),
        e(Kpi,{n:stats?stats.clusters:'—',l:'topics discovered'}),
        e(Kpi,{n:stats?stats.bugs:'—',l:'bugs detected'}),
        e(Kpi,{n:cache,l:'LLM cache hit-rate'})
      ),
      e('div',{className:'grid'},
        e('div',null,
          e('div',{className:'card'},
            e('h2',null,'Prioritised roadmap'),
            roadmap.length? roadmap.map((it,i)=>e('div',{className:'row',key:it.id||i},
              e('div',{className:'rank'},i+1),
              e('div',{className:'grow'},
                e('div',{className:'title'},it.label||it.dominant_feature_area||'(topic)'),
                e('div',{className:'sub'},(it.size+' reports · sev '+it.avg_severity+' · '+(it.rationale||''))),
                e('div',{className:'sev'},e('i',{style:{width:Math.min(100,(it.avg_severity/5*100))+'%'}}))
              ),
              it.emerging? e('span',{className:'pill emerging'},'emerging'):null,
              e('div',{className:'score'},Math.round(it.priority_score))
            )) : e('div',{className:'muted'},'No data yet — POST feedback to /webhook or run "vibecheck demo".')
          )
        ),
        e('div',null,
          e('div',{className:'card'},
            e('h2',null,'Feedback by feature area'),
            e('canvas',{id:'areaChart',height:180})
          ),
          e('div',{className:'card'},
            e('h2',null,'Alerts routed'),
            alerts.length? alerts.map((a,i)=>e('div',{className:'alert',key:a.id||i},
              e('span',{className:'chan'},(a.channels||[]).join('+')||'—'),
              e('div',{className:'grow'},
                e('div',null,a.title),
                e('div',{className:'sub'},a.detail))
            )) : e('div',{className:'muted'},'No alerts routed.')
          )
        )
      )
    )
  );
}
ReactDOM.createRoot(document.getElementById('root')).render(e(App));
</script>
</body>
</html>
"""
