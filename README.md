<div align="center">

# VibeCheck-AI

### AI-powered customer feedback & product analytics engine

Ingests unstructured customer feedback — support tickets, app reviews, chats —
and turns it into an **auto-updating, prioritised engineering roadmap**.
Enrich → cluster → prioritise → route. In the spirit of Enterpret / Viable.

[![CI](https://github.com/avase33/vibecheck-ai/actions/workflows/ci.yml/badge.svg)](https://github.com/avase33/vibecheck-ai/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.10%20|%203.11%20|%203.12-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Code style: ruff](https://img.shields.io/badge/lint-ruff-000000.svg)](https://github.com/astral-sh/ruff)

</div>

---

## Why

Product and engineering teams drown in feedback across a dozen channels. The
signal *which recurring problems are actually hurting retention*  is buried in
noise. VibeCheck-AI reads every message, structures it, groups recurring issues
with unsupervised ML, and surfaces a ranked list of what to fix first, routing
the urgent, churn-driving topics straight to Slack and Jira.

## What makes it interesting (the ML)

- **Incremental, density-aware clustering.** A streaming, HDBSCAN-inspired
  clusterer discovers *emerging* topics each night by assigning new tickets to the
  nearest topic centroid or spawning a new one **without retraining** a global
  model. Provisional clusters are promoted only after reaching a min-size density
  threshold, so singletons never pollute the roadmap.
- **Deterministic metadata enrichment (guaranteed schema).** Every ticket yields a
  *valid* structured record `feature_area`, `bug_severity` (0–5),
  `churn_risk`, `sentiment`, … Instructor/Anthropic output is parsed, coerced and
  **repaired** against the schema (clamps bad numbers, fixes bad enums), with a
  deterministic fallback. The pipeline can never emit malformed data.
- **Self-healing noise filter.** Content-free messages ("Hi", "Thanks!",
  out-of-office auto-replies, bare URLs) are dropped *before* they hit the vector
  store — with an auditable reason each — protecting topic quality and write cost.

## Proof of scale

- **LLM cache** collapses repetitive feedback into free lookups the benchmark
  reports the exact **% of enrichment API calls avoided** (typically ~40% on
  realistic data).
- **Async ingest** decouples webhook latency from enrichment; workers scale
  horizontally behind Redis/Celery.

Run it yourself:

```bash
python benchmarks/bench.py -n 5000
```

## Quickstart (zero external services)

```bash
pip install -e .

# 1) Flood the engine with 5,000 realistic mock tickets and see the roadmap
python scripts/generate_mock_tickets.py

# or, in one command:
vibecheck demo --count 2000
```

Example output:

```
Ingested 5000 tickets in 0.9s (5,400 tickets/sec)
  accepted=4100  noise_filtered=900  topics=28  bugs=1700  cache_hit_rate=63%  alerts=6

Top roadmap:
   1. [ 84.2] Billing               size=340  sev=4.6  (high severity, 41% churn-risk mentions, 340 reports)
   2. [ 77.9] Reliability           size=295  sev=5.0  (high severity, emerging/spiking)
   3. [ 61.3] Authentication        size=210  sev=4.1  (high severity, 210 reports)
   ...
```

> Everything above runs with **no API keys, no Redis, no database server** the
> platform ships pure-Python defaults (mock enricher, hashing embeddings,
> in-memory queue, SQLite). Real adapters switch on via environment variables.

## Run the API + dashboard

```bash
pip install -e ".[server]"
python scripts/generate_mock_tickets.py -n 5000   # seed data
vibecheck serve                                   # http://localhost:8000
```

- `GET /` — built-in analytics dashboard (React via CDN, no build step)
- `POST /webhook` inbound feedback (Zendesk/Intercom/app-store shape)
- `GET /roadmap`, `/clusters`, `/feature-areas`, `/alerts`, `/stats`, `/metrics`

### Production frontend (Next.js)

A componentised Next.js + TypeScript + Recharts dashboard lives in
[`frontend/`](frontend/):

```bash
cd frontend && npm install && npm run dev   # http://localhost:3000
```

## Full stack (Docker Compose)

```bash
docker compose up --build
```

Brings up the web-api, ingestion worker, Redis, Qdrant, Prometheus + Grafana, and
the Next.js frontend.

## Architecture

```
webhooks → queue(Redis/Celery) → ingestion-worker
             (noise filter → cache-backed enrichment → embedding → persist)
                     │
          Postgres + Qdrant/PGVector
                     │  nightly
          analytics-pipeline (incremental clustering → roadmap)
                     │  emerging / severe
          agent-service (LangGraph-style) → Slack / Jira
                     │
          web-api read models → Next.js dashboard
```

See [`docs/architecture.md`](docs/architecture.md) for the full design.

## Configuration

Copy `.env.example` to `.env`. Highlights:

| Variable | Default | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | — | switch enrichment to Claude (else deterministic mock) |
| `VIBECHECK_EMBEDDINGS` | `hashing` | `sentence-transformers` for neural embeddings |
| `VIBECHECK_QUEUE` | `memory` | `celery` for Redis/RabbitMQ |
| `VIBECHECK_VECTOR` | `memory` | `qdrant` for scaled vector search |
| `VIBECHECK_CLUSTER_SIM` | `0.55` | cosine threshold to join a topic |
| `SLACK_WEBHOOK` / `JIRA_URL` | | real alert routing |

## Repository layout

```
vibecheck/
  core/          tokenizer, hashing embeddings, noise filter,
                 enrichment (schema-guaranteed), incremental clustering, LLM cache
  services/      ingestion worker, analytics batch, alerting agent, web-api, dashboard
  storage/       SQLite/Postgres store
  pipeline.py    per-ticket ingest pipeline
  engine.py      high-level façade (CLI/API/tests)
  cli.py         `vibecheck` command
  mockdata.py    realistic synthetic feedback generator
scripts/         generate_mock_tickets.py
benchmarks/      throughput + cache-savings benchmark
frontend/        Next.js + TypeScript + Recharts dashboard
infra/           Terraform (ECR, ECS, ElastiCache, RDS)
monitoring/      Prometheus + Grafana
docker-compose.yml, Dockerfile, .github/workflows/ci.yml
```

## Development

```bash
pip install -e ".[server,dev]"
pytest --cov=vibecheck
ruff check vibecheck scripts
python verify_vibecheck.py      # offline end-to-end self-check
```

## License

MIT © Akhil Vase
