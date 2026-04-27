# ─── Shared secrets pattern: ACR pull + app secrets ─────────────────────────

resource "azurerm_container_app" "celery" {
  name                         = "ca-${var.prefix}-celery"
  container_app_environment_id = azurerm_container_app_environment.main.id
  resource_group_name          = azurerm_resource_group.main.name
  revision_mode                = "Single"

  registry {
    server               = azurerm_container_registry.main.login_server
    username             = azurerm_container_registry.main.admin_username
    password_secret_name = "acr-password"
  }

  secret {
    name  = "acr-password"
    value = azurerm_container_registry.main.admin_password
  }

  secret {
    name  = "openai-api-key"
    value = var.openai_api_key
  }

  secret {
    name  = "agent-jwt-password"
    value = var.agent_jwt_password
  }

  secret {
    name  = "redis-broker"
    value = local.celery_broker_url
  }

  secret {
    name  = "redis-result"
    value = local.celery_result_backend_url
  }

  secret {
    name  = "redis-memory"
    value = local.agent_memory_redis_url
  }

  template {
    min_replicas = 1
    max_replicas = 3

    container {
      name   = "celery"
      image  = local.celery_image
      cpu    = var.celery_cpu
      memory = var.celery_memory

      env {
        name  = "DJANGO_BASE_URL"
        value = var.django_base_url
      }
      env {
        name  = "AGENT_JWT_EMAIL"
        value = var.agent_jwt_email
      }
      env {
        name        = "AGENT_JWT_PASSWORD"
        secret_name = "agent-jwt-password"
      }
      env {
        name  = "AGENT_JWT_CHURCH_ID"
        value = var.agent_jwt_church_id
      }
      env {
        name        = "OPENAI_API_KEY"
        secret_name = "openai-api-key"
      }
      env {
        name        = "CELERY_BROKER_URL"
        secret_name = "redis-broker"
      }
      env {
        name        = "CELERY_RESULT_BACKEND"
        secret_name = "redis-result"
      }
      env {
        name        = "AGENT_MEMORY_REDIS_URL"
        secret_name = "redis-memory"
      }
      env {
        name  = "VECTOR_STORE_TYPE"
        value = "chroma"
      }
      env {
        name  = "CHROMA_PERSIST_DIR"
        value = "/tmp/chroma"
      }
      env {
        name  = "OPENAI_MODEL_COMPLEX"
        value = "gpt-4.1"
      }
      env {
        name  = "OPENAI_MODEL_SIMPLE"
        value = "gpt-4.1-mini"
      }
      env {
        name  = "SUPPORT_TEAM_EMAIL"
        value = var.support_team_email
      }
    }
  }
}

resource "azurerm_container_app" "orchestrator" {
  name                         = "ca-${var.prefix}-orch"
  container_app_environment_id = azurerm_container_app_environment.main.id
  resource_group_name          = azurerm_resource_group.main.name
  revision_mode                = "Single"

  registry {
    server               = azurerm_container_registry.main.login_server
    username             = azurerm_container_registry.main.admin_username
    password_secret_name = "acr-password"
  }

  secret {
    name  = "acr-password"
    value = azurerm_container_registry.main.admin_password
  }

  secret {
    name  = "openai-api-key"
    value = var.openai_api_key
  }

  secret {
    name  = "agent-jwt-password"
    value = var.agent_jwt_password
  }

  secret {
    name  = "redis-memory"
    value = local.agent_memory_redis_url
  }

  template {
    min_replicas = 1
    max_replicas = 5

    container {
      name   = "orchestrator"
      image  = local.orchestrator_image
      cpu    = var.orchestrator_cpu
      memory = var.orchestrator_memory

      env {
        name  = "DJANGO_BASE_URL"
        value = var.django_base_url
      }
      env {
        name  = "AGENT_JWT_EMAIL"
        value = var.agent_jwt_email
      }
      env {
        name        = "AGENT_JWT_PASSWORD"
        secret_name = "agent-jwt-password"
      }
      env {
        name  = "AGENT_JWT_CHURCH_ID"
        value = var.agent_jwt_church_id
      }
      env {
        name        = "OPENAI_API_KEY"
        secret_name = "openai-api-key"
      }
      env {
        name        = "AGENT_MEMORY_REDIS_URL"
        secret_name = "redis-memory"
      }
      env {
        name  = "AGENTS_HTTP_HOST"
        value = "0.0.0.0"
      }
      env {
        name  = "AGENTS_HTTP_PORT"
        value = "8001"
      }
      env {
        name  = "VECTOR_STORE_TYPE"
        value = "chroma"
      }
      env {
        name  = "CHROMA_PERSIST_DIR"
        value = "/tmp/chroma"
      }
      env {
        name  = "SUPPORT_TEAM_EMAIL"
        value = var.support_team_email
      }
    }
  }

  ingress {
    external_enabled           = true
    target_port                = 8001
    transport                  = "auto"
    allow_insecure_connections = false

    traffic_weight {
      percentage      = 100
      latest_revision = true
    }
  }

  depends_on = [azurerm_container_app.celery]
}

locals {
  # Use ingress FQDN (stable). latest_revision_fqdn embeds a revision suffix and returns 404 after new revisions.
  orchestrator_public_url = format("https://%s", azurerm_container_app.orchestrator.ingress[0].fqdn)
}

resource "azurerm_container_app" "dashboard" {
  name                         = "ca-${var.prefix}-web"
  container_app_environment_id = azurerm_container_app_environment.main.id
  resource_group_name          = azurerm_resource_group.main.name
  revision_mode                = "Single"

  registry {
    server               = azurerm_container_registry.main.login_server
    username             = azurerm_container_registry.main.admin_username
    password_secret_name = "acr-password"
  }

  secret {
    name  = "acr-password"
    value = azurerm_container_registry.main.admin_password
  }

  secret {
    name  = "django-agent-password"
    value = var.agent_jwt_password
  }

  template {
    min_replicas = 1
    max_replicas = 5

    container {
      name   = "dashboard"
      image  = local.dashboard_image
      cpu    = var.dashboard_cpu
      memory = var.dashboard_memory

      env {
        name  = "NODE_ENV"
        value = "production"
      }
      env {
        name  = "PORT"
        value = "3000"
      }
      env {
        name  = "HOSTNAME"
        value = "0.0.0.0"
      }
      env {
        name  = "NEXT_PUBLIC_DJANGO_URL"
        value = var.django_base_url
      }
      env {
        name  = "AGENTS_API_URL"
        value = local.orchestrator_public_url
      }
      env {
        name  = "DJANGO_AGENT_EMAIL"
        value = var.agent_jwt_email
      }
      env {
        name        = "DJANGO_AGENT_PASSWORD"
        secret_name = "django-agent-password"
      }
    }
  }

  ingress {
    external_enabled           = true
    target_port                = 3000
    transport                  = "auto"
    allow_insecure_connections = false

    traffic_weight {
      percentage      = 100
      latest_revision = true
    }
  }

  depends_on = [azurerm_container_app.orchestrator]
}
