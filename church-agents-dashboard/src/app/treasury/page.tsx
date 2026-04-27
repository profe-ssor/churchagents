"use client"

import Link from "next/link"
import { useQuery } from "@tanstack/react-query"
import { formatDistanceToNow } from "date-fns"
import { ArrowRight, DollarSign } from "lucide-react"

import { AgentInfoPanel } from "@/components/agent-info-panel"
import { AgentTaskFlow } from "@/components/agent-task-flow"
import { PageHeader } from "@/components/page-header"
import { TreasuryStatisticsView } from "@/components/treasury-statistics-view"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { useDashboardChurchScope } from "@/hooks/use-dashboard-church-scope"
import { api } from "@/lib/api"
import type { AgentAlert, AgentLog, TreasuryStatistics } from "@/lib/types"
import { cn } from "@/lib/utils"

const TREASURY_AGENT_NAME = "TreasuryHealthAgent"

function isTreasuryStatistics(data: unknown): data is TreasuryStatistics {
  if (!data || typeof data !== "object") return false
  const o = data as Record<string, unknown>
  if ("error" in o) return false
  return typeof o.total_income !== "undefined" && typeof o.total_expenses !== "undefined"
}

const TREASURY_AGENT_BULLETS = [
  "Iterates every active church and calls treasury MCP endpoints for that tenant.",
  "Creates WARNING alerts (STALLED_EXPENSE) when approvals exceed EXPENSE_STALL_THRESHOLD_HOURS.",
  "Creates CRITICAL alerts (ANOMALY_TRANSACTION) when a transaction exceeds ANOMALY_TRANSACTION_THRESHOLD.",
  "Optionally (TREASURY_EXTENDED_HEALTH_CHECKS) flags no recent income and high program budget utilization per department.",
  "Orchestrator can call income/expense summaries, detect_anomalies, get_treasury_statistics, get_asset_inventory, get_budget_vs_actual, generate_financial_report (JSON), and send_treasurer_alert.",
  "Emails PLATFORM_ADMIN_EMAIL with a digest when any issues are found (requires outbound email).",
  "Writes AgentAlert rows and logs treasury_health_check to AgentLog on each scheduled run.",
] as const

const TREASURY_TASK_STEPS = [
  {
    title: "Scheduled run",
    description:
      "Celery Beat invokes the treasury health job on a fixed interval — the same pipeline as agents/treasury_health.py.",
  },
  {
    title: "Pull live data",
    description:
      "For each tenant, the job calls Django/MCP treasury APIs: pending expenses, transactions, statistics — not cached dashboard snapshots.",
  },
  {
    title: "Detect risks",
    description:
      "Rules fire on stalled expense approvals, oversized transactions (anomaly threshold), and optional extended checks (income gaps, department budget pressure).",
  },
  {
    title: "Surface & record",
    description:
      "Creates AgentAlert rows (severity by rule), optional digest email to admins, and an AgentLog row so this page can show outcomes.",
  },
] as const

const severityClass: Record<string, string> = {
  CRITICAL: "border-[#ff6b6b44] bg-[#ff6b6b22] text-[#ff6b6b]",
  WARNING: "border-[#ffd16644] bg-[#ffd16622] text-[#ffd166]",
}

function scopeFiltersTreasuryRow(
  row: { agent_name: string; church_id?: string | null },
  churchId: string
): boolean {
  if (row.agent_name !== TREASURY_AGENT_NAME) return false
  if (!churchId) return false
  return row.church_id === churchId || row.church_id === null
}

