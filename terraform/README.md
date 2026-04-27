# Terraform — Azure (ChurchAgents)

Provisions:

- Resource group  
- **Azure Cache for Redis** (Celery broker, results, agent memory)  
- **Azure Container Registry** (admin enabled for simpler pulls; prefer managed identity later)  
- **Log Analytics** + **Container Apps Environment**  
- **Three Container Apps**: Celery worker+beat, Orchestrator (8001), Dashboard (3000)

Django stays on **Render**; set `django_base_url` to that HTTPS origin.

## Prerequisites

1. [Azure CLI](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli) (`az login`)
2. [Terraform](https://developer.hashicorp.com/terraform/install) `>= 1.5`
3. Subscription with rights to create the resources above
4. Docker images pushed to ACR **before** containers can start (see below)

## Quick start

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars — unique prefix if name clash, secrets, Render URL

terraform init
terraform plan
terraform apply
```

Sensitive values belong in `terraform.tfvars` (keep out of git).

## Push container images

Repository root (`churchagents/`):

```bash
ACR_NAME="<your registry name from apply output / Azure Portal>"
az acr login --name "$ACR_NAME"

# Celery (existing docker/Dockerfile)
docker build -f docker/Dockerfile -t $ACR_NAME.azurecr.io/churchagents-celery:latest .
docker push $ACR_NAME.azurecr.io/churchagents-celery:latest

# Orchestrator + dashboard (Dockerfiles live in-repo: docker/Dockerfile.orchestrator, church-agents-dashboard/Dockerfile)
docker build -f docker/Dockerfile.orchestrator -t $ACR_NAME.azurecr.io/churchagents-orchestrator:latest .
docker push $ACR_NAME.azurecr.io/churchagents-orchestrator:latest

cd church-agents-dashboard
docker build -t $ACR_NAME.azurecr.io/churchagents-dashboard:latest .
docker push $ACR_NAME.azurecr.io/churchagents-dashboard:latest
```

After pushing, restart revisions or run `terraform apply` again so new tags roll out.

## Outputs

- `orchestrator_https_url` — stable `ingress` hostname for `AGENTS_API_URL` (do not use `latest_revision_fqdn` in env; it breaks after each revision).  
- `dashboard_https_url` — browser entry point.  
- Add both URLs to Render Django **CORS / CSRF trusted origins** if the browser calls Django directly.

## Redis firewall

Default Redis allows Azure-internal access patterns; for strict networks, open the Container Apps environment to Redis or use Private Link (advanced).

## Destroy

```bash
terraform destroy
```

## Variables

See `variables.tf`. Main inputs: `django_base_url`, `openai_api_key`, `agent_jwt_email`, `agent_jwt_password`, `prefix`, `location`.
