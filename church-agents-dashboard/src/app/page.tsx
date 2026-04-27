"use client"

import { useMemo } from "react"
import { useQuery } from "@tanstack/react-query"
import { formatDistanceToNow } from "date-fns"
import { AlertTriangle, Church as ChurchIcon, CreditCard, LayoutDashboard, XCircle } from "lucide-react"
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"

import { AgentStatusCard } from "@/components/agent-status-card"
import { StatCard } from "@/components/stat-card"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { api } from "@/lib/api"
import { buildAgentActionsChartData } from "@/lib/agent-log-chart"
import type { AgentLog, Church } from "@/lib/types"

export default function DashboardPage() {
  const { data: churchesData, isLoading: loadingChurches } = useQuery({
    queryKey: ["churches"],
    queryFn: () => api.getChurches({ page_size: "500" }),
  })

  const { data: logsData, isLoading: loadingLogs } = useQuery({
    queryKey: ["agent-logs"],
    queryFn: () => api.getAgentLogs({ page_size: "500" }),
    refetchInterval: 30_000,
  })

  const { data: schedulesData, isLoading: loadingSchedules } = useQuery({
    queryKey: ["agent-schedules"],
    queryFn: () => api.getAgentSchedules(),
  })

  const churchList: Church[] = churchesData?.results ?? []
  const logList = (logsData?.results ?? []) as AgentLog[]
  const scheduleList = schedulesData?.results ?? []

  const chartData = useMemo(() => buildAgentActionsChartData(logList), [logList])

  const now = Date.now()
  const stats = {
    total: churchList.length,
    active: churchList.filter((c) => c.subscription_status === "ACTIVE" || c.status === "ACTIVE")
      .length,
    expiring: churchList.filter((c) => {
      if (!c.subscription_ends_at) return false
      const days = (new Date(c.subscription_ends_at).getTime() - now) / 86400000
      return days <= 7 && days >= 0
    }).length,
    suspended: churchList.filter((c) => c.platform_access_enabled === false).length,
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <div className="flex size-10 items-center justify-center rounded-xl border border-[#6c63ff44] bg-[#6c63ff22]">
          <LayoutDashboard size={18} className="text-[#6c63ff]" />
        </div>
        <div>
          <h1 className="text-xl font-bold text-white">Dashboard</h1>
          <p className="text-sm text-slate-400">Platform overview — all agents</p>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {loadingChurches ? (
          Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-24 bg-slate-800" />)
        ) : (
          <>
            <StatCard title="Total Churches" value={stats.total} icon={ChurchIcon} color="#6c63ff" />
            <StatCard title="Active Subscriptions" value={stats.active} icon={CreditCard} color="#00d4aa" />
            <StatCard title="Expiring This Week" value={stats.expiring} icon={AlertTriangle} color="#ffd166" />
            <StatCard title="Suspended" value={stats.suspended} icon={XCircle} color="#ff6b6b" />
          </>
        )}
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <Card className="border-slate-800 bg-[#1a1d27] lg:col-span-2">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-semibold text-white">
              Agent Actions — Last 7 Days
            </CardTitle>
          </CardHeader>
          <CardContent>
            {loadingLogs ? (
              <Skeleton className="h-[200px] w-full bg-slate-800" />
            ) : (
              <ResponsiveContainer width="100%" height={200}>
                <LineChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#2e3250" />
                  <XAxis dataKey="day" tick={{ fill: "#8892b0", fontSize: 11 }} />
                  <YAxis allowDecimals={false} tick={{ fill: "#8892b0", fontSize: 11 }} />
                  <Tooltip
                    content={({ active, payload }) => {
                      if (!active || !payload?.length) return null
                      const row = payload[0]?.payload as { dateLabel?: string; actions?: number }
                      return (
                        <div
                          className="rounded-lg border border-[#2e3250] bg-[#21253a] px-3 py-2 text-xs shadow-lg"
                          style={{ color: "#fff" }}
                        >
                          <div className="mb-1 text-[11px] text-slate-400">{row.dateLabel}</div>
                          <div className="font-medium tabular-nums">{row.actions ?? 0} actions</div>
                        </div>
                      )
                    }}
                  />
                  <Line type="monotone" dataKey="actions" stroke="#6c63ff" strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>

        <Card className="border-slate-800 bg-[#1a1d27]">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-semibold text-white">Recent Activity</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {loadingLogs
              ? Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-8 bg-slate-800" />)
              : logList.slice(0, 6).map((log) => (
                  <div key={log.id} className="flex items-center gap-2 py-1">
                    <div
                      className={`size-1.5 shrink-0 rounded-full ${
                        log.status === "SUCCESS"
                          ? "bg-[#00d4aa]"
                          : log.status === "FAILED"
                            ? "bg-[#ff6b6b]"
                            : "bg-[#8892b0]"
                      }`}
                    />
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-xs text-slate-300">
                        {log.agent_name.replace("Agent", "")}
                      </p>
                      <p className="truncate text-[10px] text-slate-600">{log.action}</p>
                    </div>
                    <span className="shrink-0 text-[10px] text-slate-600">
                      {formatDistanceToNow(new Date(log.created_at), { addSuffix: true })}
                    </span>
                  </div>
                ))}
            {!loadingLogs && logList.length === 0 && (
              <p className="text-xs text-slate-500">No agent logs yet. Run an agent from churchagents.</p>
            )}
          </CardContent>
        </Card>
      </div>

      <div>
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-slate-400">
          Agent Status
        </h2>
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          {loadingSchedules
            ? Array.from({ length: 8 }).map((_, i) => <Skeleton key={i} className="h-28 bg-slate-800" />)
            : scheduleList.map((s) => <AgentStatusCard key={String(s.id)} schedule={s} />)}
        </div>
      </div>
    </div>
  )
}