export default function TreasuryPage() {
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
  } = useDashboardChurchScope("churchagents_treasury_church_scope")

  const scopeReady = Boolean(
    sessionReady && churchesReady && effectiveChurchId && sessionInfo?.authenticated
  )

  const { data, isLoading, error } = useQuery({
    queryKey: ["treasury-stats", effectiveChurchId ?? "none"],
    queryFn: () =>
      api.getTreasuryStats(effectiveChurchId ? { church_id: effectiveChurchId } : undefined),
    enabled: scopeReady,
  })

  const { data: alertsData, isLoading: alertsLoading } = useQuery({
    queryKey: ["treasury-agent-alerts", effectiveChurchId ?? "none"],
    queryFn: () => api.getAgentAlerts({ page_size: "200" }),
    enabled: scopeReady,
    refetchInterval: 60_000,
  })

  const { data: logsData, isLoading: logsLoading } = useQuery({
    queryKey: ["treasury-agent-logs", effectiveChurchId ?? "none"],
    queryFn: () => api.getAgentLogs({ page_size: "80" }),
    enabled: scopeReady,
    refetchInterval: 60_000,
  })

  const alertList = (alertsData?.results ?? []) as AgentAlert[]
  const logList = (logsData?.results ?? []) as AgentLog[]

  const alertsForChurch = effectiveChurchId
    ? alertList.filter((a) => scopeFiltersTreasuryRow(a, effectiveChurchId))
    : []

  const selectedChurchName = churches.find((c) => c.id === effectiveChurchId)?.name

  const logsForChurch = effectiveChurchId
    ? logList.filter((log) => {
        if (log.agent_name !== TREASURY_AGENT_NAME) return false
        const cid = log.church_id ?? null
        if (cid === effectiveChurchId) return true
        if (selectedChurchName && log.church_name === selectedChurchName) return true
        return false
      })
    : []

  const logsForChurchSorted = [...logsForChurch].sort(
    (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
  )

  const latestTreasuryRun = logsForChurchSorted[0]
  const lastRunLabel = latestTreasuryRun
    ? formatDistanceToNow(new Date(latestTreasuryRun.created_at), { addSuffix: true })
    : undefined

  const recentAlerts = [...alertsForChurch]
    .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
    .slice(0, 12)

  const monitorLoading = alertsLoading || logsLoading

  return (
    <div className="space-y-6">
      <PageHeader
        title="Treasury Monitor"
        description="TreasuryHealthAgent watches this church on a schedule: pull treasury data → apply stall/anomaly rules → raise alerts and logs. The cards below separate agent outputs from raw API totals."
        icon={DollarSign}
        color="#00d4aa"
        agentName="TreasuryHealthAgent"
        lastRun={lastRunLabel}
      />

      <AgentTaskFlow accent="#00d4aa" steps={TREASURY_TASK_STEPS} />

      <AgentInfoPanel
        agentName="TreasuryHealthAgent"
        schedule="Typical schedule (Celery Beat): every 12 hours — see churchagents `scheduler/celery_app.py`."
        bullets={TREASURY_AGENT_BULLETS}
        accent="#00d4aa"
        defaultOpen
        footerNote="Expand/collapse anytime. The “TreasuryHealthAgent activity” card is alerts + runs from the scheduled job. “Financial snapshot” is live GET /api/treasury/statistics/ for context (same numbers the agent can read via tools). Orchestrator chat can call treasury tools separately — that is interactive, not this schedule."
      />

      {showScopePicker && (
        <div className="flex max-w-xl flex-col gap-1.5 rounded-lg border border-slate-800 bg-[#1a1d27] p-4">
          <label htmlFor="treasury-church-scope" className="text-xs font-medium text-slate-400">
            Which church should we show?
          </label>
          <select
            id="treasury-church-scope"
            value={scopeChurchId}
            onChange={(e) => setScopeChurchId(e.target.value)}
            aria-describedby="treasury-scope-hint"
            className="rounded-lg border border-slate-700 bg-[#21253a] px-3 py-2 text-sm text-white outline-none focus:border-[#00d4aa]"
          >
            <option value="">Select a church…</option>
            {churches.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
          <p id="treasury-scope-hint" className="text-[11px] leading-snug text-slate-500">
            Agent alerts, last run, and treasury statistics are scoped to this congregation. Selection is remembered on
            this device.
          </p>
        </div>
      )}

      <Card className="border-slate-800 bg-[#1a1d27]">
        <CardContent className="space-y-4 p-6">
          <div>
            <h2 className="text-base font-semibold text-white">TreasuryHealthAgent activity</h2>
            <p className="mt-1 text-xs text-slate-500">
              Observable outputs from the agent job — alerts it created and log lines it wrote for this church. Same
              codebase as <code className="text-slate-400">agents/treasury_health.py</code>.
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
                {latestTreasuryRun ? (
                  <>
                    <Badge variant="outline" className="border-slate-600 font-mono text-xs text-slate-300">
                      {latestTreasuryRun.action}
                    </Badge>
                    <span
                      className={cn(
                        "rounded-full px-2 py-0.5 text-xs font-semibold",
                        latestTreasuryRun.status === "SUCCESS"
                          ? "bg-[#00d4aa22] text-[#00d4aa]"
                          : latestTreasuryRun.status === "FAILED"
                            ? "bg-[#ff6b6b22] text-[#ff6b6b]"
                            : "bg-slate-700 text-slate-300"
                      )}
                    >
                      {latestTreasuryRun.status}
                    </span>
                    <span className="text-xs text-slate-500">
                      {formatDistanceToNow(new Date(latestTreasuryRun.created_at), { addSuffix: true })} ·{" "}
                      {latestTreasuryRun.duration_ms}ms
                    </span>
                  </>
                ) : (
                  <span className="text-slate-500">No TreasuryHealthAgent runs logged for this church yet.</span>
                )}
                <Link
                  href="/logs"
                  className="ml-auto inline-flex items-center gap-1 text-xs font-medium text-[#00d4aa] hover:underline"
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
                          No TreasuryHealthAgent alerts for this church. When the scheduled job finds stalled expenses
                          or large transactions, they appear here.
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
          <h2 className="mb-4 text-base font-semibold text-white">Financial snapshot</h2>
          <p className="mb-4 text-xs text-slate-500">
            Direct API totals (not produced by the scheduled agent run). Use it as ground truth next to the agent
            activity card — the agent’s tools read the same backend when the orchestrator answers questions.
          </p>
          {bootLoading && <Skeleton className="min-h-[200px] bg-slate-800" />}
          {!bootLoading && waitingPlatformScope && (
            <p className="text-sm text-slate-400">Choose a church above to load treasury statistics.</p>
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
          {!bootLoading && !waitingPlatformScope && error != null ? (
            <p className="text-sm text-slate-400">
              Could not load treasury statistics. Confirm your Django user can access{" "}
              <code className="text-slate-300">GET /api/treasury/statistics/?church_id=…</code>.
            </p>
          ) : null}
          {!bootLoading &&
          !waitingPlatformScope &&
          !isLoading &&
          error == null &&
          !needsChurch &&
          effectiveChurchId &&
          data != null &&
          !isTreasuryStatistics(data) ? (
            <pre className="max-h-[320px] overflow-auto rounded-lg bg-[#0d1117] p-4 text-xs text-amber-200/90">
              {JSON.stringify(data, null, 2)}
            </pre>
          ) : null}
          {!bootLoading &&
          !waitingPlatformScope &&
          !isLoading &&
          error == null &&
          !needsChurch &&
          effectiveChurchId &&
          data != null &&
          isTreasuryStatistics(data) ? (
            <TreasuryStatisticsView data={data} />
          ) : null}
        </CardContent>
      </Card>
    </div>
  )
}
