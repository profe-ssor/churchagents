"use client"

import Link from "next/link"
import { useMemo, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { formatDistanceToNow } from "date-fns"
import { ArrowRight, Users } from "lucide-react"

import { AgentInfoPanel } from "@/components/agent-info-panel"
import { PageHeader } from "@/components/page-header"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { useDashboardChurchScope } from "@/hooks/use-dashboard-church-scope"
import { api } from "@/lib/api"
import type { AgentAlert, AgentLog } from "@/lib/types"
import { cn } from "@/lib/utils"

const MEMBER_AGENT_NAME = "MemberCareAgent"
const ACCENT = "#ffd166"

/** Backend returns a JSON array or (if paginated elsewhere) `{ results: [...] }`. */
function memberRowsFromResponse(data: unknown): Record<string, unknown>[] {
  if (Array.isArray(data)) return data
  if (
    data &&
    typeof data === "object" &&
    Array.isArray((data as { results?: unknown }).results)
  ) {
    return (data as { results: Record<string, unknown>[] }).results
  }
  return []
}

function memberDisplayName(row: Record<string, unknown>): string {
  const fn = typeof row.first_name === "string" ? row.first_name : ""
  const mn =
    typeof row.middle_name === "string" && row.middle_name.trim()
      ? ` ${row.middle_name}`
      : ""
  const ln = typeof row.last_name === "string" ? row.last_name : ""
  const composed = `${fn}${mn} ${ln}`.trim()
  return composed || "—"
}

function nestedLocation(row: Record<string, unknown>): Record<string, unknown> | null {
  const loc = row.location
  if (loc && typeof loc === "object") return loc as Record<string, unknown>
  return null
}

function memberEmail(row: Record<string, unknown>): string {
  const loc = nestedLocation(row)
  const le = loc && typeof loc.email === "string" ? loc.email : ""
  return le.trim()
}

function memberPhone(row: Record<string, unknown>): string {
  const loc = nestedLocation(row)
  const p =
    loc && typeof loc.phone_primary === "string" ? loc.phone_primary.trim() : ""
  return p || "—"
}

function departmentCell(row: Record<string, unknown>): string {
  const dn = row.department_names
  if (Array.isArray(dn) && dn.every((x) => typeof x === "string")) {
    return (dn as string[]).join(", ") || "—"
  }
  return "—"
}

function statusBadgeVariant(
  status: string
): "default" | "secondary" | "destructive" | "outline" {
  switch (status) {
    case "ACTIVE":
      return "default"
    case "INACTIVE":
      return "secondary"
    case "TRANSFER":
      return "destructive"
    default:
      return "outline"
  }
}

function scopeFiltersMemberCareRow(
  row: { agent_name: string; church_id?: string | null },
  churchId: string
): boolean {
  if (row.agent_name !== MEMBER_AGENT_NAME) return false
  if (!churchId) return false
  return row.church_id === churchId || row.church_id === null
}

const severityClass: Record<string, string> = {
  CRITICAL: "border-[#ff6b6b44] bg-[#ff6b6b22] text-[#ff6b6b]",
  WARNING: "border-[#ffd16644] bg-[#ffd16622] text-[#ffd166]",
}

const MEMBER_CARE_BULLETS = [
  "Finds members whose birthday is today (per church) and sends them a congratulatory email.",
  "Emails recent visitors at follow-up intervals you configure (days since visit).",
  "Creates dashboard alerts when members look inactive beyond the configured day threshold.",
  "Writes each scheduled run to Agent Logs with counts for birthdays, visitor emails, and inactive highlights.",
] as const

export default function MembersPage() {
  const [showRawResponse, setShowRawResponse] = useState(false)
  const {
    sessionInfo,
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
  } = useDashboardChurchScope("churchagents_members_church_scope")

  const scopeReady = Boolean(
    sessionReady && churchesReady && effectiveChurchId && sessionInfo?.authenticated
  )

  const { data, isLoading, error } = useQuery({
    queryKey: ["members", "list", effectiveChurchId ?? "none"],
    queryFn: () =>
      api.getMembers({
        page_size: "100",
        ...(effectiveChurchId ? { church_id: effectiveChurchId } : {}),
      }),
    enabled: scopeReady,
  })

  const { data: alertsData, isLoading: alertsLoading } = useQuery({
    queryKey: ["member-care-agent-alerts", effectiveChurchId ?? "none"],
    queryFn: () => api.getAgentAlerts({ page_size: "200" }),
    enabled: scopeReady,
    refetchInterval: 60_000,
  })

  const { data: logsData, isLoading: logsLoading } = useQuery({
    queryKey: ["member-care-agent-logs", effectiveChurchId ?? "none"],
    queryFn: () => api.getAgentLogs({ page_size: "80" }),
    enabled: scopeReady,
    refetchInterval: 60_000,
  })

  const alertList = (alertsData?.results ?? []) as AgentAlert[]
  const logList = (logsData?.results ?? []) as AgentLog[]

  const alertsForChurch = effectiveChurchId
    ? alertList.filter((a) => scopeFiltersMemberCareRow(a, effectiveChurchId))
    : []

  const selectedChurchName = churches.find((c) => c.id === effectiveChurchId)?.name

  const logsForChurch = effectiveChurchId
    ? logList.filter((log) => {
        if (log.agent_name !== MEMBER_AGENT_NAME) return false
        const cid = log.church_id ?? null
        if (cid === effectiveChurchId) return true
        if (selectedChurchName && log.church_name === selectedChurchName) return true
        return false
      })
    : []

  const logsForChurchSorted = [...logsForChurch].sort(
    (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
  )

  const latestMemberCareRun = logsForChurchSorted[0]
  const lastRunLabel = latestMemberCareRun
    ? formatDistanceToNow(new Date(latestMemberCareRun.created_at), { addSuffix: true })
    : undefined

  const recentAlerts = [...alertsForChurch]
    .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
    .slice(0, 12)

  const monitorLoading = alertsLoading || logsLoading

  const memberRows = useMemo(() => (data != null ? memberRowsFromResponse(data) : []), [data])

  return (
    <div className="space-y-6">
      <PageHeader
        title="Members"
        description="MemberCareAgent — pastoral care signals; below you see scheduled agent activity for this church and live membership data from Django."
        icon={Users}
        color={ACCENT}
        agentName={MEMBER_AGENT_NAME}
        lastRun={lastRunLabel}
      />

      <AgentInfoPanel
        agentName={MEMBER_AGENT_NAME}
        schedule="Typical schedule (Celery Beat): daily at 08:00 — see churchagents `scheduler/celery_app.py` (timezone there applies)."
        bullets={MEMBER_CARE_BULLETS}
        accent={ACCENT}
        footerNote={
          "The “Agent activity” card shows alerts and runs from MemberCareAgent for the selected church. The “Congregation roster” card is live data from GET /api/members/members/ (Django), not from the LLM."
        }
      />

      {showScopePicker && (
        <div className="flex max-w-xl flex-col gap-1.5 rounded-lg border border-slate-800 bg-[#1a1d27] p-4">
          <label htmlFor="members-church-scope" className="text-xs font-medium text-slate-400">
            Which church should we show?
          </label>
          <select
            id="members-church-scope"
            value={scopeChurchId}
            onChange={(e) => setScopeChurchId(e.target.value)}
            aria-describedby="members-scope-hint"
            className="rounded-lg border border-slate-700 bg-[#21253a] px-3 py-2 text-sm text-white outline-none focus:border-[#ffd166]"
          >
            <option value="">Select a church…</option>
            {churches.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
          <p id="members-scope-hint" className="text-[11px] leading-snug text-slate-500">
            Agent activity, roster, and statistics are scoped to this congregation. Selection is remembered on this
            device.
          </p>
        </div>
      )}

      <Card className="border-slate-800 bg-[#1a1d27]">
        <CardContent className="space-y-4 p-6">
          <div>
            <h2 className="text-base font-semibold text-white">{MEMBER_AGENT_NAME} activity</h2>
            <p className="mt-1 text-xs text-slate-500">
              Alerts and scheduled runs from the same pipeline as{" "}
              <code className="text-slate-400">agents/member_care.py</code>.
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
                <span className="text-slate-400">Latest scheduled run</span>
                {latestMemberCareRun ? (
                  <>
                    <Badge variant="outline" className="border-slate-600 font-mono text-xs text-slate-300">
                      {latestMemberCareRun.action}
                    </Badge>
                    <span
                      className={cn(
                        "rounded-full px-2 py-0.5 text-xs font-semibold",
                        latestMemberCareRun.status === "SUCCESS"
                          ? "bg-[#ffd16622] text-[#ffd166]"
                          : latestMemberCareRun.status === "FAILED"
                            ? "bg-[#ff6b6b22] text-[#ff6b6b]"
                            : "bg-slate-700 text-slate-300"
                      )}
                    >
                      {latestMemberCareRun.status}
                    </span>
                    <span className="text-xs text-slate-500">
                      {formatDistanceToNow(new Date(latestMemberCareRun.created_at), { addSuffix: true })} ·{" "}
                      {latestMemberCareRun.duration_ms}ms
                    </span>
                  </>
                ) : (
                  <span className="text-slate-500">No MemberCareAgent runs logged for this church yet.</span>
                )}
                <Link
                  href="/logs"
                  className="ml-auto inline-flex items-center gap-1 text-xs font-medium text-[#ffd166] hover:underline"
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
                          No MemberCareAgent alerts for this church. When the scheduled job highlights inactive members
                          or similar issues, they appear here.
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
        <CardContent className="p-6">
          <h2 className="mb-1 text-base font-semibold text-white">Congregation roster</h2>
          <p className="mb-4 text-xs text-slate-500">
            Live directory from <code className="text-slate-400">GET /api/members/members/</code> — operational context
            alongside the agent monitor above.
          </p>
          {bootLoading && <Skeleton className="min-h-[200px] bg-slate-800" />}
          {!bootLoading && waitingPlatformScope && (
            <p className="text-sm text-slate-400">Choose a church above to load members.</p>
          )}
          {!bootLoading && !waitingPlatformScope && isLoading && Boolean(effectiveChurchId) && (
            <Skeleton className="h-40 bg-slate-800" />
          )}
          {!bootLoading && needsChurch && (
            <p className="text-sm text-amber-200/90">
              No church is associated with this account and none were listed. Ensure your user has a church or that
              `/api/auth/churches/` returns your congregation.
            </p>
          )}
          {!bootLoading && !waitingPlatformScope && error && (
            <p className="text-sm text-slate-400">
              Could not load members. Check `/api/members/members/` permissions for your user.
            </p>
          )}
          {!bootLoading &&
            !waitingPlatformScope &&
            !isLoading &&
            !error &&
            !needsChurch &&
            effectiveChurchId && (
              <div className="space-y-4">
                <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-800 pb-3">
                  <p className="text-sm text-slate-400">
                    <span className="font-medium text-slate-200">{memberRows.length}</span> member
                    {memberRows.length === 1 ? "" : "s"} in this response
                    {memberRows.length >= 100 ? " (cap 100)" : ""}.
                  </p>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="border-slate-600 bg-transparent text-xs text-slate-300 hover:bg-slate-800"
                    onClick={() => setShowRawResponse((v) => !v)}
                  >
                    {showRawResponse ? "Hide raw JSON" : "Show raw JSON"}
                  </Button>
                </div>

                {memberRows.length === 0 ? (
                  <p className="text-sm text-slate-400">
                    No members returned for this church (empty list from the API).
                  </p>
                ) : (
                  <div className="overflow-x-auto rounded-lg border border-slate-800">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-slate-800 bg-[#151824]">
                          <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                            Name
                          </th>
                          <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                            Email
                          </th>
                          <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                            Phone
                          </th>
                          <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                            Status
                          </th>
                          <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                            Departments
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        {memberRows.map((row, idx) => {
                          const id =
                            typeof row.id === "string"
                              ? row.id
                              : typeof row.id === "number"
                                ? String(row.id)
                                : ""
                          const status =
                            typeof row.membership_status === "string" ? row.membership_status : ""
                          const email = memberEmail(row)
                          return (
                            <tr key={id || `member-row-${idx}`} className="border-b border-slate-800/60 last:border-0">
                              <td className="px-3 py-2 font-medium text-slate-200">{memberDisplayName(row)}</td>
                              <td className="px-3 py-2 text-slate-300">
                                {email ? (
                                  <a
                                    href={`mailto:${encodeURIComponent(email)}`}
                                    className="text-[#ffd166]/90 underline-offset-2 hover:underline"
                                  >
                                    {email}
                                  </a>
                                ) : (
                                  "—"
                                )}
                              </td>
                              <td className="px-3 py-2 font-mono text-xs text-slate-400">{memberPhone(row)}</td>
                              <td className="px-3 py-2">
                                {status ? (
                                  <Badge
                                    variant={statusBadgeVariant(status)}
                                    className="text-[10px] uppercase tracking-wide"
                                  >
                                    {status.replace(/_/g, " ")}
                                  </Badge>
                                ) : (
                                  "—"
                                )}
                              </td>
                              <td className="max-w-[280px] px-3 py-2 text-xs text-slate-400">
                                {departmentCell(row)}
                              </td>
                            </tr>
                          )
                        })}
                      </tbody>
                    </table>
                  </div>
                )}

                {showRawResponse && data !== undefined && (
                  <pre className="max-h-[360px] overflow-auto rounded-lg border border-slate-800 bg-[#0d1117] p-4 text-xs text-slate-400">
                    {JSON.stringify(data, null, 2)}
                  </pre>
                )}
              </div>
            )}
        </CardContent>
      </Card>
    </div>
  )
}
