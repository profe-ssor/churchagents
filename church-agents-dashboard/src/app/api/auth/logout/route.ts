import { NextResponse } from "next/server"

import { SESSION_COOKIE, cookieOptions } from "@/lib/auth"

export async function POST() {
  const response = NextResponse.json({ ok: true })
  response.cookies.set(SESSION_COOKIE, "", cookieOptions(0))
  return response
}
