resource "azurerm_redis_cache" "main" {
  name                 = "${var.prefix}redis"
  location             = azurerm_resource_group.main.location
  resource_group_name  = azurerm_resource_group.main.name
  capacity             = var.redis_capacity
  family               = var.redis_family
  sku_name             = var.redis_sku_name
  non_ssl_port_enabled = false
  minimum_tls_version  = "1.2"

  tags = var.tags

  # Basic tier can sit in “provisioning” for a long time; avoid default deadline. Retry apply if Azure returns LRO “Unknown”.
  timeouts {
    create = "120m"
    read   = "5m"
    update = "120m"
    delete = "120m"
  }
}

locals {
  redis_host = azurerm_redis_cache.main.hostname
  redis_key  = azurerm_redis_cache.main.primary_access_key
  # Azure TLS port is 6380; ssl_port may be null on some API versions.
  redis_port = coalesce(azurerm_redis_cache.main.ssl_port, 6380)

  # redis-py 5+ from_url: use "required" | "optional" | "none" — not ssl.CERT_* names.
  # (CERT_REQUIRED in the query string causes: Invalid SSL Certificate Requirements Flag: CERT_REQUIRED)
  redis_ssl_query = "ssl_cert_reqs=required"

  # Same DB indexes as local docker / .env.example
  celery_broker_url         = "rediss://:${local.redis_key}@${local.redis_host}:${local.redis_port}/0?${local.redis_ssl_query}"
  celery_result_backend_url = "rediss://:${local.redis_key}@${local.redis_host}:${local.redis_port}/1?${local.redis_ssl_query}"
  agent_memory_redis_url    = "rediss://:${local.redis_key}@${local.redis_host}:${local.redis_port}/2?${local.redis_ssl_query}"
}
