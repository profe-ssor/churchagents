"use client"

import Link from "next/link"
import { useQuery } from "@tanstack/react-query"
import { formatDistanceToNow } from "date-fns"
import { ArrowRight, Megaphone } from "lucide-react"

import { AgentInfoPanel } from "@/components/agent-info-panel"
import { AgentTaskFlow } from "@/components/agent-task-flow"
import { PageHeader } from "@/components/page-header"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { useDashboardChurchScope } from "@/hooks/use-dashboard-church-scope"
import { api } from "@/lib/api"
import type { AgentAlert, AgentLog } from "@/lib/types"
import { cn } from "@/lib/utils"

const ACCENT = "#f4a261"
const AGENT_NAME = "AnnouncementAgent"

const ANNOUNCEMENT_AGENT_BULLETS = [
  "Calls GET /api/announcements/pending/ on each scheduled run and flags announcements in PENDING_REVIEW longer than ANNOUNCEMENT_STALL_HOURS (default 24) as stalled.",
  "Creates WARNING AgentAlert rows (STALLED_ANNOUNCEMENT) so secretariat sees items stuck in approval.",
  "Writes AgentLog entries (announcement_check) after each run — surfaced below for this church when available.",
  "Weekly digest / publish-blast behaviors in product docs are gated on Django notifications + MCP tools; extend MCP + Celery tasks to wire them.",
  "Orchestrator connects to MCP tools such as get_pending_announcements, get_published_announcements, get_announcement_stats — same backend as this page.",
  "Approve/publish/send/nudge flows require secretariat permissions in Django; dashboard is read-mostly observability.",
] as const

const ANNOUNCEMENT_TASK_STEPS = [
  {
    title: "Scheduled run",
    description:
      "Celery runs AnnouncementAgent daily at 09:00 (churchagents scheduler/celery_app.py — task run_announcement).",
  },
  {
    title: "Observe queue",
    description:
      "Pulls pending announcements via the Django API — same endpoint this page uses for “Awaiting approval”.",
  },
  {
    title: "Detect stalls",
    description:
      "Compares created/submitted timestamps to ANNOUNCEMENT_STALL_HOURS and raises alerts for stuck PENDING_REVIEW items.",
  },
  {
    title: "Record & notify",
    description:
      "Persists AgentAlert + AgentLog; optional digests and distribution hooks depend on your notifications stack.",
  },
] as const

/** Product / orchestrator capabilities — map to MCP function names where implemented. */
const TOOL_ROWS: { tool: string; purpose: string }[] = [
  { tool: "get_pending_announcements", purpose: "Announcements awaiting approval" },
  { tool: "get_published_announcements", purpose: "Published announcements list" },
  { tool: "approve_and_publish (API)", purpose: "POST approve / publish on announcement (authorized roles)" },
  { tool: "send_announcement_to_members", purpose: "Blast email/SMS to target group (via notifications)" },
  { tool: "notify_approver", purpose: "Nudge reviewer with reminder" },
  { tool: "generate_weekly_digest", purpose: "Weekly summary email (Celery + templates)" },
  { tool: "get_announcement_stats", purpose: "Reach / engagement summary (stats/summary/)" },
  { tool: "get_announcement_categories", purpose: "GET …/categories/" },
]

const TRIGGER_ROWS: { label: string; tag: string; detail: string }[] = [
  {
    tag: "SCHEDULED",
    label: "Daily health check",
    detail: "09:00 — stalled PENDING_REVIEW scan (deployed schedule in repo). Product spec also mentions 6h checks — tune Celery if needed.",
  },
  {
    tag: "SCHEDULED",
    label: "Weekly digest",
    detail: "Sunday digest to subscribed members — wire Celery beat + digest template when ready.",
  },
  {
    tag: "EVENT",
    label: "Publish → distribute",
    detail: "On publish, auto-notify targeted members/departments via email/SMS when distribution jobs are enabled.",
  },
  {
    tag: "REMIND",
    label: "Pending > 24h",
    detail: "Agent alert + optional approver nudge — stall threshold configurable via ANNOUNCEMENT_STALL_HOURS.",
  },
  {
    tag: "DIGEST",
    label: "Weekly announcement digest",
    detail: "Batch summary for subscribers — orchestrator/on-demand prompts supported when backend sends.",
  },
]

function rowsFromPaginated(data: unknown): Record<string, unknown>[] {
  if (Array.isArray(data)) return data as Record<string, unknown>[]
  if (data && typeof data === "object" && Array.isArray((data as { results?: unknown }).results)) {
    return ((data as { results: Record<string, unknown>[] }).results ?? []) as Record<string, unknown>[]
  }
  return []
}

