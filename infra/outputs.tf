output "ecr_repository_url" {
  value       = aws_ecr_repository.app.repository_url
  description = "Push web-api / worker images here."
}

output "ecs_cluster_name" {
  value = aws_ecs_cluster.this.name
}

output "redis_endpoint" {
  value = aws_elasticache_cluster.redis.cache_nodes[0].address
}

output "postgres_endpoint" {
  value = aws_db_instance.postgres.address
}
