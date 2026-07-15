"""SQLite-backed persistence for tickets, enrichments, clusters and alerts.

Chosen for zero-config durability: the entire platform persists to a single file
(``vibecheck.db``) with no server, so demos and CI are self-contained. The schema
and query surface map cleanly onto PostgreSQL for production — swap the DSN and
the SQL is portable. Embeddings are stored as JSON blobs; at scale they live in a
vector DB (see :mod:`vibecheck.core.vectorindex`) and only ids are kept here.
"""

from __future__ import annotations

import json
import sqlite3
import time
from typing import Optional, Sequence

from ..core.models import Alert, Cluster, EnrichedTicket, Enrichment, Ticket
from ..errors import StorageError

_SCHEMA = """
CREATE TABLE IF NOT EXISTS tickets (
    id TEXT PRIMARY KEY,
    text TEXT NOT NULL,
    source TEXT,
    channel TEXT,
    customer_id TEXT,
    created_at REAL,
    metadata TEXT,
    feature_area TEXT,
    is_bug INTEGER,
    is_feature_request INTEGER,
    bug_severity INTEGER,
    sentiment REAL,
    churn_risk TEXT,
    summary TEXT,
    embedding TEXT,
    cluster_id TEXT,
    noise INTEGER DEFAULT 0,
    noise_reason TEXT
);
CREATE INDEX IF NOT EXISTS idx_tickets_cluster ON tickets(cluster_id);
CREATE INDEX IF NOT EXISTS idx_tickets_area ON tickets(feature_area);
CREATE INDEX IF NOT EXISTS idx_tickets_created ON tickets(created_at);

CREATE TABLE IF NOT EXISTS clusters (
    id TEXT PRIMARY KEY,
    label TEXT,
    centroid TEXT,
    member_ids TEXT,
    dominant_feature_area TEXT,
    avg_severity REAL,
    avg_sentiment REAL,
    high_churn_share REAL,
    emerging INTEGER,
    created_at REAL,
    updated_at REAL
);

CREATE TABLE IF NOT EXISTS alerts (
    id TEXT PRIMARY KEY,
    cluster_id TEXT,
    severity INTEGER,
    title TEXT,
    detail TEXT,
    channels TEXT,
    created_at REAL
);
"""


