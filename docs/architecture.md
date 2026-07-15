# Architecture

VibeCheck-AI turns a firehose of unstructured customer feedback into a
prioritised, auto-updating engineering roadmap. It is split into an **ingest**
path (cheap, per-message, real-time) and an **analyze** path (batch, nightly),
connected by durable storage.

## Data flow

```
              webhooks (Zendesk / Intercom / App Store / G2 / email)
                                   │
                                   ▼
                          ┌─────────────────┐
                          │  web-api /webhook│  FastAPI
                          └────────┬─────────┘
                                   │  enqueue
                                   ▼
                      ┌──────────────────────────┐
                      │  message queue (Redis/    │  Celery in prod,
                      │  RabbitMQ | in-memory)    │  in-memory offline
                      └────────────┬─────────────┘
                                   │  consume
                                   ▼
          ┌──────────────────────────────────────────────────┐
          │            ingestion-worker (pipeline)            │
          │                                                   │
          │  noise filter → cache-backed enrichment →         │
          │  embedding → persist                              │
          └───────────────┬───────────────────────────────────┘
                          │ writes
                          ▼
          ┌──────────────────────────────────────────────────┐
          │  storage: Postgres (tickets/clusters/alerts)      │
          │           + Qdrant/PGVector (embeddings)          │
          └───────────────┬───────────────────────────────────┘
                          │ reads (nightly)
                          ▼
          ┌──────────────────────────────────────────────────┐
          │  analytics-pipeline (Spark/Ray | in-process)      │
          │  incremental clustering → topic stats → roadmap   │
          └───────────────┬───────────────────────────────────┘
                          │ emerging / severe topics
                          ▼
          ┌──────────────────────────────────────────────────┐
          │  agent-service (LangGraph-style state machine)    │
          │  triage → compose → dispatch(Slack | Jira)        │
          └──────────────────────────────────────────────────┘
                          │
                          ▼
             web-api read models  ──►  Next.js dashboard
```

## The three ML ideas that make it work

### 1. Incremental, density-aware clustering
Topics must *evolve*: a bug that appears tonight should form its own cluster
tonight — without retraining a global model over all history. The clusterer
(`core/clustering.py`) is a single-pass, streaming algorithm inspired by
HDBSCAN's density/min-samples idea:

- each vector joins the nearest existing cluster if cosine ≥ threshold, else
  seeds a *provisional* cluster;
- provisional clusters are promoted to real topics only once they reach
  `min_cluster_size` (the density filter — singletons never pollute the roadmap);
- centroids update as running means, so the nightly batch only needs the **new**
  tickets, not a full re-fit;
- clusters formed inside a recent window are flagged `emerging` for the
  "what's spiking" view.

### 2. Deterministic metadata enrichment (guaranteed schema)
Aggregation only works if every ticket yields the *same* structured shape.
`core/enrichment.py` always returns a valid `Enrichment`
(`feature_area`, `is_bug`, `bug_severity` 0–5, `sentiment`, `churn_risk`,
`summary`). The LLM path (Instructor/Anthropic) is wrapped in
`validate_enrichment`, which parses, coerces and repairs the model's JSON —
clamping out-of-range numbers and fixing bad enums — and falls back to the
deterministic classifier on any failure. The pipeline can therefore **never**
emit a malformed record.

### 3. Self-healing noise filter
Support streams are ~15–20% content-free ("Hi", "Thanks!", out-of-office
auto-replies, bare URLs). `core/noise.py` drops these *before* they are embedded
or clustered, with an auditable reason per message, protecting both the vector
store write path and topic quality.

## Cost & scale

- **LLM cache** (`core/cache.py`): a normalised-content cache in front of the
  enricher. Repetitive feedback ("app keeps crashing") turns most calls into free
  lookups; hit-rate directly measures API-call savings.
- **Async ingest**: the queue decouples webhook latency from enrichment, so
  spikes are absorbed and workers scale horizontally.
- **Vector search**: an exact in-memory index by default, swappable for Qdrant
  at scale via the same `add`/`search` interface.

## Offline-first design

Every heavy dependency has a pure-Python default: mock enricher, hashing
embeddings, in-memory queue and vector index, SQLite storage. The entire
platform therefore runs, tests and benchmarks with **zero external services**.
Production adapters (Anthropic, sentence-transformers, HDBSCAN, Celery/Redis,
Qdrant, Postgres, Slack/Jira) are selected by environment variables and never
change the business logic.
