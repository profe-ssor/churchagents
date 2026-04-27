# churchagents

Church automation agents (orchestrator, MCP server, Celery scheduler) and the **church-agents-dashboard** Next.js app.

## Local setup (overview)

- Copy `.env.example` to `.env` and fill secrets locally (never committed).
- Python: create a venv, `pip install -r requirements.txt`.
- Dashboard: see `church-agents-dashboard/README.md` or `.env.local.example`.

## Orchestrator HTTP bridge

Run from repo root:

```bash
python orchestrator_server.py
```

Point your Django API at this service with `CHURCHAGENTS_ORCHESTRATOR_URL` (see Django backend docs).
