# Deploy ChurchAgents to Azure (Django on Render)

This guide assumes **church-management-saas-backend (Django)** is already live on **Render**. You will host **churchagents** (Python workers, orchestrator API, optional Next.js dashboard) on **Microsoft Azure**.

---

## 1. What you are deploying

| Piece | Role | Typical Azure target |
|--------|------|----------------------|
| **Django API** | Members, treasury, accounts, agents CRUD — already on **Render** | No change |
| **Redis** | Celery broker/backend + agent session memory | **Azure Cache for Redis** |
| **Celery worker + Beat** | Scheduled agents (`scheduler/celery_app.py`) | **Container Apps** or **App Service** (Linux container) |
| **Orchestrator HTTP** | `orchestrator_server.py` — Ask CTO / tools bridge for the dashboard | **Container Apps** (second container) |
| **church-agents-dashboard** | Next.js UI | **Azure Container Apps**, **App Service**, or **Azure Static Web Apps** + Node adapter |

Your repo already includes:

- `docker/Dockerfile` — builds the **Python** image and runs **Celery worker + beat** (same process).  
- `docker/docker-compose.yml` — local pattern with **Redis**, optional split **beat** vs **worker**.

There is **no** Dockerfile in-repo today for **orchestrator_server** or **Next.js**. Section [12](#12-appendix-dockerfiles-you-can-add) gives copy-paste Dockerfiles.

---

## 2. High-level architecture

```
                    ┌─────────────────────────────────────────┐
                    │  Render (existing)                     │
                    │  Django + REST + AgentAlert/Log APIs   │
                    └─────────────────┬───────────────────────┘
                                      │ HTTPS
                                      │  DJANGO_BASE_URL / NEXT_PUBLIC_DJANGO_URL
                                      ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Azure                                                               │
│  ┌──────────────┐    ┌─────────────────┐    ┌──────────────────────┐  │
│  │ Redis Cache  │◄──►│ Celery worker   │    │ Orchestrator :8001   │  │
│  │ (broker)     │    │ + Beat          │    │ (FastAPI)            │  │
│  └──────────────┘    └─────────────────┘    └──────────┬───────────┘  │
│                                                          │             │
│  ┌──────────────────────────────────────────────────────▼──────────┐ │
│  │ Next.js dashboard (browser → NEXT_PUBLIC_DJANGO_URL, AGENTS_API_URL)│ │
│  └───────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
```

**Important:** All components must reach **Render’s public HTTPS URL** for Django (`DJANGO_BASE_URL`). The **orchestrator** and **Celery tasks** use **AGENT_JWT_EMAIL** / **AGENT_JWT_PASSWORD** (or service token pattern) — same as local `.env`.

---

## 3. Prerequisites

1. **Azure subscription** and permission to create resources (Resource group, Container Apps or App Service, Azure Container Registry, Redis).
2. **Docker** installed locally (to build/push images), or use **Azure Container Registry tasks** / **GitHub Actions**.
3. **Render Django URL** (e.g. `https://your-api.onrender.com`) — no trailing slash issues; match what you put in env vars.
4. From `.env.example` in **churchagents**, prepare production values: `DJANGO_BASE_URL`, `OPENAI_API_KEY`, `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`, `AGENT_MEMORY_REDIS_URL`, JWT credentials, etc.

---

## 4. Azure Cache for Redis

1. Portal → **Create a resource** → **Azure Cache for Redis**.
2. Choose tier (Basic for tests; Standard for HA).
3. After creation, note:
   - **Host name** (e.g. `your-redis.redis.cache.windows.net`)
   - **Port** (6380 for SSL)
   - **Access key** (primary)

Build Redis URLs (SSL):

```text
rediss://:<PRIMARY_ACCESS_KEY>@your-redis.redis.cache.windows.net:6380/0
```

Use **different DB indexes** for broker, results, and memory (same as local):

| Variable | Index (example) |
|----------|------------------|
| `CELERY_BROKER_URL` | `/0` |
| `CELERY_RESULT_BACKEND` | `/1` |
| `AGENT_MEMORY_REDIS_URL` | `/2` |

**Firewall:** Allow access from your Azure Container Apps subnet / App Service outbound IPs, or use **Private Endpoint** for production.

---

## 5. Deploy with Terraform (recommended)

Infrastructure-as-code lives in **`terraform/`** at the repo root.

1. Install [Terraform](https://developer.hashicorp.com/terraform/install) and [Azure CLI](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli); run `az login`.
2. Copy `terraform/terraform.tfvars.example` → `terraform/terraform.tfvars` and set `django_base_url`, `openai_api_key`, `agent_jwt_email`, `agent_jwt_password`. Use a unique `prefix` if names collide globally (ACR/Redis names must be unique).
3. From **`terraform/`**:

   ```bash
   terraform init
   terraform plan
   terraform apply
   ```

4. **Push container images** to the ACR created by Terraform (see `terraform/README.md`). Images must exist before revisions stay healthy:

   - `churchagents-celery` — `docker build -f docker/Dockerfile …`
   - `churchagents-orchestrator` — `docker build -f docker/Dockerfile.orchestrator …`
   - `churchagents-dashboard` — build from `church-agents-dashboard/` (see [§12](#12-appendix-dockerfiles-you-can-add))

5. Read outputs: `terraform output orchestrator_https_url`, `terraform output dashboard_https_url`.

Full variable list and troubleshooting: **`terraform/README.md`**.

---

## 5b. Azure Container Registry (ACR) — manual path

1. Create **Container registry** (e.g. `churchagentsacr`).
2. Enable admin user or use **managed identity** for pulls (recommended with Container Apps).

Login and push (from your machine):

```bash
az acr login --name churchagentsacr

# Build from repo root (churchagents)
docker build -f docker/Dockerfile -t churchagentsacr.azurecr.io/churchagents-celery:latest .

docker push churchagentsacr.azurecr.io/churchagents-celery:latest
```

Repeat for **orchestrator** and **dashboard** images once you add Dockerfiles (see [§12](#12-appendix-dockerfiles-you-can-add)).

---

## 6. Azure Container Apps (recommended)

Container Apps runs multiple containers, autoscaling, and ingress. Alternative: **App Service for Linux** + **Web App for Containers** (simpler UI, single container per app).

### 6.1 Environment

1. Create **Container Apps** → **Environment** (with **Log Analytics** workspace).
2. Integrate with your **subnet** / **Redis** firewall rules as needed.

### 6.2 Celery service

- **Image:** `churchagentsacr.azurecr.io/churchagents-celery:latest`
- **Ingress:** **None** (workers do not need public HTTP).
- **Environment variables:** paste from `.env` (see [§7](#7-environment-variables-checklist)), at minimum:

  - `DJANGO_BASE_URL=https://your-render-app.onrender.com`
  - `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`, `AGENT_MEMORY_REDIS_URL` (rediss URLs)
  - `AGENT_JWT_EMAIL`, `AGENT_JWT_PASSWORD`
  - `OPENAI_API_KEY`, model vars
  - `CHROMA_PERSIST_DIR=/app/data/chroma` — mount **Azure Files** or **emptyDir** + backup strategy for Chroma persistence

- **Scaling:** min replicas ≥ 1 for worker; beat is inside same image CMD — for production you may prefer **splitting** worker and beat into two revisions with different **commands** (see docker-compose pattern).

### 6.3 Orchestrator service

- Separate **Container App**, **HTTP** ingress, target port **8001** (or set `AGENTS_HTTP_PORT`).
- **Command/args** override image default to run:

  ```bash
  uvicorn orchestrator_server:app --host 0.0.0.0 --port 8001
  ```

  (Adjust if your `orchestrator_server` exposes ASGI differently — check file for app object name.)

- Set the **same** env as Celery for Django + OpenAI + Redis memory.

- Assign a stable **HTTPS URL** from Container Apps ingress — this becomes:

  - `AGENTS_API_URL` in the **dashboard**
  - Optional: `ORCHESTRATOR_INTERNAL_BASE_URL` for internal callbacks

### 6.4 Next.js dashboard

- Build image with Dockerfile in [§12.2](#122-nextjs-dashboard-dockerfile).
- Container App with **ingress: external**, port **3000**.
- **Build-time / runtime env** for Next:

  - `NEXT_PUBLIC_DJANGO_URL=https://your-render-app.onrender.com`
  - `DJANGO_AGENT_EMAIL`, `DJANGO_AGENT_PASSWORD` (server-side proxy to Django)
  - `AGENTS_API_URL=https://your-orchestrator.azurecontainerapps.io` (your orchestrator public URL)

Use **Azure Key Vault references** or **Container Apps secrets** for passwords and API keys — do not commit production secrets.

---

## 7. Environment variables checklist

### churchagents (Celery + orchestrator)

| Variable | Notes |
|---------|--------|
| `DJANGO_BASE_URL` | Render HTTPS base URL |
| `AGENT_JWT_EMAIL` / `AGENT_JWT_PASSWORD` | Service user in Django |
| `CELERY_BROKER_URL` / `CELERY_RESULT_BACKEND` | Azure Redis `rediss://…` |
| `AGENT_MEMORY_REDIS_URL` | Same Redis, different DB index |
| `OPENAI_API_KEY` | Required for orchestrator / agents |
| `CHROMA_PERSIST_DIR` | Persistent volume path if you keep Chroma on disk |
| `AGENTS_HTTP_PORT` | Default `8001` inside orchestrator container |

### Next.js (`church-agents-dashboard`)

Copy from `.env.local.example` and point to production URLs:

| Variable | Notes |
|---------|--------|
| `NEXT_PUBLIC_DJANGO_URL` | Render URL (browser-visible) |
| `AGENTS_API_URL` | Public HTTPS URL of orchestrator on Azure |
| `DJANGO_AGENT_EMAIL` / `DJANGO_AGENT_PASSWORD` | Same as server-side Django login for the proxy |

---

## 8. Render (Django) checklist

Ensure the Render app allows:

1. **CORS** — if the dashboard origin is new (e.g. `https://churchagents-dashboard.azurecontainerapps.io`), add it to Django `CORS_ALLOWED_ORIGINS` (or your project’s equivalent).
2. **CSRF / trusted origins** — for session/cookie flows if applicable.
3. **Rate limits** — Azure outbound IPs may change unless you use static egress; for webhooks prefer **fixed IP** add-on on Azure or Render if you whitelist IPs.

---

## 9. TLS and custom domains

- **Container Apps:** add custom domain + managed certificate on the **orchestrator** and **dashboard** ingress.
- Point **DNS** CNAME to the default `*.azurecontainerapps.io` hostname.
- Use **HTTPS only** for `NEXT_PUBLIC_DJANGO_URL` and `AGENTS_API_URL`.

---

## 10. Observability

- Enable **Azure Monitor** / **Log Analytics** for Container Apps (stdout/stderr).
- **LangSmith** — keep `LANGCHAIN_*` variables if you use tracing.
- **Application Insights** (optional) for Node/Python.

---

## 11. Troubleshooting

| Symptom | Check |
|---------|--------|
| Celery tasks not running | Redis URL, firewall, worker replicas, Beat schedule timezone in `celery_app.py` |
| `403` / `401` from Django | JWT user, `DJANGO_BASE_URL`, church scoping (`AGENT_JWT_CHURCH_ID`) |
| Ask CTO fails in UI | `AGENTS_API_URL` reachable from browser (CORS not on orchestrator for simple HTTP — usually dashboard calls **server-side** Next API routes → orchestrator) |
| Chroma / RAG empty | Volume mount path, cold start without persistent disk |

---

## 12. Appendix: Dockerfiles (in this repo)

The repository’s `docker/Dockerfile` targets **Celery**. Orchestrator and dashboard Dockerfiles are checked in under the paths below.

### 12.1 Orchestrator Dockerfile

`docker/Dockerfile.orchestrator` (build context: **repo root** `churchagents/`):

```dockerfile
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV AGENTS_HTTP_HOST=0.0.0.0
ENV AGENTS_HTTP_PORT=8001

RUN pip install --no-cache-dir uvicorn

CMD ["uvicorn", "orchestrator_server:app", "--host", "0.0.0.0", "--port", "8001"]
```

**Verify** in `orchestrator_server.py` that the FastAPI app is named `app`. If not, adjust the module path.

Build:

```bash
docker build -f docker/Dockerfile.orchestrator -t <acr>/churchagents-orchestrator:latest .
```

### 12.2 Next.js dashboard Dockerfile

`church-agents-dashboard/Dockerfile` uses **standalone** output.

1. In `church-agents-dashboard/next.config.ts` (or `.mjs`), ensure:

   ```ts
   const nextConfig = {
     output: "standalone",
   }
   ```

2. Dockerfile (multi-stage):

```dockerfile
FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci

FROM node:22-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM node:22-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs

COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs
EXPOSE 3000
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"
CMD ["node", "server.js"]
```

Build from `church-agents-dashboard/`:

```bash
cd church-agents-dashboard
docker build -t <acr>/churchagents-dashboard:latest .
```

Pass env at runtime in Azure (not all need to be in image).

---

## 13. CI/CD (optional)

- **GitHub Actions:** on push to `main`, build three images, `az acr push`, then `az containerapp update` with new tags.
- Store `AZURE_CREDENTIALS`, `REGISTRY_LOGIN` as secrets.

---

## 14. Cost and ops tips

- Start with **single-region** Container Apps + **Basic Redis** for staging.
- **Split Celery worker and beat** into two deployments when you need independent scaling or zero-downtime deploys.
- Back up **Chroma** directory if RAG is critical; consider **Azure Files** mount.

---

*Last aligned with churchagents layout: `docker/Dockerfile`, `scheduler/celery_app.py`, `orchestrator_server.py`, `church-agents-dashboard` Next.js 16.*
