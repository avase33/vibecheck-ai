"""FastAPI web-api.

Exposes the ingestion webhook and the read models the dashboard consumes:

    POST /webhook          inbound feedback (Zendesk/Intercom/app-store shape)
    POST /ingest           ingest a batch of plain messages
    POST /analyze          run the nightly analytics batch + alerting on demand
    GET  /roadmap          prioritised roadmap
    GET  /clusters         topic clusters
    GET  /feature-areas    volume/severity/sentiment per area
    GET  /alerts           recently routed alerts
    GET  /stats            platform + cache stats
    GET  /                 the built-in dashboard (zero-build React via CDN)

FastAPI/uvicorn are optional dependencies; import this module only when running
the server (``vibecheck serve`` or ``uvicorn``).
"""

from __future__ import annotations

from typing import Any, Optional

from ..config import Settings
from ..core.models import Ticket
from ..engine import VibeCheck


def create_app(db: str = "vibecheck.db", settings: Optional[Settings] = None):
    from fastapi import FastAPI, Body
    from fastapi.responses import HTMLResponse, JSONResponse
    from pydantic import BaseModel

    cfg = settings or Settings.from_env()
    cfg.database_url = db
    app = FastAPI(title="VibeCheck-AI", version="0.1.0",
                  description="AI-powered customer feedback & product analytics engine")

    def engine() -> VibeCheck:
        # one engine per request keeps SQLite connections thread-safe
        return VibeCheck(cfg)

    class Feedback(BaseModel):
        text: str
        source: str = "other"
        channel: str = "support"
        customer_id: str = ""

    class Batch(BaseModel):
        messages: list[str]

    @app.post("/webhook")
    def webhook(event: dict = Body(...)) -> dict:
        vc = engine()
        text = (event.get("text") or event.get("body") or event.get("comment") or "").strip()
        res = vc.pipeline.ingest(Ticket(
            text=text, source=str(event.get("source", "other")),
            channel=event.get("channel", "support"),
            customer_id=str(event.get("customer_id", ""))))
        vc.close()
        return {"ticket_id": res.ticket_id, "accepted": res.accepted, "noise_reason": res.noise_reason}

    @app.post("/ingest")
    def ingest(batch: Batch) -> dict:
        vc = engine()
        out = vc.ingest_many(Ticket(text=m) for m in batch.messages if m.strip())
        vc.close()
        return out

    @app.post("/analyze")
    def analyze() -> dict:
        vc = engine()
        clusters = vc.analytics.rebuild()
        alerts = vc.run_alerts()
        out = {"clusters": len(clusters), "alerts": len(alerts)}
        vc.close()
        return out

    @app.get("/roadmap")
    def roadmap(top: int = 15) -> Any:
        vc = engine()
        out = [it.to_dict() for it in vc.roadmap(limit=top)]
        vc.close()
        return JSONResponse(out)

    @app.get("/clusters")
    def clusters(top: int = 30) -> Any:
        vc = engine()
        out = [c.to_dict() for c in vc.store.top_clusters(limit=top)]
        vc.close()
        return JSONResponse(out)

    @app.get("/feature-areas")
    def feature_areas() -> Any:
        vc = engine()
        out = vc.store.feature_area_breakdown()
        vc.close()
        return JSONResponse(out)

    @app.get("/alerts")
    def alerts(limit: int = 50) -> Any:
        vc = engine()
        out = [a.to_dict() for a in vc.store.recent_alerts(limit=limit)]
        vc.close()
        return JSONResponse(out)

    @app.get("/stats")
    def stats() -> dict:
        vc = engine()
        out = vc.stats()
        vc.close()
        return out

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "version": "0.1.0"}

    @app.get("/metrics")
    def metrics():
        from fastapi.responses import PlainTextResponse

        vc = engine()
        s = vc.stats()
        vc.close()
        cache = s.get("cache", {})
        lines = [
            "# HELP vibecheck_tickets_ingested_total Total accepted tickets.",
            "# TYPE vibecheck_tickets_ingested_total counter",
            f"vibecheck_tickets_ingested_total {s.get('total_tickets', 0)}",
            "# HELP vibecheck_tickets_noise_total Tickets dropped by the noise filter.",
            "# TYPE vibecheck_tickets_noise_total counter",
            f"vibecheck_tickets_noise_total {s.get('noise_filtered', 0)}",
            "# HELP vibecheck_clusters_total Topic clusters discovered.",
            "# TYPE vibecheck_clusters_total gauge",
            f"vibecheck_clusters_total {s.get('clusters', 0)}",
            "# HELP vibecheck_bugs_total Tickets classified as bugs.",
            "# TYPE vibecheck_bugs_total counter",
            f"vibecheck_bugs_total {s.get('bugs', 0)}",
            "# HELP vibecheck_cache_hits_total LLM enrichment cache hits.",
            "# TYPE vibecheck_cache_hits_total counter",
            f"vibecheck_cache_hits_total {cache.get('hits', 0)}",
            "# HELP vibecheck_cache_misses_total LLM enrichment cache misses.",
            "# TYPE vibecheck_cache_misses_total counter",
            f"vibecheck_cache_misses_total {cache.get('misses', 0)}",
        ]
        return PlainTextResponse("\n".join(lines) + "\n")

    @app.get("/", response_class=HTMLResponse)
    def dashboard() -> str:
        from .dashboard import DASHBOARD_HTML
        return DASHBOARD_HTML

    return app


def run_server(host: str = "127.0.0.1", port: int = 8000, db: str = "vibecheck.db") -> None:  # pragma: no cover
    import uvicorn

    uvicorn.run(create_app(db=db), host=host, port=port)
