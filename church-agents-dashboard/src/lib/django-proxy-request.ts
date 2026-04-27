import { NextRequest, NextResponse } from "next/server"

import {
  SESSION_COOKIE,
  COOKIE_MAX_AGE,
  cookieOptions,
  parseSession,
  type SessionUser,
} from "@/lib/auth"

const DJANGO_URL = (process.env.NEXT_PUBLIC_DJANGO_URL || "http://localhost:8000").replace(
  /\/$/,
  ""
)

async function refreshSession(session: SessionUser): Promise<SessionUser | null> {
  if (!session.refresh) return null
  try {
    const res = await fetch(`${DJANGO_URL}/api/token/refresh/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh: session.refresh }),
    })
    if (!res.ok) return null
    const data = (await res.json()) as Record<string, unknown>
    if (typeof data.access !== "string") return null
    return {
      ...session,
      access: data.access,
      refresh: typeof data.refresh === "string" ? data.refresh : session.refresh,
    }
  } catch {
    return null
  }
}

/** Authenticated proxy to Django `/api/<path>/` — same logic as `/api/django/[...path]`. */
export async function proxyRequest(
  req: NextRequest,
  pathSegments: string[],
  retried: boolean
): Promise<NextResponse> {
  const sessionCookie = req.cookies.get(SESSION_COOKIE)
  const session = parseSession(sessionCookie?.value)

  if (!session) {
    return NextResponse.json({ detail: "Not authenticated — please log in." }, { status: 401 })
  }

  const path = pathSegments.join("/")
  const normalizedPath = path.endsWith("/") ? path : `${path}/`
  const search = req.nextUrl.search
  const url = `${DJANGO_URL}/api/${normalizedPath}${search}`

  const method = req.method
  let body: string | undefined
  const headers: HeadersInit = { Authorization: `Bearer ${session.access}` }

  if (method !== "GET" && method !== "HEAD") {
    body = await req.text()
    const ct = req.headers.get("content-type")
    if (ct) headers["Content-Type"] = ct
    else if (body) headers["Content-Type"] = "application/json"
  }

  let res = await fetch(url, { method, headers, body })
  let updatedSession: SessionUser | null = null

  if (res.status === 401 && !retried) {
    const refreshed = await refreshSession(session)
    if (!refreshed) {
      return NextResponse.json(
        { detail: "Session expired — please log in again." },
        { status: 401 }
      )
    }
    updatedSession = refreshed
    const retryHeaders: HeadersInit = { Authorization: `Bearer ${refreshed.access}` }
    if (method !== "GET" && method !== "HEAD") {
      const ct = req.headers.get("content-type")
      if (ct) retryHeaders["Content-Type"] = ct
      else if (body) retryHeaders["Content-Type"] = "application/json"
    }
    res = await fetch(url, { method, headers: retryHeaders, body })
  }

  const contentType = res.headers.get("content-type") || ""
  let response: NextResponse

  if (contentType.includes("application/json")) {
    const data = await res.json().catch(() => ({}))
    response = NextResponse.json(data, { status: res.status })
  } else {
    const text = await res.text()
    response = new NextResponse(text, {
      status: res.status,
      headers: { "Content-Type": contentType || "text/plain" },
    })
  }

  if (updatedSession) {
    response.cookies.set(SESSION_COOKIE, JSON.stringify(updatedSession), cookieOptions(COOKIE_MAX_AGE))
  }

  return response
}
