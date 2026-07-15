import type { AlertItem } from "@/lib/api";

export function Alerts({ alerts }: { alerts: AlertItem[] }) {
  return (
    <div className="card">
      <h2>Alerts routed</h2>
      {alerts.length ? (
        alerts.map((a, i) => (
          <div className="alert" key={a.id || i}>
            <span className="chan">{(a.channels || []).join("+") || "—"}</span>
            <div className="grow">
              <div>{a.title}</div>
              <div className="sub">{a.detail}</div>
            </div>
          </div>
        ))
      ) : (
        <div className="muted">No alerts routed.</div>
      )}
    </div>
  );
}
