export interface SessionUser {
  access: string
  refresh: string
  email: string
  first_name: string
  last_name: string
  full_name: string
  is_platform_admin: boolean
  church_id: string | null
  church_name: string | null
}

export const SESSION_COOKIE = "church_session"
export const COOKIE_MAX_AGE = 60 * 60 * 24 * 7 // 7 days

export function parseSession(value: string | undefined): SessionUser | null {
  if (!value) return null
  try {
    const parsed = JSON.parse(value) as Partial<SessionUser>
    if (typeof parsed.access !== "string" || !parsed.access) return null
    if (typeof parsed.email !== "string" || !parsed.email.trim()) return null
    const email = parsed.email.trim()
    return {
      access: parsed.access,
      refresh: typeof parsed.refresh === "string" ? parsed.refresh : "",
      email,
      first_name: typeof parsed.first_name === "string" ? parsed.first_name : "",
      last_name: typeof parsed.last_name === "string" ? parsed.last_name : "",
      full_name: typeof parsed.full_name === "string" && parsed.full_name ? parsed.full_name : email,
      is_platform_admin: parsed.is_platform_admin === true,
      church_id: typeof parsed.church_id === "string" ? parsed.church_id : null,
      church_name: typeof parsed.church_name === "string" ? parsed.church_name : null,
    }
  } catch {
    return null
  }
}

export function cookieOptions(maxAge = COOKIE_MAX_AGE) {
  return {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax" as const,
    path: "/",
    maxAge,
  }
}
