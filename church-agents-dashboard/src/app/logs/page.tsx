"use client"

import { Fragment, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { formatDistanceToNow } from "date-fns"
import { ChevronDown, ChevronRight, ScrollText } from "lucide-react"

import { PageHeader } from "@/components/page-header"
import { Card, CardContent } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { api } from "@/lib/api"
import type { AgentLog } from "@/lib/types"
import { cn } from "@/lib/utils"

const statusColor: Record<string, string> = {
  SUCCESS: "bg-[#00d4aa22] text-[#00d4aa] border border-[#00d4aa44]",
  FAILED: "bg-[#ff6b6b22] text-[#ff6b6b] border border-[#ff6b6b44]",
  SKIPPED: "bg-slate-700 text-slate-300",
}

export default function LogsPage() {
  const [expanded, setExpanded] = useState<string | null>(null)

  const { data, isLoading } = useQuery({
    queryKey: ["agent-logs-full"],
    queryFn: () => api.getAgentLogs({ page_size: "100" }),
    refetchInterval: 15_000,
  })

  const list = (data?.results ?? []) as AgentLog[]

  return (
    <div className="space-y-6">
      <PageHeader
        title="Agent Logs"
        description="Append-only runs from churchagents → Django AgentLog"
        icon={ScrollText}
        color="#8892b0"
        agentName="All agents"
      />

      <Card className="border-slate-800 bg-[#1a1d27]">
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-800">
                  <th className="w-8 px-3 py-3" />
                  {["Agent", "Action", "Church", "Status", "Trigger", "Duration", "When"].map((h) => (
                    <th
                      key={h}
                      className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-500"
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {isLoading &&
                  Array.from({ length: 8 }).map((_, i) => (
                    <tr key={i}>
                      <td colSpan={8} className="px-4 py-3">
                        <Skeleton className="h-6 bg-slate-800" />
                      </td>
                    </tr>
                  ))}
                {!isLoading &&
                  list.map((log) => (
                    <Fragment key={log.id}>
                      <tr
                        className="cursor-pointer border-b border-slate-800/50 hover:bg-[#21253a]"
                        onClick={() => setExpanded(expanded === log.id ? null : log.id)}
                      >
                        <td className="px-3 py-3 text-slate-600">
                          {expanded === log.id ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
                        </td>
                        <td className="px-4 py-3 text-xs font-medium text-white">
                          {log.agent_name.replace("Agent", "").replace(/([A-Z])/g, " $1").trim()}
                        </td>
                        <td className="max-w-[180px] truncate px-4 py-3 text-xs text-slate-400">
                          {log.action}
                        </td>
                        <td className="px-4 py-3 text-xs text-slate-500">{log.church_name ?? "—"}</td>
                        <td className="px-4 py-3">
                          <span
                            className={cn(
                              "rounded-full px-2 py-0.5 text-xs font-semibold",
                              statusColor[log.status] ?? "bg-slate-700 text-slate-300"
                            )}
                          >
                            {log.status}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-xs text-slate-500">{log.triggered_by}</td>
                        <td className="px-4 py-3 text-xs text-slate-500">{log.duration_ms}ms</td>
                        <td className="px-4 py-3 text-xs text-slate-500">
                          {formatDistanceToNow(new Date(log.created_at), { addSuffix: true })}
                        </td>
                      </tr>
                      {expanded === log.id && (
                        <tr className="bg-[#21253a]">
                          <td colSpan={8} className="px-6 py-4">
                            <div className="grid grid-cols-2 gap-4">
                              <div>
                                <p className="mb-1 text-xs font-semibold uppercase text-slate-500">Input</p>
                                <pre className="max-h-32 overflow-auto rounded-lg bg-[#0d1117] p-3 text-xs text-slate-400">
                                  {JSON.stringify(log.input_data ?? {}, null, 2)}
                                </pre>
                              </div>
                              <div>
                                <p className="mb-1 text-xs font-semibold uppercase text-slate-500">
                                  {log.status === "FAILED" ? "Error" : "Output"}
                                </p>
                                <pre
                                  className={cn(
                                    "max-h-32 overflow-auto rounded-lg bg-[#0d1117] p-3 text-xs",
                                    log.status === "FAILED" ? "text-[#ff6b6b]" : "text-slate-400"
                                  )}
                                >
                                  {log.status === "FAILED"
                                    ? log.error || ""
                                    : JSON.stringify(log.output_data ?? {}, null, 2)}
                                </pre>
                              </div>
                            </div>
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  ))}
              </tbody>
            </table>
          </div>
          {!isLoading && list.length === 0 && (
            <p className="p-8 text-center text-sm text-slate-500">No logs yet.</p>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
