"use client"

import { useMemo } from "react"
import { useQuery } from "@tanstack/react-query"
import { formatDistanceToNow } from "date-fns"
import { Activity, ExternalLink } from "lucide-react"
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"

import { PageHeader } from "@/components/page-header"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { api } from "@/lib/api"
import {
  avgLatencyByAgent,
  latencyTrendByDay,
  slowestRuns,
  statusCounts,
  summarizeLatency,
  triggerCounts,
} from "@/lib/observability-metrics"
import type { AgentAlert, AgentLog } from "@/lib/types"

const LANGSMITH_HINT =
  "Add NEXT_PUBLIC_LANGSMITH_UI_URL in .env.local (e.g. your LangSmith project URL) for a one-click link to traces."

export default function ObservabilityPage() {
  const langsmithUrl = process.env.NEXT_PUBLIC_LANGSMITH_UI_URL?.replace(/\/$/, "") ?? ""

  const { data: logsData, isLoading: loadingLogs } = useQuery({
    queryKey: ["observability-agent-logs"],
    queryFn: () => api.getAgentLogs({ page_size: "500" }),
    refetchInterval: 30_000,
  })

  const { data: alertsData, isLoading: loadingAlerts } = useQuery({
    queryKey: ["observability-agent-alerts"],
    queryFn: () => api.getAgentAlerts({ page_size: "200" }),
    refetchInterval: 60_000,
  })

  const logList = useMemo(() => (logsData?.results ?? []) as AgentLog[], [logsData])
  const alertList = useMemo(() => (alertsData?.results ?? []) as AgentAlert[], [alertsData])

  const latency = useMemo(() => summarizeLatency(logList), [logList])
  const trend = useMemo(() => latencyTrendByDay(logList, 14), [logList])
  const byAgent = useMemo(() => avgLatencyByAgent(logList, 1), [logList])
  const statuses = useMemo(() => statusCounts(logList), [logList])
  const triggers = useMemo(() => triggerCounts(logList), [logList])
  const slow = useMemo(() => slowestRuns(logList, 15), [logList])

  /** Newest first; avoid Date.now during render (react-hooks/purity). */
  const recentAlerts = useMemo(() => {
    return [...alertList]
      .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
      .slice(0, 40)
  }, [alertList])

  const sevCounts = useMemo(() => {
    const m: Record<string, number> = {}
    for (const a of recentAlerts.slice(0, 25)) {
      const s = a.severity || "INFO"
      m[s] = (m[s] ?? 0) + 1
    }
    return m
  }, [recentAlerts])

  return (
    <div className="space-y-6">
      <PageHeader
        title="Observability"
        description="Latency and volume from AgentLog; recent AgentAlert observations. Refreshes automatically."
        icon={Activity}
        color="#8892b0"
        agentName="Metrics"
      />

      <div className="flex flex-wrap items-center gap-3 rounded-lg border border-slate-800 bg-[#1a1d27] px-4 py-3 text-xs text-slate-400">
        <span>LLM traces:</span>
        {langsmithUrl ? (
          <a
            href={langsmithUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 font-medium text-[#6c63ff] hover:underline"
          >
            Open LangSmith <ExternalLink className="size-3" />
          </a>
        ) : (
          <span>{LANGSMITH_HINT}</span>
        )}
      </div>

      {!loadingLogs && latency.totalRuns > 0 && latency.runsWithDuration === 0 && (
        <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-100/90">
          <p className="font-medium text-amber-50">Latency shows &quot;—&quot; because every loaded row has duration 0</p>
          <p className="mt-2 text-xs leading-relaxed text-amber-100/80">
            Django stores whatever churchagents sends. Older <code className="rounded bg-black/20 px-1">admin_qa</code> rows
            were logged before the orchestrator started sending real{" "}
            <code className="rounded bg-black/20 px-1">duration_ms</code>, so they stay at the model default (0). Charts
            only use rows where <code className="rounded bg-black/20 px-1">duration_ms &gt; 0</code>. Fix: restart{" "}
            <code className="rounded bg-black/20 px-1">python3 orchestrator_server.py</code> with current churchagents
            code, use Ask CTO a few times, then refresh — new logs should show non-zero duration (full round-trip time).
          </p>
        </div>
      )}

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {loadingLogs ? (
          Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-24 bg-slate-800" />)
        ) : (
          <>
            <MetricCard
              label="Runs (loaded window)"
              value={String(latency.totalRuns)}
              sub={
                latency.totalRuns
                  ? `${latency.runsWithDuration} timed · ${latency.runsWithoutTiming} zero / missing ms`
                  : "Up to 500 latest rows"
              }
            />
            <MetricCard
              label="Avg latency"
              value={latency.runsWithDuration ? `${latency.avgMs} ms` : "—"}
              sub={
                latency.runsWithDuration
                  ? `${latency.runsWithDuration} runs with duration > 0`
                  : `0 of ${latency.totalRuns} loaded rows have duration > 0`
              }
            />
            <MetricCard
              label="p95 / max"
              value={
                latency.runsWithDuration ? `${latency.p95Ms} / ${latency.maxMs} ms` : "—"
              }
              sub="Among runs reporting duration > 0"
            />
            <MetricCard
              label="Recent alerts (loaded)"
              value={String(recentAlerts.length)}
              sub={Object.keys(sevCounts).length ? Object.entries(sevCounts).map(([k, v]) => `${k}:${v}`).join(" · ") : "None"}
            />
          </>
        )}
      </div>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <Card className="border-slate-800 bg-[#1a1d27]">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-semibold text-white">Latency trend (daily avg)</CardTitle>
            <p className="text-xs text-slate-500">Mean duration_ms per day — last 14 days</p>
          </CardHeader>
          <CardContent>
            {loadingLogs ? (
              <Skeleton className="h-[220px] w-full bg-slate-800" />
            ) : (
              <ResponsiveContainer width="100%" height={220}>
                <LineChart data={trend}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#2e3250" />
                  <XAxis dataKey="dateLabel" tick={{ fill: "#8892b0", fontSize: 10 }} interval="preserveStartEnd" />
                  <YAxis tick={{ fill: "#8892b0", fontSize: 10 }} width={44} />
                  <Tooltip
                    content={({ active, payload }) => {
                      if (!active || !payload?.length) return null
                      const row = payload[0]?.payload as (typeof trend)[0]
                      return (
                        <div className="rounded-lg border border-[#2e3250] bg-[#21253a] px-3 py-2 text-xs text-white shadow-lg">
                          <div className="text-[11px] text-slate-400">{row.day}</div>
                          <div>avg {row.avgMs} ms · median {row.medianMs} ms</div>
                          <div className="text-slate-500">{row.count} timed runs</div>
                        </div>
                      )
                    }}
                  />
                  <Line type="monotone" dataKey="avgMs" stroke="#6c63ff" strokeWidth={2} dot name="Avg ms" />
                  <Line type="monotone" dataKey="medianMs" stroke="#00d4aa" strokeWidth={1.5} dot={false} name="Median ms" />
                </LineChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>

        <Card className="border-slate-800 bg-[#1a1d27]">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-semibold text-white">Avg latency by agent</CardTitle>
            <p className="text-xs text-slate-500">Runs with duration_ms &gt; 0 only</p>
          </CardHeader>
          <CardContent>
            {loadingLogs ? (
              <Skeleton className="h-[220px] w-full bg-slate-800" />
            ) : byAgent.length === 0 ? (
              <p className="py-8 text-center text-xs text-slate-500">No timed runs in this window.</p>
            ) : (
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={byAgent} layout="vertical" margin={{ left: 8, right: 16 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#2e3250" horizontal={false} />
                  <XAxis type="number" tick={{ fill: "#8892b0", fontSize: 10 }} />
                  <YAxis
                    type="category"
                    dataKey="agent"
                    width={100}
                    tick={{ fill: "#8892b0", fontSize: 10 }}
                    tickFormatter={(v) => (String(v).length > 14 ? `${String(v).slice(0, 12)}…` : v)}
                  />
                  <Tooltip
                    content={({ active, payload }) => {
                      if (!active || !payload?.length) return null
                      const row = payload[0]?.payload as (typeof byAgent)[0]
                      return (
                        <div className="rounded-lg border border-[#2e3250] bg-[#21253a] px-3 py-2 text-xs text-white shadow-lg">
                          <div className="font-medium">{row.agent}</div>
                          <div>avg {row.avgMs} ms · median {row.medianMs} ms</div>
                          <div className="text-slate-500">{row.runs} runs</div>
                        </div>
                      )
                    }}
                  />
                  <Bar dataKey="avgMs" fill="#6c63ff" radius={[0, 4, 4, 0]} name="Avg ms" />
                </BarChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <Card className="border-slate-800 bg-[#1a1d27]">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-semibold text-white">Status mix</CardTitle>
          </CardHeader>
          <CardContent className="space-y-1 text-xs text-slate-400">
            {Object.keys(statuses).length === 0 ? (
              <p>No logs.</p>
            ) : (
              Object.entries(statuses)
                .sort((a, b) => b[1] - a[1])
                .map(([k, v]) => (
                  <div key={k} className="flex justify-between gap-2">
                    <span className="text-slate-300">{k}</span>
                    <span className="tabular-nums text-slate-500">{v}</span>
                  </div>
                ))
            )}
          </CardContent>
        </Card>

        <Card className="border-slate-800 bg-[#1a1d27]">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-semibold text-white">Trigger mix</CardTitle>
          </CardHeader>
          <CardContent className="space-y-1 text-xs text-slate-400">
            {Object.keys(triggers).length === 0 ? (
              <p>No logs.</p>
            ) : (
              Object.entries(triggers)
                .sort((a, b) => b[1] - a[1])
                .map(([k, v]) => (
                  <div key={k} className="flex justify-between gap-2">
                    <span className="text-slate-300">{k}</span>
                    <span className="tabular-nums text-slate-500">{v}</span>
                  </div>
                ))
            )}
          </CardContent>
        </Card>

        <Card className="border-slate-800 bg-[#1a1d27]">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-semibold text-white">Recent alerts</CardTitle>
            <p className="text-xs text-slate-500">Newest first (up to 12 shown)</p>
          </CardHeader>
          <CardContent className="max-h-[200px] space-y-2 overflow-y-auto text-xs">
            {loadingAlerts ? (
              <Skeleton className="h-16 bg-slate-800" />
            ) : recentAlerts.length === 0 ? (
              <p className="text-slate-500">No alerts returned.</p>
            ) : (
              recentAlerts.slice(0, 12).map((a) => (
                <div key={a.id} className="border-b border-slate-800/80 pb-2 last:border-0">
                  <div className="flex items-center justify-between gap-2">
                    <span className="truncate font-medium text-slate-300">{a.alert_type}</span>
                    <span className="shrink-0 text-[10px] text-slate-600">
                      {formatDistanceToNow(new Date(a.created_at), { addSuffix: true })}
                    </span>
                  </div>
                  <p className="mt-0.5 line-clamp-2 text-slate-500">{a.message}</p>
                  <p className="mt-0.5 text-[10px] text-slate-600">
                    {a.severity} · {a.agent_name}
                    {a.church_name ? ` · ${a.church_name}` : ""}
                  </p>
                </div>
              ))
            )}
          </CardContent>
        </Card>
      </div>

      <Card className="border-slate-800 bg-[#1a1d27]">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-semibold text-white">Slowest runs in window</CardTitle>
          <p className="text-xs text-slate-500">Sorted by duration_ms</p>
        </CardHeader>
        <CardContent className="overflow-x-auto p-0">
          {loadingLogs ? (
            <div className="p-4">
              <Skeleton className="h-32 w-full bg-slate-800" />
            </div>
          ) : slow.length === 0 ? (
            <p className="p-4 text-xs text-slate-500">No runs with non-zero duration in the loaded sample.</p>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-800 text-left text-xs uppercase tracking-wider text-slate-500">
                  <th className="px-4 py-2">Agent</th>
                  <th className="px-4 py-2">Action</th>
                  <th className="px-4 py-2">Church</th>
                  <th className="px-4 py-2">Duration</th>
                  <th className="px-4 py-2">When</th>
                </tr>
              </thead>
              <tbody>
                {slow.map((log) => (
                  <tr key={log.id} className="border-b border-slate-800/50 text-xs">
                    <td className="px-4 py-2 text-slate-300">{log.agent_name}</td>
                    <td className="max-w-[200px] truncate px-4 py-2 text-slate-400">{log.action}</td>
                    <td className="px-4 py-2 text-slate-500">{log.church_name ?? "—"}</td>
                    <td className="px-4 py-2 font-mono tabular-nums text-[#ffd166]">{log.duration_ms} ms</td>
                    <td className="px-4 py-2 text-slate-600">
                      {formatDistanceToNow(new Date(log.created_at), { addSuffix: true })}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

function MetricCard({ label, value, sub }: { label: string; value: string; sub: string }) {
  return (
    <div className="rounded-lg border border-slate-800 bg-[#1a1d27] p-4">
      <p className="text-[11px] font-medium uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-1 text-lg font-semibold tabular-nums text-white">{value}</p>
      <p className="mt-1 text-[11px] leading-snug text-slate-600">{sub}</p>
    </div>
  )
}
