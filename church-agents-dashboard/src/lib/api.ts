import type { AgentSchedule, Church } from "@/lib/types"

async function djangoFetch(path: string, init?: RequestInit): Promise<Response> {
  const url = path.startsWith("http") ? path : `/api/django/${path.replace(/^\//, "")}`
  return fetch(url, init)
}

async function parseJson<T>(res: Response): Promise<T> {
  const text = await res.text()
  if (!text) return {} as T
  try {
    return JSON.parse(text) as T
  } catch {
    return {} as T
  }
}

/** Paginated DRF response */
interface Paginated<T> {
  results?: T[]
  count?: number
}

async function getPaginated<T>(path: string): Promise<Paginated<T>> {
  const res = await djangoFetch(path)
  const data = await parseJson<Paginated<T> | T[]>(res)
  if (Array.isArray(data)) return { results: data }
  return data
}

export const api = {
  getDashboardStats: async () => {
    const data = await getPaginated<Church>("auth/churches/?page_size=500")
    const churches = data.results ?? []
    const now = Date.now()
    const weekMs = 7 * 86400000
    return {
      total_churches: churches.length,
      active_subscriptions: churches.filter(
        (c) => c.subscription_status === "ACTIVE" || c.status === "ACTIVE"
      ).length,
      expiring_this_week: churches.filter((c) => {
        if (!c.subscription_ends_at) return false
        const t = new Date(c.subscription_ends_at).getTime()
        return t - now <= weekMs && t >= now
      }).length,
      suspended: churches.filter((c) => c.platform_access_enabled === false).length,
    }
  },

  getAgentLogs: (params?: Record<string, string>) => {
    const q = params ? `?${new URLSearchParams(params)}` : ""
    return djangoFetch(`agents/logs/${q}`).then((r) => parseJson<Paginated<unknown>>(r))
  },

  getAgentAlerts: (params?: Record<string, string>) => {
    const q = params ? `?${new URLSearchParams(params)}` : ""
    return djangoFetch(`agents/alerts/${q}`).then((r) => parseJson<Paginated<unknown>>(r))
  },

  getAgentSchedules: async (): Promise<{ results: AgentSchedule[] }> => {
    const res = await djangoFetch("agents/schedules/")
    if (!res.ok) return { results: FALLBACK_SCHEDULES }
    const data = await parseJson<{ results?: AgentSchedule[] }>(res)
    return { results: data.results ?? FALLBACK_SCHEDULES }
  },

  updateAgentSchedule: (_id: number | string, _data: Partial<AgentSchedule>) =>
    Promise.resolve({ status: "not_implemented" }),

  runAgentNow: (_agentName: string) =>
    Promise.resolve({ message: "Run agents via `python main.py <agent>` or Celery." }),

  askAgent: (
    question: string,
    session_id: string,
    opts?: { church_id?: string | null }
  ) => {
    const payload: Record<string, string> = { question, session_id }
    if (opts?.church_id !== undefined && opts.church_id !== null && opts.church_id !== "") {
      payload.church_id = opts.church_id
    }
    // Django POST /api/agents/ask/ (JWT via proxy): DB fallbacks + optional CHURCHAGENTS_ORCHESTRATOR_URL.
    // Do not call AGENTS_API_URL from the browser — Azure orchestrator often returns 500/HTML on failure.
    return djangoFetch("agents/ask/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }).then((r) => parseJson<{ answer?: string; response?: string }>(r))
  },

  getChurches: (params?: Record<string, string>) => {
    const q = params ? `?${new URLSearchParams(params)}` : ""
    // Django ChurchView returns a bare array [], not {"results": [...]}
    return getPaginated<Church>(`auth/churches/${q}`)
  },

  disableChurch: (id: string) =>
    djangoFetch(`auth/churches/${id}/platform-access/`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ platform_access_enabled: false }),
    }).then((r) => parseJson(r)),

  reinstateChurch: (id: string) =>
    djangoFetch(`auth/churches/${id}/platform-access/`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ platform_access_enabled: true }),
    }).then((r) => parseJson(r)),

  /** Same email template as SubscriptionWatchdogAgent / MCP `send_renewal_reminder_email`. */
  sendRenewalReminder: (churchId: string, daysLeft: number = 7) =>
    fetch("/api/agents/send-renewal-reminder", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ church_id: churchId, days_left: daysLeft }),
    }).then(async (r) => {
      const data = await parseJson<Record<string, unknown>>(r)
      if (!r.ok) {
        const detail =
          typeof data.detail === "object" && data.detail !== null
            ? JSON.stringify(data.detail)
            : typeof data.error === "string"
              ? data.error
              : `Request failed (${r.status})`
        throw new Error(detail)
      }
      return data
    }),

  getTreasuryStats: (params?: Record<string, string>) => {
    const q = params ? `?${new URLSearchParams(params)}` : ""
    return djangoFetch(`treasury/statistics/${q}`).then((r) => parseJson(r))
  },

  getStalledExpenses: () =>
    djangoFetch("treasury/expense-requests/?page_size=100").then((r) => parseJson(r)),

  getMembers: (params?: Record<string, string>) => {
    const q = params ? `?${new URLSearchParams(params)}` : ""
    return djangoFetch(`members/members/${q}`).then((r) => parseJson(r))
  },

  getDepartments: (params?: Record<string, string>) => {
    const q = params ? `?${new URLSearchParams(params)}` : ""
    return getPaginated<Record<string, unknown>>(`departments/${q}`)
  },

  getPrograms: (params?: Record<string, string>) => {
    const q = params ? `?${new URLSearchParams(params)}` : ""
    return getPaginated<Record<string, unknown>>(`programs/${q}`)
  },

  getDepartmentActivities: (departmentId: string, params?: Record<string, string>) => {
    const q = params ? `?${new URLSearchParams(params)}` : ""
    return getPaginated<Record<string, unknown>>(`departments/${departmentId}/activities/${q}`)
  },

  /** Paginated list; optional filters match Django (status, priority, search, page_size, …). */
  getAnnouncements: (params?: Record<string, string>) => {
    const q = params && Object.keys(params).length ? `?${new URLSearchParams(params)}` : ""
    return djangoFetch(`announcements/${q}`).then((r) => parseJson(r))
  },

  getAnnouncementPending: (params?: Record<string, string>) => {
    const q = params ? `?${new URLSearchParams(params)}` : ""
    return djangoFetch(`announcements/pending/${q}`).then((r) => parseJson(r))
  },

  getAnnouncementPublished: (params?: Record<string, string>) => {
    const q = params ? `?${new URLSearchParams(params)}` : ""
    return djangoFetch(`announcements/published/${q}`).then((r) => parseJson(r))
  },

  getAnnouncementStatsSummary: () =>
    djangoFetch(`announcements/stats/summary/`).then((r) => parseJson(r)),

  getAnnouncementStatsTimeline: (range: string = "month") =>
    djangoFetch(`announcements/stats/timeline/?range=${encodeURIComponent(range)}`).then((r) =>
      parseJson(r)
    ),

  getAnnouncementCategories: (params?: Record<string, string>) => {
    const q = params ? `?${new URLSearchParams(params)}` : ""
    return djangoFetch(`announcements/categories/${q}`).then((r) => parseJson(r))
  },

  getAuditLogs: (params?: Record<string, string>) => {
    const q = params ? `?${new URLSearchParams(params)}` : ""
    return djangoFetch(`activity/${q}`).then((r) => parseJson(r))
  },

  /** GET /api/auth/users/?locked_only=true — returns a JSON array from Django UserView. */
  getLockedUsers: (params?: Record<string, string>) => {
    const q = params ? `?${new URLSearchParams(params)}` : ""
    return djangoFetch(`auth/users/${q}`).then((r) => parseJson<unknown[]>(r))
  },

  /** When `church_saas` mounts `secretariat/` routes and ViewSets. Throws if Django returns !ok (404 until wired). */
  getSecretariatDocumentRequests: async (params?: Record<string, string>) => {
    const q = params ? `?${new URLSearchParams(params)}` : ""
    const res = await djangoFetch(`secretariat/document-requests/${q}`)
    const data = await parseJson<Record<string, unknown>>(res)
    if (!res.ok) {
      const msg =
        typeof data.detail === "string" ? data.detail : `Request failed (${res.status})`
      throw new Error(msg)
    }
    return data
  },

  getSecretariatMeetingMinutes: async (params?: Record<string, string>) => {
    const q = params ? `?${new URLSearchParams(params)}` : ""
    const res = await djangoFetch(`secretariat/meeting-minutes/${q}`)
    const data = await parseJson<Record<string, unknown>>(res)
    if (!res.ok) {
      const msg =
        typeof data.detail === "string" ? data.detail : `Request failed (${res.status})`
      throw new Error(msg)
    }
    return data
  },
}

