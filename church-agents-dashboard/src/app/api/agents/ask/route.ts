import { NextRequest } from "next/server"

import { proxyRequest } from "@/lib/django-proxy-request"

/**
 * Same backend as `api.askAgent` → Django `POST /api/agents/ask/` (JWT).
 * Keeps legacy `/api/agents/ask` callers aligned with the django proxy path so Ask
 * does not depend on a healthy Azure orchestrator for DB-backed answers.
 */
export async function POST(req: NextRequest) {
  return proxyRequest(req, ["agents", "ask"], false)
}
