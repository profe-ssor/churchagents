import { cookies } from "next/headers"
import { NextResponse } from "next/server"

import { SESSION_COOKIE, parseSession } from "@/lib/auth"

/** Public session flags for client UI (no tokens). */
export async function GET() {
  const store = await cookies()
  const session = parseSession(store.get(SESSION_COOKIE)?.value)

  if (!session) {
    return NextResponse.json({
      authenticated: false,
      is_platform_admin: false,
      church_id: null,
      church_name: null,
    })
  }

  return NextResponse.json({
    authenticated: true,
    is_platform_admin: session.is_platform_admin,
    church_id: session.church_id,
    church_name: session.church_name,
    email: session.email,
  })
}