/** Matches churchagents `scheduler/celery_app.py` when GET /api/agents/schedules/ is unavailable */
const FALLBACK_SCHEDULES: AgentSchedule[] = [
  {
    id: "orch",
    agent_name: "OrchestratorAgent",
    is_enabled: true,
    cron_expr: "0 7 * * *",
    last_run: null,
    next_run: null,
    last_status: "Configure Celery beat",
  },
  {
    id: "sub",
    agent_name: "SubscriptionWatchdogAgent",
    is_enabled: true,
    cron_expr: "0 */6 * * *",
    last_run: null,
    next_run: null,
    last_status: "",
  },
  {
    id: "tre",
    agent_name: "TreasuryHealthAgent",
    is_enabled: true,
    cron_expr: "0 */12 * * *",
    last_run: null,
    next_run: null,
    last_status: "",
  },
  {
    id: "mem",
    agent_name: "MemberCareAgent",
    is_enabled: true,
    cron_expr: "0 8 * * *",
    last_run: null,
    next_run: null,
    last_status: "",
  },
  {
    id: "dep",
    agent_name: "DepartmentProgramAgent",
    is_enabled: true,
    cron_expr: "0 */12 * * *",
    last_run: null,
    next_run: null,
    last_status: "",
  },
  {
    id: "ann",
    agent_name: "AnnouncementAgent",
    is_enabled: true,
    cron_expr: "0 9 * * *",
    last_run: null,
    next_run: null,
    last_status: "",
  },
  {
    id: "aud",
    agent_name: "AuditSecurityAgent",
    is_enabled: true,
    cron_expr: "0 1 * * *",
    last_run: null,
    next_run: null,
    last_status: "",
  },
  {
    id: "sec",
    agent_name: "SecretariatAgent",
    is_enabled: true,
    cron_expr: "0 7 * * *",
    last_run: null,
    next_run: null,
    last_status: "",
  },
]
