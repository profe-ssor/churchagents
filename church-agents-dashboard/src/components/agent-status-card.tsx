import { formatDistanceToNow } from "date-fns"

import { Card, CardContent } from "@/components/ui/card"
import type { AgentSchedule } from "@/lib/types"
import { AI_NAME_SHORT } from "@/lib/branding"
import { cn } from "@/lib/utils"

const AGENT_COLORS: Record<string, string> = {
  OrchestratorAgent: "#6c63ff",
  SubscriptionWatchdogAgent: "#ff6b6b",
  TreasuryHealthAgent: "#00d4aa",
  MemberCareAgent: "#ffd166",
  DepartmentProgramAgent: "#4ecdc4",
  AnnouncementAgent: "#a8dadc",
  AuditSecurityAgent: "#f4a261",
  SecretariatAgent: "#e76f51",
}

export function AgentStatusCard({ schedule }: { schedule: AgentSchedule }) {
  const color = AGENT_COLORS[schedule.agent_name] || "#8892b0"
  const isOk = schedule.last_status === "SUCCESS" || !schedule.last_status
  const shortName =
    schedule.agent_name === "OrchestratorAgent"
      ? AI_NAME_SHORT
      : schedule.agent_name.replace("Agent", "").replace(/([A-Z])/g, " $1").trim()

  return (
    <Card className={cn("border-slate-800 bg-[#1a1d27]", !schedule.is_enabled && "opacity-50")}>
      <CardContent className="p-4">
        <div className="mb-3 flex items-center gap-2">
          <div
            className={cn("size-2 rounded-full", schedule.is_enabled ? "animate-pulse" : "")}
            style={{ background: schedule.is_enabled ? color : "#4b5563" }}
          />
          <p className="truncate text-xs font-semibold text-white">{shortName}</p>
        </div>
        <div className="space-y-1">
          <div className="flex justify-between text-xs">
            <span className="text-slate-500">Status</span>
            <span className={isOk ? "text-[#00d4aa]" : "text-[#ff6b6b]"}>
              {schedule.last_status || "Never run"}
            </span>
          </div>
          <div className="flex justify-between text-xs">
            <span className="text-slate-500">Last run</span>
            <span className="text-slate-400">
              {schedule.last_run
                ? formatDistanceToNow(new Date(schedule.last_run), { addSuffix: true })
                : "—"}
            </span>
          </div>
          <div className="flex justify-between text-xs">
            <span className="text-slate-500">Schedule</span>
            <span className="font-mono text-[10px] text-slate-400">{schedule.cron_expr}</span>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
