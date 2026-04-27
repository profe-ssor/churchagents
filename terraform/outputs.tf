output "resource_group_name" {
  value       = azurerm_resource_group.main.name
  description = "Resource group containing ChurchAgents Azure resources."
}

output "acr_login_server" {
  value       = azurerm_container_registry.main.login_server
  description = "docker login <this> before docker push."
}

output "redis_hostname" {
  value       = azurerm_redis_cache.main.hostname
  description = "Azure Cache for Redis hostname (TLS)."
}

output "orchestrator_https_url" {
  value       = local.orchestrator_public_url
  description = "Public URL for FastAPI orchestrator (AGENTS_API_URL)."
}

output "dashboard_https_url" {
  value       = format("https://%s", azurerm_container_app.dashboard.ingress[0].fqdn)
  description = "Public URL for the Next.js dashboard (stable ingress hostname)."
}

output "push_images_help" {
  value = <<-EOT
    Build and push images (from churchagents repo root), then update Container Apps if needed:

      az acr login --name ${azurerm_container_registry.main.name}
      docker build -f docker/Dockerfile -t ${local.acr_server}/churchagents-celery:latest .
      docker push ${local.acr_server}/churchagents-celery:latest

    Orchestrator and dashboard Dockerfiles: see docs/azure-deployment.md §12.
  EOT
}
