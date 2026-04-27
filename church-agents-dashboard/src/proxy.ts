import { NextRequest, NextResponse } from "next/server"

import { SESSION_COOKIE } from "@/lib/auth"

const PUBLIC = ["/login", "/api/auth/"]

export function proxy(req: NextRequest) {
  const { pathname } = req.nextUrl

  if (PUBLIC.some((p) => pathname.startsWith(p))) {
    return NextResponse.next()
  }

  const session = req.cookies.get(SESSION_COOKIE)
  if (!session?.value) {
    const loginUrl = new URL("/login", req.url)
    loginUrl.searchParams.set("next", pathname)
    return NextResponse.redirect(loginUrl)
  }

  return NextResponse.next()
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
}
