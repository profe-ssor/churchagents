import { NextRequest, NextResponse } from "next/server"

import { SESSION_COOKIE, COOKIE_MAX_AGE, cookieOptions, type SessionUser } from "@/lib/auth"

const DJANGO_URL = (process.env.NEXT_PUBLIC_DJANGO_URL || "http://localhost:8000").replace(/\/$/, "")

function normalizePassword(raw: string): string {
  let p = raw.trim()
  if ((p.startsWith('"') && p.endsWith('"')) || (p.startsWith("'") && p.endsWith("'"))) {
    p = p.slice(1, -1)
  }
  return p
}

export async function POST(req: NextRequest) {
  let body: { email?: string; password?: string }
  try {
    body = await req.json()
  } catch {
    return NextResponse.json({ detail: "Invalid request body" }, { status: 400 })
  }

  const email = (body.email || "").trim()
  const password = normalizePassword(body.password || "")

  if (!email || !password) {
    return NextResponse.json({ detail: "Email and password are required" }, { status: 400 })
  }

  let djangoRes: Response
  try {
    djangoRes = await fetch(`${DJANGO_URL}/api/auth/login/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    })
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e)
    return NextResponse.json({ detail: `Cannot reach Django at ${DJANGO_URL}: ${msg}` }, { status: 503 })
  }

  const data = (await djangoRes.json()) as Record<string, unknown>

  if (!djangoRes.ok) {
    const detail =
      (data.detail as string) ||
      (Array.isArray(data.non_field_errors) ? data.non_field_errors[0] : undefined) ||
      "Invalid credentials"
    return NextResponse.json({ detail }, { status: djangoRes.status })
  }

  const user = (data.user as Record<string, unknown>) || {}
  const tokens = (data.tokens as Record<string, unknown>) || {}
  const access = (tokens.access as string) || (data.access as string)
  const refresh = (tokens.refresh as string) || (data.refresh as string) || ""

  if (!access) {
    return NextResponse.json({ detail: "Login failed: no access token in response" }, { status: 500 })
  }

  const firstName = (user.first_name as string) || ""
  const lastName = (user.last_name as string) || ""

  const session: SessionUser = {
    access,
    refresh,
    email: (user.email as string) || email,
    first_name: firstName,
    last_name: lastName,
    full_name: (user.full_name as string) || `${firstName} ${lastName}`.trim() || email,
    is_platform_admin: user.is_platform_admin === true,
    church_id: (user.church as string) || null,
    church_name: (user.church_name as string) || null,
  }

  const response = NextResponse.json({
    ok: true,
    is_platform_admin: session.is_platform_admin,
    full_name: session.full_name,
  })

  response.cookies.set(SESSION_COOKIE, JSON.stringify(session), cookieOptions(COOKIE_MAX_AGE))

  return response
}
