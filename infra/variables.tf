variable "project" {
  type    = string
  default = "vibecheck"
}

variable "environment" {
  type    = string
  default = "production"
}

variable "region" {
  type    = string
  default = "us-east-1"
}

variable "redis_node_type" {
  type    = string
  default = "cache.t4g.micro"
}

variable "db_instance_class" {
  type    = string
  default = "db.t4g.micro"
}

variable "db_username" {
  type    = string
  default = "vibecheck"
}

variable "db_password" {
  type      = string
  sensitive = true
}
