# Infrastructure (Terraform)

Provisions the production footprint for VibeCheck-AI on AWS:

- **ECR** — registry for the `web-api` / `ingestion-worker` images
- **ECS (Fargate)** — runs the services with Container Insights
- **ElastiCache (Redis)** — Celery broker + LLM enrichment cache
- **RDS (Postgres)** — durable ticket / cluster / alert storage

```bash
cd infra
terraform init
terraform plan  -var "db_password=$(openssl rand -base64 24)"
terraform apply -var "db_password=..."
```

> This is a starting point sized for a single environment. For multi-env, wrap in
> workspaces or a module and add an ALB + task definitions for each service. The
> app is 12-factor: everything it needs comes from environment variables
> (`REDIS_URL`, `VIBECHECK_DB`, `QDRANT_URL`, `ANTHROPIC_API_KEY`, …).
