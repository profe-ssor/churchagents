"use client"

import Link from "next/link"
import { useQuery } from "@tanstack/react-query"
import { formatDistanceToNow } from "date-fns"
import { ArrowRight, Shield } from "lucide-react"

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

const AUDIT_AGENT_NAME = "AuditSecurityAgent"

const AUDIT_TOOLS: { name: string; purpose: string }[] = [
  { name: "get_audit_logs", purpose: "Paginated AuditLog via GET /api/activity/ (filters, date range)." },
  { name: "get_failed_login_attempts", purpose: "Aggregate LOGIN_FAILED for brute-force style patterns." },
  { name: "get_permission_changes", purpose: "PERMISSION_CHANGE + ROLE_CHANGE rows for RBAC review." },
  { name: "get_locked_accounts", purpose: "Users with active failed-login lock (auth/users?locked_only=true)." },
  { name: "flag_suspicious_activity", purpose: "Raise AgentAlert for support (LOCKOUT, BULK, PERM, LOGIN, etc.)." },
  { name: "generate_audit_report", purpose: "Structured compliance JSON (+ treasury cross-check when scoped)." },
  { name: "send_security_alert", purpose: "Urgent admin email via Django notifications (outbound gate aware)." },
  { name: "detect_bulk_actions", purpose: "DELETE volume in a short window vs threshold (mass delete signal)." },
]

const AUDIT_TRIGGERS = [
  { kind: "REAL-TIME", text: "Account locked after repeated failed logins → LOCKOUT alert on scheduled scan." },
  { kind: "SCHEDULED", text: "Nightly 1:00 AM — full audit sweep (Celery `run_audit_security`)." },
  { kind: "EVENT", text: "Many DELETE rows in a 5-minute window → BULK alert." },
  { kind: "EVENT", text: "Logins at odd UTC hours → LOGIN warning (heuristic sample)." },
  { kind: "ON-DEMAND", text: 'Orchestrator / dashboard: "security events for Church X this week".' },
] as const

const AUDIT_ALERTS = [
  { code: "LOCKOUT", text: "Time-based account lock from failed attempts." },
  { code: "BULK", text: "Elevated DELETE activity in a short window." },
  { code: "PERM", text: "RBAC changes detected in the audit period." },
  { code: "LOGIN", text: "Brute-force pattern or unusual-hour logins." },
  { code: "TREASURY_CROSSREF", text: "Treasury large transactions alongside financial-model audit noise." },
] as const

const AUDIT_AGENT_BULLETS = [
  "Orchestrator exposes eight audit tools (see table) backed by Django AuditLog, users API, and treasury MCP helpers.",
  "Scheduled job (`agents/audit_security.py`) runs nightly: bulk deletes, failed-login aggregates, lockouts, RBAC summary, treasury cross-check sample.",
  "Critical / warning findings create AgentAlert rows; optional digest email to PLATFORM_ADMIN_EMAIL when configured.",
  "Dashboard below shows alerts + agent logs for AuditSecurityAgent and a live activity table for the selected church.",
] as const

const AUDIT_TASK_STEPS = [
  {
    title: "Collect signals",
    description:
      "Pull /api/activity/ with time bounds, permission-change bundle, locked users, and DELETE density in a sliding window.",
  },
  {
    title: "Classify risk",
    description:
      "Map events to LOCKOUT, BULK, PERM, LOGIN, and optional TREASURY_CROSSREF using thresholds from env and heuristics.",
  },
  {
    title: "Record & notify",
    description:
      "Write AgentAlert + AgentLog; optional email digest to platform admin for follow-up in the dashboard.",
  },
] as const

const severityClass: Record<string, string> = {
  CRITICAL: "border-[#ff6b6b44] bg-[#ff6b6b22] text-[#ff6b6b]",
  WARNING: "border-[#ffd16644] bg-[#ffd16622] text-[#ffd166]",
  INFO: "border-slate-600 bg-slate-800 text-slate-300",
}

interface ActivityRow {
  id?: string
  action?: string
  action_display?: string
  model_name?: string
  user_email?: string | null
  user_display?: string | null
  church_name?: string | null
  ip_address?: string | null
  description?: string
  created_at?: string
}

