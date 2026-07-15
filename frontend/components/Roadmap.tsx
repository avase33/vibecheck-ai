import type { RoadmapItem } from "@/lib/api";

export function Roadmap({ items }: { items: RoadmapItem[] }) {
  return (
    <div className="card">
      <h2>Prioritised roadmap</h2>
      {items.length ? (
        items.map((it, i) => (
          <div className="row" key={it.id || i}>
            <div className="rank">{i + 1}</div>
            <div className="grow">
              <div className="title">{it.label || it.dominant_feature_area || "(topic)"}</div>
              <div className="sub">
                {it.size} reports · sev {it.avg_severity} · {it.rationale}
              </div>
              <div className="sev">
                <i style={{ width: `${Math.min(100, (it.avg_severity / 5) * 100)}%` }} />
              </div>
            </div>
            {it.emerging ? <span className="pill emerging">emerging</span> : null}
            <div className="score">{Math.round(it.priority_score)}</div>
          </div>
        ))
      ) : (
        <div className="muted">No data yet — POST feedback to /webhook or run “vibecheck demo”.</div>
      )}
    </div>
  );
}
