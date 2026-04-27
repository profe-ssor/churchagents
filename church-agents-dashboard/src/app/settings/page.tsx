"use client"

import { useQuery } from "@tanstack/react-query"
import { Settings } from "lucide-react"

import { AgentStatusCard } from "@/components/agent-status-card"
import { PageHeader } from "@/components/page-header"
import { Card, CardContent } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { Switch } from "@/components/ui/switch"
import { api } from "@/lib/api"
import type { AgentSchedule } from "@/lib/types"

export default function SettingsPage() {
  const { data, isLoading } = useQuery({
    queryKey: ["agent-schedules"],
    queryFn: () => api.getAgentSchedules(),
  })

  const list: AgentSchedule[] = data?.results ?? []

  return (
    <div className="space-y-6">
      <PageHeader
        title="Agent Settings"
        description="Schedules are informational until Celery beat endpoints are exposed"
        icon={Settings}
        color="#8892b0"
        agentName="Configuration"
      />

      <Card className="border-slate-800 bg-[#1a1d27]">
        <CardContent className="flex items-start gap-3 p-4 text-sm text-slate-400">
          <Switch checked disabled className="mt-0.5" />
          <p>
            Toggling agents from the UI requires backend routes (e.g. <code className="text-slate-300">/api/agents/schedules/</code>).
            Today you can enable/disable workloads via Celery beat and run jobs with{" "}
            <code className="text-slate-300">python main.py &lt;agent&gt;</code>.
          </p>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
        {isLoading
          ? Array.from({ length: 8 }).map((_, i) => <Skeleton key={i} className="h-52 bg-slate-800" />)
          : list.map((s) => <AgentStatusCard key={String(s.id)} schedule={s} />)}
      </div>
    </div>
  )
}
