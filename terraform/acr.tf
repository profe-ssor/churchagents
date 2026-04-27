resource "azurerm_container_registry" "main" {
  name                = replace("${var.prefix}acr", "-", "")
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  sku                 = var.acr_sku
  admin_enabled       = true

  tags = var.tags
}

locals {
  acr_server = azurerm_container_registry.main.login_server
  # Images must exist in ACR before Container Apps start (build + push after first apply or pre-seed).
  celery_image       = "${local.acr_server}/churchagents-celery:${var.image_tag}"
  orchestrator_image = "${local.acr_server}/churchagents-orchestrator:${var.image_tag}"
  dashboard_image    = "${local.acr_server}/churchagents-dashboard:${var.image_tag}"
}