function pickTitle(row: Record<string, unknown>): string {
  const t = row.title
  return typeof t === "string" && t.trim() ? t : "—"
}

function pickStatus(row: Record<string, unknown>): string {
  const s = row.status
  return typeof s === "string" ? s : "—"
}

function scopeFiltersAnnouncementRow(
  row: { agent_name: string; church_id?: string | null },
  churchId: string
): boolean {
  if (row.agent_name !== AGENT_NAME) return false
  if (!churchId) return false
  return row.church_id === churchId || row.church_id === null
}

function tagTone(tag: string): string {
  switch (tag) {
    case "SCHEDULED":
      return "border-sky-500/40 bg-sky-500/15 text-sky-300"
    case "EVENT":
      return "border-emerald-500/40 bg-emerald-500/15 text-emerald-300"
    case "REMIND":
      return "border-amber-500/40 bg-amber-500/15 text-amber-200"
    case "DIGEST":
      return "border-violet-500/40 bg-violet-500/15 text-violet-300"
    default:
      return "border-slate-600 bg-slate-800 text-slate-400"
  }
}

export default function AnnouncementsPage() {
  const {
    churches,
    scopeChurchId,
    setScopeChurchId,
    effectiveChurchId,
    waitingPlatformScope,
    needsChurch,
    showScopePicker,
    bootLoading,
    sessionReady,
    churchesReady,
    sessionInfo,
  } = useDashboardChurchScope("churchagents_announcements_church_scope")

  const scopeReady = Boolean(
    sessionReady && churchesReady && effectiveChurchId && sessionInfo?.authenticated
  )

  const { data: pendingData, isLoading: pendingLoading } = useQuery({
    queryKey: ["announcements", "pending", effectiveChurchId ?? "none"],
    queryFn: () => api.getAnnouncementPending({ page_size: "100" }),
    enabled: scopeReady,
    refetchInterval: 60_000,
  })

  const { data: publishedData, isLoading: publishedLoading } = useQuery({
    queryKey: ["announcements", "published", effectiveChurchId ?? "none"],
    queryFn: () => api.getAnnouncementPublished({ page_size: "100" }),
    enabled: scopeReady,
    refetchInterval: 60_000,
  })

  const { data: statsData, isLoading: statsLoading } = useQuery({
    queryKey: ["announcements", "stats", effectiveChurchId ?? "none"],
    queryFn: () => api.getAnnouncementStatsSummary(),
    enabled: scopeReady,
    refetchInterval: 120_000,
  })

  const { data: categoriesData, isLoading: categoriesLoading } = useQuery({
    queryKey: ["announcements", "categories", effectiveChurchId ?? "none"],
    queryFn: () => api.getAnnouncementCategories({ page_size: "200" }),
    enabled: scopeReady,
  })

  const { data: alertsData, isLoading: alertsLoading } = useQuery({
    queryKey: ["announcement-agent-alerts", effectiveChurchId ?? "none"],
    queryFn: () => api.getAgentAlerts({ page_size: "200" }),
    enabled: scopeReady,
    refetchInterval: 60_000,
  })

  const { data: logsData, isLoading: logsLoading } = useQuery({
    queryKey: ["announcement-agent-logs", effectiveChurchId ?? "none"],
    queryFn: () => api.getAgentLogs({ page_size: "80" }),
    enabled: scopeReady,
    refetchInterval: 60_000,
  })

  const pendingRows = rowsFromPaginated(pendingData)
  const publishedRows = rowsFromPaginated(publishedData)
  const categoryRows = rowsFromPaginated(categoriesData)

  const stats = statsData && typeof statsData === "object" ? (statsData as Record<string, unknown>) : null
  const totalAnnouncements =
    typeof stats?.total_announcements === "number" ? stats.total_announcements : null

  const alertList = (alertsData?.results ?? []) as AgentAlert[]
  const logList = (logsData?.results ?? []) as AgentLog[]

  const alertsForChurch = effectiveChurchId
    ? alertList.filter((a) => scopeFiltersAnnouncementRow(a, effectiveChurchId))
    : []

  const selectedChurchName = churches.find((c) => c.id === effectiveChurchId)?.name

  const logsForChurch = effectiveChurchId
    ? logList.filter((log) => {
        if (log.agent_name !== AGENT_NAME) return false
        const cid = log.church_id ?? null
        if (cid === effectiveChurchId) return true
        if (selectedChurchName && log.church_name === selectedChurchName) return true
        return false
      })
    : []

  const logsSorted = [...logsForChurch].sort(
    (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
  )
  const latestRun = logsSorted[0]
  const lastRunLabel = latestRun
    ? formatDistanceToNow(new Date(latestRun.created_at), { addSuffix: true })
    : undefined

  const recentAlerts = [...alertsForChurch]
    .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
    .slice(0, 12)

  const monitorLoading = alertsLoading || logsLoading
  const listsLoading = pendingLoading || publishedLoading || statsLoading || categoriesLoading

  const severityClass: Record<string, string> = {
    CRITICAL: "border-[#ff6b6b44] bg-[#ff6b6b22] text-[#ff6b6b]",
    WARNING: "border-[#ffd16644] bg-[#ffd16622] text-[#ffd166]",
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="📢 Announcements"
        description={`${AGENT_NAME} · Communications & Publishing Coordinator · Monitors PENDING_REVIEW stalls, publishes feeds below, and aligns with MCP/orchestrator tools for digests and distribution.`}
        icon={Megaphone}
        color={ACCENT}
        agentName={AGENT_NAME}
        lastRun={lastRunLabel}
      />

      <div className="flex flex-wrap items-center gap-2">
        <Badge variant="outline" className="border-[#f4a26155] text-[11px] text-[#f4a261]">
          AGENT 6
        </Badge>
        <Badge variant="outline" className="border-slate-600 text-[11px] text-slate-400">
          Church-scoped Django API — lists reflect your signing user&apos;s congregation
        </Badge>
      </div>

      <AgentTaskFlow accent={ACCENT} steps={ANNOUNCEMENT_TASK_STEPS} />

      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="border-slate-800 bg-[#1a1d27]">
          <CardContent className="p-5">
            <h2 className="text-sm font-semibold text-white">Tools</h2>
            <p className="mt-1 text-[11px] text-slate-500">
              MCP / orchestrator names — backend routes must exist for writes.
            </p>
            <div className="mt-3 overflow-x-auto rounded-lg border border-slate-800">
              <table className="w-full text-left text-[11px]">
                <thead>
                  <tr className="border-b border-slate-800 bg-[#151824] text-slate-500">
                    <th className="px-2 py-2 font-medium">Function</th>
                    <th className="px-2 py-2 font-medium">Role</th>
                  </tr>
                </thead>
                <tbody>
                  {TOOL_ROWS.map((row) => (
                    <tr key={row.tool} className="border-b border-slate-800/60 last:border-0">
                      <td className="px-2 py-2 font-mono text-[10px] text-[#f4a261]/95">{row.tool}</td>
                      <td className="px-2 py-2 text-slate-400">{row.purpose}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>

        <Card className="border-slate-800 bg-[#1a1d27]">
          <CardContent className="p-5">
            <h2 className="text-sm font-semibold text-white">Triggers</h2>
            <p className="mt-1 text-[11px] text-slate-500">
              Mix of deployed schedules and target product behaviors — align Celery with your ops cadence.
            </p>
            <ul className="mt-3 space-y-3">
              {TRIGGER_ROWS.map((t) => (
                <li key={t.label} className="rounded-lg border border-slate-800 bg-[#151824] px-3 py-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge variant="outline" className={cn("text-[10px]", tagTone(t.tag))}>
                      {t.tag}
                    </Badge>
                    <span className="text-xs font-medium text-white">{t.label}</span>
                  </div>
                  <p className="mt-1 text-[11px] leading-snug text-slate-400">{t.detail}</p>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      </div>

      <AgentInfoPanel
        agentName={AGENT_NAME}
        schedule="Deployed: daily at 09:00 (churchagents scheduler/celery_app.py — announcement beat). Extend with digest jobs as needed."
        bullets={ANNOUNCEMENT_AGENT_BULLETS}
        accent={ACCENT}
        defaultOpen
        footerNote="Empty queues are normal until secretariat creates announcements in Django. Results always match GET /api/announcements/* for your authenticated user’s church."
      />

      {showScopePicker && (
        <div className="flex max-w-xl flex-col gap-1.5 rounded-lg border border-slate-800 bg-[#1a1d27] p-4">
          <label htmlFor="announcements-church-scope" className="text-xs font-medium text-slate-400">
            Platform admin: pick a church label for scoped widgets (API still follows your Django user church).
          </label>
          <select
            id="announcements-church-scope"
            value={scopeChurchId}
            onChange={(e) => setScopeChurchId(e.target.value)}
            className="rounded-lg border border-slate-700 bg-[#21253a] px-3 py-2 text-sm text-white outline-none focus:border-[#f4a261]"
          >
            <option value="">Select a church…</option>
            {churches.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </div>
      )}

      <Card className="border-slate-800 bg-[#1a1d27]">
        <CardContent className="space-y-4 p-6">
          <div>
            <h2 className="text-base font-semibold text-white">{AGENT_NAME} activity</h2>
            <p className="mt-1 text-xs text-slate-500">
              Alerts and logs emitted by the scheduled announcement job for this church context — same pipeline as{" "}
              <code className="text-slate-400">agents/announcement.py</code>.
            </p>
          </div>

          {bootLoading && <Skeleton className="h-24 bg-slate-800" />}
          {!bootLoading && waitingPlatformScope && (
            <p className="text-sm text-slate-400">Choose a church to load agent monitor data.</p>
          )}
          {!bootLoading && !waitingPlatformScope && needsChurch && (
            <p className="text-sm text-amber-200/90">
              No church on this account. Associate a congregation or ensure `/api/auth/churches/` returns data.
            </p>
          )}
          {!bootLoading && !waitingPlatformScope && scopeReady && monitorLoading && (
            <Skeleton className="h-32 bg-slate-800" />
          )}
          {!bootLoading && !waitingPlatformScope && scopeReady && !monitorLoading && (
            <>
              <div className="flex flex-wrap items-center gap-3 rounded-lg border border-slate-800 bg-[#151824] px-4 py-3 text-sm">
                <span className="text-slate-400">Latest scheduled check</span>
                {latestRun ? (
                  <>
                    <Badge variant="outline" className="border-slate-600 font-mono text-xs text-slate-300">
                      {latestRun.action}
                    </Badge>
                    <span
                      className={cn(
                        "rounded-full px-2 py-0.5 text-xs font-semibold",
                        latestRun.status === "SUCCESS"
                          ? "bg-[#f4a26122] text-[#f4a261]"
                          : latestRun.status === "FAILED"
                            ? "bg-[#ff6b6b22] text-[#ff6b6b]"
                            : "bg-slate-700 text-slate-300"
                      )}
                    >
                      {latestRun.status}
                    </span>
                    <span className="text-xs text-slate-500">
                      {formatDistanceToNow(new Date(latestRun.created_at), { addSuffix: true })} ·{" "}
                      {latestRun.duration_ms}ms
                    </span>
                  </>
                ) : (
                  <span className="text-slate-500">No {AGENT_NAME} runs logged for this church yet.</span>
                )}
                <Link
                  href="/logs"
                  className="ml-auto inline-flex items-center gap-1 text-xs font-medium text-[#f4a261] hover:underline"
                >
                  All agent logs <ArrowRight className="size-3" />
                </Link>
              </div>

              <div className="overflow-x-auto rounded-lg border border-slate-800">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-slate-800 bg-[#151824]">
                      <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                        When
                      </th>
                      <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                        Type
                      </th>
                      <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                        Severity
                      </th>
                      <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                        Message
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {recentAlerts.length === 0 ? (
                      <tr>
                        <td colSpan={4} className="px-3 py-6 text-center text-xs text-slate-500">
                          No stalled-announcement alerts yet. When items sit in PENDING_REVIEW past the stall threshold,
                          they appear here.
                        </td>
                      </tr>
                    ) : (
                      recentAlerts.map((a) => (
                        <tr key={a.id} className="border-b border-slate-800/60 last:border-0">
                          <td className="whitespace-nowrap px-3 py-2 text-xs text-slate-500">
                            {formatDistanceToNow(new Date(a.created_at), { addSuffix: true })}
                          </td>
                          <td className="px-3 py-2 text-xs text-slate-300">{a.alert_type}</td>
                          <td className="px-3 py-2">
                            <span
                              className={cn(
                                "rounded-full border px-2 py-0.5 text-[11px] font-semibold",
                                severityClass[a.severity] ?? "border-slate-600 bg-slate-800 text-slate-400"
                              )}
                            >
                              {a.severity}
                            </span>
                          </td>
                          <td className="max-w-md px-3 py-2 text-xs text-slate-400">{a.message}</td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </CardContent>
      </Card>

      <Card className="border-slate-800 bg-[#1a1d27]">
        <CardContent className="space-y-5 p-6">
          <div>
            <h2 className="text-base font-semibold text-white">Operational snapshot</h2>
            <p className="mt-1 text-xs text-slate-500">
              Source: Django REST — pending/, published/, stats/summary/, categories/. If every call returns{" "}
              <code className="text-slate-400">count: 0</code>, there is no announcement data for your user&apos;s church
              yet (or the user lacks secretariat visibility for drafts).
            </p>
          </div>

          {!bootLoading && waitingPlatformScope && (
            <p className="text-sm text-slate-400">Select a church to load announcement API data.</p>
          )}
          {!bootLoading && !waitingPlatformScope && needsChurch && (
            <p className="text-sm text-amber-200/90">Church scope required for this dashboard view.</p>
          )}

          {scopeReady && listsLoading && <Skeleton className="h-40 bg-slate-800" />}

          {scopeReady && !listsLoading && (
            <>
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                <div className="rounded-lg border border-slate-800 bg-[#151824] px-4 py-3">
                  <p className="text-[11px] uppercase text-slate-500">Total (stats)</p>
                  <p className="mt-1 text-2xl font-semibold text-white">{totalAnnouncements ?? "—"}</p>
                </div>
                <div className="rounded-lg border border-slate-800 bg-[#151824] px-4 py-3">
                  <p className="text-[11px] uppercase text-slate-500">Pending review</p>
                  <p className="mt-1 text-2xl font-semibold text-[#f4a261]">{pendingRows.length}</p>
                </div>
                <div className="rounded-lg border border-slate-800 bg-[#151824] px-4 py-3">
                  <p className="text-[11px] uppercase text-slate-500">Published (page)</p>
                  <p className="mt-1 text-2xl font-semibold text-emerald-300/90">{publishedRows.length}</p>
                </div>
                <div className="rounded-lg border border-slate-800 bg-[#151824] px-4 py-3">
                  <p className="text-[11px] uppercase text-slate-500">Categories</p>
                  <p className="mt-1 text-2xl font-semibold text-slate-200">
                    {categoriesLoading ? "…" : categoryRows.length}
                  </p>
                </div>
              </div>

              <div className="grid gap-6 lg:grid-cols-2">
                <div>
                  <h3 className="mb-2 text-sm font-medium text-white">Awaiting approval</h3>
                  <div className="overflow-x-auto rounded-lg border border-slate-800">
                    <table className="w-full text-[11px]">
                      <thead>
                        <tr className="border-b border-slate-800 bg-[#151824] text-slate-500">
                          <th className="px-2 py-2 text-left font-medium">Title</th>
                          <th className="px-2 py-2 text-left font-medium">Status</th>
                        </tr>
                      </thead>
                      <tbody>
                        {pendingRows.length === 0 ? (
                          <tr>
                            <td colSpan={2} className="px-2 py-6 text-center text-slate-500">
                              No items in PENDING_REVIEW — nothing stuck in the queue right now.
                            </td>
                          </tr>
                        ) : (
                          pendingRows.map((row, idx) => (
                            <tr key={String(row.id ?? `p-${idx}`)} className="border-b border-slate-800/50">
                              <td className="max-w-[200px] truncate px-2 py-2 text-slate-300">{pickTitle(row)}</td>
                              <td className="whitespace-nowrap px-2 py-2 text-slate-400">{pickStatus(row)}</td>
                            </tr>
                          ))
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>

                <div>
                  <h3 className="mb-2 text-sm font-medium text-white">Published</h3>
                  <div className="overflow-x-auto rounded-lg border border-slate-800">
                    <table className="w-full text-[11px]">
                      <thead>
                        <tr className="border-b border-slate-800 bg-[#151824] text-slate-500">
                          <th className="px-2 py-2 text-left font-medium">Title</th>
                          <th className="px-2 py-2 text-left font-medium">Status</th>
                        </tr>
                      </thead>
                      <tbody>
                        {publishedRows.length === 0 ? (
                          <tr>
                            <td colSpan={2} className="px-2 py-6 text-center text-slate-500">
                              No published announcements returned — create & publish in the main app first.
                            </td>
                          </tr>
                        ) : (
                          publishedRows.map((row, idx) => (
                            <tr key={String(row.id ?? `pub-${idx}`)} className="border-b border-slate-800/50">
                              <td className="max-w-[200px] truncate px-2 py-2 text-slate-300">{pickTitle(row)}</td>
                              <td className="whitespace-nowrap px-2 py-2 text-slate-400">{pickStatus(row)}</td>
                            </tr>
                          ))
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>

              {categoryRows.length > 0 && (
                <div>
                  <h3 className="mb-2 text-sm font-medium text-white">Categories</h3>
                  <div className="flex flex-wrap gap-2">
                    {categoryRows.map((c) => (
                      <Badge key={String(c.id ?? c.name)} variant="outline" className="border-slate-600 text-slate-300">
                        {typeof c.name === "string" ? c.name : "Category"}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
