import { NextRequest, NextResponse } from "next/server"

import { SESSION_COOKIE, parseSession } from "@/lib/auth"
import { fetchOrchestratorJson } from "@/lib/orchestrator-proxy"

const AGENTS_URL = process.env.AGENTS_API_URL || ""

function canRemindForChurch(args: {
  session: NonNullable<ReturnType<typeof parseSession>>
  targetChurchId: string
}): boolean {
  const { session, targetChurchId } = args
  if (session.is_platform_admin) return true
  if (!session.church_id) return false
  return session.church_id === targetChurchId
}

export async function POST(req: NextRequest) {
  let body: { church_id?: string; days_left?: number }
  try {
    body = await req.json()
  } catch {
    return NextResponse.json({ error: "Invalid JSON body." }, { status: 400 })
  }

  const churchId = typeof body.church_id === "string" ? body.church_id.trim() : ""
  if (!churchId) {
    return NextResponse.json({ error: "church_id is required." }, { status: 400 })
  }

  const daysRaw = body.days_left
  const daysLeft =
    typeof daysRaw === "number" && Number.isFinite(daysRaw)
      ? Math.min(365, Math.max(1, Math.floor(daysRaw)))
      : 7

  const sessionCookie = req.cookies.get(SESSION_COOKIE)
  const session = parseSession(sessionCookie?.value)
  if (!session) {
    return NextResponse.json({ error: "Not authenticated." }, { status: 401 })
  }

  if (!canRemindForChurch({ session, targetChurchId: churchId })) {
    return NextResponse.json({ error: "Forbidden for this church." }, { status: 403 })
  }

  if (!AGENTS_URL.trim()) {
    return NextResponse.json(
      {
        error:
          "Orchestrator not configured. Set AGENTS_API_URL in `.env.local` and run `python orchestrator_server.py` in churchagents.",
      },
      { status: 503 }
    )
  }

  const url = `${AGENTS_URL.replace(/\/$/, "")}/renewal-reminder`
  try {
    const parsed = await fetchOrchestratorJson(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ church_id: churchId, days_left: daysLeft }),
    })
    if (!parsed.ok) {
      return NextResponse.json(
        {
          error: `${parsed.parseError} (HTTP ${parsed.status}). Fix Container App health or AGENTS_API_URL; try GET /health on the orchestrator base URL.`,
        },
        { status: 502 }
      )
    }
    const data = parsed.data
    if (parsed.status >= 400) {
      return NextResponse.json(data, { status: parsed.status })
    }
    return NextResponse.json(data)
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err)
    return NextResponse.json(
      { error: `Cannot reach orchestrator (${msg}).` },
      { status: 502 }
    )
  }
}
