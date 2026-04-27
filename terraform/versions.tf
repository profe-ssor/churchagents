terraform {
  required_version = ">= 1.5.0"

  required_providers {
    azurerm = {
      source = "hashicorp/azurerm"
      # 3.115+ improves LRO polling for Redis / Container Apps; stay on 3.x.
      version = ">= 3.115.0, < 4.0.0"
    }
  }
}
