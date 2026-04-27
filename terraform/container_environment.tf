resource "azurerm_log_analytics_workspace" "main" {
  name                = "log-${var.prefix}"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  sku                 = "PerGB2018"
  retention_in_days   = 30

  tags = var.tags
}

resource "azurerm_container_app_environment" "main" {
  name                       = "cae-${var.prefix}"
  location                   = azurerm_resource_group.main.location
  resource_group_name        = azurerm_resource_group.main.name
  log_analytics_workspace_id = azurerm_log_analytics_workspace.main.id

  tags = var.tags

  lifecycle {
    # An environment imported from Azure often has no Log Analytics link in the read model, while
    # this config sets `log_analytics_workspace_id`. For this resource, that diff forces a full
    # **replace** (destroy + recreate) of the entire managed environment. Ignore so we keep the
    # existing CAE; link diagnostics in Portal / `az containerapp env update` if needed.
    ignore_changes = [
      log_analytics_workspace_id,
      tags,
    ]
  }

  # Provisioning often exceeds Terraform’s default (~60m); CAE + VNet injection can take 90m+ in eastus.
  timeouts {
    create = "180m"
    read   = "10m"
    update = "180m"
    delete = "120m"
  }
}