/** Django UserView list row when locked_only=true */
interface LockedUserRow {
  id?: string
  email?: string
  username?: string
  failed_login_attempts?: number
  account_locked_until?: string
}

function scopeFiltersAuditRow(
  row: { agent_name: string; church_id?: string | null },
  churchId: string
): boolean {
  if (row.agent_name !== AUDIT_AGENT_NAME) return false
  if (!churchId) return false
  return row.church_id === churchId || row.church_id === null
}

export default function SecurityPage() {
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
  } = useDashboardChurchScope("churchagents_security_church_scope")

  const scopeReady = Boolean(
    sessionReady && churchesReady && effectiveChurchId && sessionInfo?.authenticated
  )

  const activityParams: Record<string, string> = {}
  if (effectiveChurchId) {
    activityParams.church_id = effectiveChurchId
    activityParams.page_size = "40"
  }

  const { data: activityData, isLoading: activityLoading, error: activityError } = useQuery({
    queryKey: ["audit-activity", effectiveChurchId ?? "none"],
    queryFn: () => api.getAuditLogs(activityParams),
    enabled: scopeReady,
  })

  const { data: lockedRaw, isLoading: lockedLoading } = useQuery({
    queryKey: ["audit-locked", effectiveChurchId ?? "none"],
    queryFn: () =>
      api.getLockedUsers({
        locked_only: "true",
        ...(effectiveChurchId ? { church_id: effectiveChurchId } : {}),
      }),
    enabled: scopeReady,
  })

  const { data: alertsData, isLoading: alertsLoading } = useQuery({
    queryKey: ["audit-agent-alerts", effectiveChurchId ?? "none"],
    queryFn: () => api.getAgentAlerts({ page_size: "200" }),
    enabled: scopeReady,
    refetchInterval: 60_000,
  })

  const { data: logsData, isLoading: logsLoading } = useQuery({
    queryKey: ["audit-agent-logs", effectiveChurchId ?? "none"],
    queryFn: () => api.getAgentLogs({ page_size: "80" }),
    enabled: scopeReady,
    refetchInterval: 60_000,
  })

  const activityRows = (
    Array.isArray((activityData as { results?: unknown })?.results)
      ? (activityData as { results: ActivityRow[] }).results
      : []
  ) as ActivityRow[]

  const lockedUsers: LockedUserRow[] = Array.isArray(lockedRaw)
    ? (lockedRaw as LockedUserRow[])
    : []
  const alertList = (alertsData?.results ?? []) as AgentAlert[]
  const logList = (logsData?.results ?? []) as AgentLog[]

  const alertsForChurch = effectiveChurchId
    ? alertList.filter((a) => scopeFiltersAuditRow(a, effectiveChurchId))
    : []

  const logsForChurch = effectiveChurchId
    ? logList.filter((log) => {
        if (log.agent_name !== AUDIT_AGENT_NAME) return false
        const cid = log.church_id ?? null
        return cid === effectiveChurchId || cid === null
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

  return (
    <div className="space-y-6">
      <PageHeader
        title="Audit & Security Monitor"
        description="AuditSecurityAgent (AGENT 7) — compliance-oriented monitoring on top of Django AuditLog, lockouts, RBAC changes, and treasury cross-reference."
        icon={Shield}
        color="#f4a261"
        agentName={AUDIT_AGENT_NAME}
        lastRun={lastRunLabel}
      />
      {process.env.NEXT_PUBLIC_BUILD_ID ? (
        <p className="mb-2 text-[10px] text-slate-600">
          Dashboard build: <span className="font-mono">{process.env.NEXT_PUBLIC_BUILD_ID}</span> — if you still see
          the old &quot;Security&quot; + raw JSON page, this line is missing in the browser (stale deploy or wrong host).
        </p>
      ) : null}

      <AgentTaskFlow accent="#f4a261" steps={AUDIT_TASK_STEPS} />

      <AgentInfoPanel
        agentName={AUDIT_AGENT_NAME}
        schedule="Typical schedule (Celery Beat): nightly at 1:00 AM — see `scheduler/celery_app.py` (`audit-security`)."
        bullets={AUDIT_AGENT_BULLETS}
        accent="#f4a261"
        defaultOpen
        footerNote="Orchestrator chat can invoke the same audit tools interactively; this page focuses on scheduled agent outputs plus live activity for the scoped church."
      />

      <Card className="border-slate-800 bg-[#1a1d27]">
        <CardContent className="space-y-4 p-6">
          <h2 className="text-base font-semibold text-white">Orchestrator tools (AGENT 7)</h2>
          <p className="text-xs text-slate-500">
            These names map to <code className="text-slate-400">run_orchestrator_tool</code> handlers calling{" "}
            <code className="text-slate-400">mcp_server/tools/audit_security.py</code>.
          </p>
          <div className="overflow-x-auto rounded-lg border border-slate-800">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-800 bg-[#151824]">
                  <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                    Tool
                  </th>
                  <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                    Role
                  </th>
                </tr>
              </thead>
              <tbody>
                {AUDIT_TOOLS.map((t) => (
                  <tr key={t.name} className="border-b border-slate-800/60 last:border-0">
                    <td className="whitespace-nowrap px-3 py-2 font-mono text-xs text-[#f4a261]">{t.name}</td>
                    <td className="px-3 py-2 text-xs text-slate-400">{t.purpose}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="border-slate-800 bg-[#1a1d27]">
          <CardContent className="p-6">
            <h2 className="text-base font-semibold text-white">Triggers</h2>
            <ul className="mt-3 space-y-2 text-xs text-slate-400">
              {AUDIT_TRIGGERS.map((t) => (
                <li key={t.text} className="flex gap-2">
                  <Badge variant="outline" className="shrink-0 border-slate-600 font-mono text-[10px] text-slate-300">
                    {t.kind}
                  </Badge>
                  <span>{t.text}</span>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
        <Card className="border-slate-800 bg-[#1a1d27]">
          <CardContent className="p-6">
            <h2 className="text-base font-semibold text-white">Alert codes</h2>
            <ul className="mt-3 space-y-2 text-xs text-slate-400">
              {AUDIT_ALERTS.map((a) => (
                <li key={a.code} className="flex gap-2">
                  <span className="font-mono text-[#f4a261]">{a.code}</span>
                  <span>{a.text}</span>
                </li>
              ))}
            </ul>
            <p className="mt-4 text-[11px] text-slate-500">
              Monthly compliance PDF is not auto-generated; use <code className="text-slate-400">generate_audit_report</code>{" "}
              for export-ready JSON, or extend with a report service later.
            </p>
          </CardContent>
        </Card>
      </div>

      {showScopePicker && (
        <div className="flex max-w-xl flex-col gap-1.5 rounded-lg border border-slate-800 bg-[#1a1d27] p-4">
          <label htmlFor="security-church-scope" className="text-xs font-medium text-slate-400">
            Which church should we show?
          </label>
          <select
            id="security-church-scope"
            value={scopeChurchId}
            onChange={(e) => setScopeChurchId(e.target.value)}
            aria-describedby="security-scope-hint"
            className="rounded-lg border border-slate-700 bg-[#21253a] px-3 py-2 text-sm text-white outline-none focus:border-[#f4a261]"
          >
            <option value="">Select a church…</option>
            {churches.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
          <p id="security-scope-hint" className="text-[11px] leading-snug text-slate-500">
            Activity feed and lockouts respect this congregation. Platform admins can still use orchestrator tools
            with explicit <code className="text-slate-400">church_id</code>.
          </p>
        </div>
      )}

      <Card className="border-slate-800 bg-[#1a1d27]">
        <CardContent className="space-y-4 p-6">
          <div>
            <h2 className="text-base font-semibold text-white">AuditSecurityAgent activity</h2>
            <p className="mt-1 text-xs text-slate-500">
              Alerts and log lines emitted by the scheduled audit job for this church (plus unscoped platform alerts
              tied to the agent).
            </p>
          </div>

          {bootLoading && <Skeleton className="h-24 bg-slate-800" />}
          {!bootLoading && waitingPlatformScope && (
            <p className="text-sm text-slate-400">Choose a church to load security monitor data.</p>
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
                <span className="text-slate-400">Latest scheduled scan</span>
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
                  <span className="text-slate-500">No AuditSecurityAgent runs logged for this church yet.</span>
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
                          No AuditSecurityAgent alerts for this church. Lockouts, bulk deletes, and RBAC summaries
                          appear here after the nightly job runs.
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

      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="border-slate-800 bg-[#1a1d27]">
          <CardContent className="p-6">
            <h2 className="mb-2 text-base font-semibold text-white">Locked accounts</h2>
            <p className="mb-4 text-xs text-slate-500">
              Live query: <code className="text-slate-400">GET /api/auth/users/?locked_only=true</code> with church
              scope.
            </p>
            {!scopeReady && <p className="text-sm text-slate-500">Select a church to load lockouts.</p>}
            {scopeReady && lockedLoading && <Skeleton className="h-24 bg-slate-800" />}
            {scopeReady && !lockedLoading && lockedUsers.length === 0 && (
              <p className="text-sm text-slate-500">No accounts are currently locked for this church.</p>
            )}
            {scopeReady && !lockedLoading && lockedUsers.length > 0 && (
              <ul className="space-y-2 text-xs text-slate-300">
                {lockedUsers.slice(0, 12).map((u) => (
                  <li
                    key={String(u.id)}
                    className="rounded border border-slate-800 bg-[#151824] px-3 py-2 font-mono text-[11px]"
                  >
                    {u.email || u.username || "—"}{" "}
                    <span className="text-slate-500">
                      · attempts {String(u.failed_login_attempts ?? "")} · until{" "}
                      {u.account_locked_until
                        ? formatDistanceToNow(new Date(u.account_locked_until), { addSuffix: true })
                        : "—"}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        <Card className="border-slate-800 bg-[#1a1d27]">
          <CardContent className="p-6">
            <h2 className="mb-2 text-base font-semibold text-white">Activity feed (audit trail)</h2>
            <p className="mb-4 text-xs text-slate-500">
              Recent <code className="text-slate-400">AuditLog</code> rows for the scoped church (same API the agent
              reads).
            </p>
            {!scopeReady && <p className="text-sm text-slate-500">Select a church to load activity.</p>}
            {scopeReady && activityLoading && <Skeleton className="h-40 bg-slate-800" />}
            {scopeReady && activityError && (
              <p className="text-sm text-slate-400">
                Activity unavailable. Confirm your user has church context or platform admin +{" "}
                <code className="text-slate-500">church_id</code> access.
              </p>
            )}
            {scopeReady && !activityLoading && !activityError && activityRows.length === 0 && (
              <p className="text-sm text-slate-500">No activity rows returned for this range.</p>
            )}
            {scopeReady && !activityLoading && !activityError && activityRows.length > 0 && (
              <div className="max-h-[360px] overflow-auto rounded-lg border border-slate-800">
                <table className="w-full text-left text-xs text-slate-300">
                  <thead className="sticky top-0 bg-[#151824] text-slate-500">
                    <tr>
                      <th className="px-2 py-2">When</th>
                      <th className="px-2 py-2">Action</th>
                      <th className="px-2 py-2">Model</th>
                      <th className="px-2 py-2">Actor</th>
                    </tr>
                  </thead>
                  <tbody>
                    {activityRows.map((row) => (
                      <tr key={row.id} className="border-t border-slate-800/80">
                        <td className="whitespace-nowrap px-2 py-2 text-slate-500">
                          {row.created_at
                            ? formatDistanceToNow(new Date(row.created_at), { addSuffix: true })
                            : "—"}
                        </td>
                        <td className="px-2 py-2 font-mono text-[#f4a261]">{row.action || "—"}</td>
                        <td className="px-2 py-2">{row.model_name || "—"}</td>
                        <td className="max-w-[140px] truncate px-2 py-2" title={row.user_email || ""}>
                          {row.user_email || row.user_display || "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
