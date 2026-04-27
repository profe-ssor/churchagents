variable "location" {
  type        = string
  description = "Azure region (e.g. eastus, westeurope)."
  default     = "eastus"
}

variable "prefix" {
  type        = string
  description = "Short prefix for resource names (letters/numbers only where required)."
  default     = "churchagents"
}

variable "django_base_url" {
  type        = string
  description = "Render Django base URL, e.g. https://your-api.onrender.com (no trailing slash)."
}

variable "openai_api_key" {
  type        = string
  sensitive   = true
  description = "OpenAI API key for agents and orchestrator."
}

variable "agent_jwt_email" {
  type        = string
  description = "Django service user email for MCP/API calls."
}

variable "agent_jwt_password" {
  type        = string
  sensitive   = true
  description = "Django service user password."
}

variable "agent_jwt_church_id" {
  type        = string
  default     = ""
  description = "Optional church UUID for platform admin JWT (AGENT_JWT_CHURCH_ID → X-Church-ID for Django outbound email/SMS and alerts)."
}

variable "image_tag" {
  type        = string
  description = "Tag pushed to ACR for all three images."
  default     = "latest"
}

variable "celery_cpu" {
  type    = number
  default = 1.0
}

variable "celery_memory" {
  type    = string
  default = "2Gi"
}

variable "orchestrator_cpu" {
  type    = number
  default = 0.5
}

variable "orchestrator_memory" {
  type    = string
  default = "1Gi"
}

variable "dashboard_cpu" {
  type    = number
  default = 0.5
}

variable "dashboard_memory" {
  type    = string
  default = "1Gi"
}

variable "redis_capacity" {
  type        = number
  description = "Azure Redis Basic C0 = 0, C1 = 1."
  default     = 0
}

variable "redis_family" {
  type    = string
  default = "C"
}

variable "redis_sku_name" {
  type    = string
  default = "Basic"
}

variable "acr_sku" {
  type    = string
  default = "Basic"
}

variable "support_team_email" {
  type        = string
  description = "Support inbox for notify_support_team / escalations (orchestrator + Celery)."
  default     = ""
}

variable "tags" {
  type        = map(string)
  description = "Tags applied to supported resources."
  default     = {}
}