class Store:
    def __init__(self, path: str = "vibecheck.db") -> None:
        self.path = path
        try:
            self._conn = sqlite3.connect(path)
            self._conn.row_factory = sqlite3.Row
            self._conn.executescript(_SCHEMA)
            self._conn.commit()
        except sqlite3.Error as exc:  # pragma: no cover
            raise StorageError(f"cannot open database {path}: {exc}") from exc

    # ---- tickets --------------------------------------------------------

    def save_enriched(self, et: EnrichedTicket, noise: bool = False, noise_reason: str = "") -> None:
        t, e = et.ticket, et.enrichment
        self._conn.execute(
            """INSERT OR REPLACE INTO tickets
               (id,text,source,channel,customer_id,created_at,metadata,
                feature_area,is_bug,is_feature_request,bug_severity,sentiment,
                churn_risk,summary,embedding,cluster_id,noise,noise_reason)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (t.id, t.text, t.source, t.channel, t.customer_id, t.created_at, json.dumps(t.metadata),
             e.feature_area, int(e.is_bug), int(e.is_feature_request), e.bug_severity, e.sentiment,
             e.churn_risk, e.summary, json.dumps(et.embedding), et.cluster_id, int(noise), noise_reason),
        )
        self._conn.commit()

    def save_noise(self, ticket: Ticket, reason: str) -> None:
        self._conn.execute(
            """INSERT OR REPLACE INTO tickets
               (id,text,source,channel,customer_id,created_at,metadata,noise,noise_reason)
               VALUES (?,?,?,?,?,?,?,1,?)""",
            (ticket.id, ticket.text, ticket.source, ticket.channel, ticket.customer_id,
             ticket.created_at, json.dumps(ticket.metadata), reason),
        )
        self._conn.commit()

    def iter_enriched(self, since: float = 0.0, exclude_noise: bool = True) -> list[EnrichedTicket]:
        q = "SELECT * FROM tickets WHERE created_at >= ?"
        if exclude_noise:
            q += " AND noise = 0"
        q += " ORDER BY created_at"
        out: list[EnrichedTicket] = []
        for r in self._conn.execute(q, (since,)):
            if r["feature_area"] is None:
                continue
            out.append(_row_to_enriched(r))
        return out

    def count_tickets(self, exclude_noise: bool = True) -> int:
        q = "SELECT COUNT(*) AS n FROM tickets"
        if exclude_noise:
            q += " WHERE noise = 0"
        return int(self._conn.execute(q).fetchone()["n"])

    # ---- clusters -------------------------------------------------------

    def upsert_cluster(self, c: Cluster) -> None:
        self._conn.execute(
            """INSERT OR REPLACE INTO clusters
               (id,label,centroid,member_ids,dominant_feature_area,avg_severity,
                avg_sentiment,high_churn_share,emerging,created_at,updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (c.id, c.label, json.dumps(c.centroid), json.dumps(c.member_ids),
             c.dominant_feature_area, c.avg_severity, c.avg_sentiment, c.high_churn_share,
             int(c.emerging), c.created_at, c.updated_at),
        )
        self._conn.commit()

    def upsert_clusters(self, clusters: Sequence[Cluster]) -> None:
        for c in clusters:
            self.upsert_cluster(c)

    def load_clusters(self) -> list[Cluster]:
        rows = self._conn.execute("SELECT * FROM clusters").fetchall()
        return [_row_to_cluster(r) for r in rows]

    def top_clusters(self, limit: int = 20, order_by: str = "avg_severity") -> list[Cluster]:
        allowed = {"avg_severity", "avg_sentiment", "high_churn_share", "updated_at"}
        col = order_by if order_by in allowed else "avg_severity"
        rows = self._conn.execute(
            f"SELECT * FROM clusters ORDER BY {col} DESC, updated_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [_row_to_cluster(r) for r in rows]

    # ---- alerts ---------------------------------------------------------

    def save_alert(self, a: Alert) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO alerts (id,cluster_id,severity,title,detail,channels,created_at) VALUES (?,?,?,?,?,?,?)",
            (a.id, a.cluster_id, a.severity, a.title, a.detail, json.dumps(a.channels), a.created_at),
        )
        self._conn.commit()

    def recent_alerts(self, limit: int = 50) -> list[Alert]:
        rows = self._conn.execute(
            "SELECT * FROM alerts ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [Alert(id=r["id"], cluster_id=r["cluster_id"], severity=r["severity"],
                      title=r["title"], detail=r["detail"], channels=json.loads(r["channels"] or "[]"),
                      created_at=r["created_at"]) for r in rows]

    # ---- analytics ------------------------------------------------------

    def feature_area_breakdown(self) -> list[dict]:
        rows = self._conn.execute(
            """SELECT feature_area AS area, COUNT(*) AS n, AVG(bug_severity) AS sev,
                      AVG(sentiment) AS sent
               FROM tickets WHERE noise = 0 AND feature_area IS NOT NULL
               GROUP BY feature_area ORDER BY n DESC"""
        ).fetchall()
        return [{"feature_area": r["area"], "count": r["n"],
                 "avg_severity": round(r["sev"] or 0, 2), "avg_sentiment": round(r["sent"] or 0, 3)}
                for r in rows]

    def stats(self) -> dict:
        c = self._conn.execute(
            "SELECT COUNT(*) AS total, SUM(noise) AS noise, SUM(is_bug) AS bugs, "
            "SUM(is_feature_request) AS features FROM tickets"
        ).fetchone()
        clusters = self._conn.execute("SELECT COUNT(*) AS n FROM clusters").fetchone()["n"]
        return {"total_tickets": c["total"] or 0, "noise_filtered": c["noise"] or 0,
                "bugs": c["bugs"] or 0, "feature_requests": c["features"] or 0,
                "clusters": clusters}

    def close(self) -> None:
        try:
            self._conn.close()
        except sqlite3.Error:
            pass


def _row_to_enriched(r: sqlite3.Row) -> EnrichedTicket:
    ticket = Ticket(id=r["id"], text=r["text"], source=r["source"] or "other",
                    channel=r["channel"] or "support", customer_id=r["customer_id"] or "",
                    created_at=r["created_at"] or time.time(),
                    metadata=json.loads(r["metadata"] or "{}"))
    enr = Enrichment(feature_area=r["feature_area"], is_bug=bool(r["is_bug"]),
                     is_feature_request=bool(r["is_feature_request"]), bug_severity=r["bug_severity"] or 0,
                     sentiment=r["sentiment"] or 0.0, churn_risk=r["churn_risk"] or "low",
                     summary=r["summary"] or "")
    return EnrichedTicket(ticket=ticket, enrichment=enr,
                          embedding=json.loads(r["embedding"] or "[]"), cluster_id=r["cluster_id"])


def _row_to_cluster(r: sqlite3.Row) -> Cluster:
    return Cluster(id=r["id"], label=r["label"] or "", centroid=json.loads(r["centroid"] or "[]"),
                   member_ids=json.loads(r["member_ids"] or "[]"),
                   dominant_feature_area=r["dominant_feature_area"] or "",
                   avg_severity=r["avg_severity"] or 0.0, avg_sentiment=r["avg_sentiment"] or 0.0,
                   high_churn_share=r["high_churn_share"] or 0.0, emerging=bool(r["emerging"]),
                   created_at=r["created_at"] or time.time(), updated_at=r["updated_at"] or time.time())
