import type { LucideIcon } from "lucide-react"

import { Badge } from "@/components/ui/badge"

interface PageHeaderProps {
  title: string
  description: string
  icon: LucideIcon
  color: string
  agentName: string
  lastRun?: string
}

export function PageHeader({
  title,
  description,
  icon: Icon,
  color,
  agentName,
  lastRun,
}: PageHeaderProps) {
  return (
    <div className="mb-6 flex items-start justify-between">
      <div className="flex items-center gap-4">
        <div
          className="flex size-11 items-center justify-center rounded-xl"
          style={{ background: `${color}22`, border: `1px solid ${color}44` }}
        >
          <Icon size={20} style={{ color }} />
        </div>
        <div>
          <h1 className="text-xl font-bold text-white">{title}</h1>
          <p className="mt-0.5 text-sm text-slate-400">{description}</p>
        </div>
      </div>
      <div className="flex items-center gap-2">
        <Badge variant="outline" className="border-slate-700 text-xs text-slate-400">
          {agentName}
        </Badge>
        {lastRun && <span className="text-xs text-slate-600">Last run: {lastRun}</span>}
      </div>
    </div>
  )
}
