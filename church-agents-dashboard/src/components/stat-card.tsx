import type { LucideIcon } from "lucide-react"

import { Card, CardContent } from "@/components/ui/card"
import { cn } from "@/lib/utils"

interface StatCardProps {
  title: string
  value: string | number
  subtitle?: string
  icon: LucideIcon
  color: string
  trend?: { value: number; label: string }
}

export function StatCard({ title, value, subtitle, icon: Icon, color, trend }: StatCardProps) {
  return (
    <Card className="border-slate-800 bg-[#1a1d27]">
      <CardContent className="p-5">
        <div className="flex items-start justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">{title}</p>
            <p className="mt-1 text-2xl font-bold text-white">{value}</p>
            {subtitle && <p className="mt-1 text-xs text-slate-500">{subtitle}</p>}
            {trend && (
              <p
                className={cn(
                  "mt-2 text-xs font-medium",
                  trend.value >= 0 ? "text-[#00d4aa]" : "text-[#ff6b6b]"
                )}
              >
                {trend.value >= 0 ? "↑" : "↓"} {Math.abs(trend.value)}% {trend.label}
              </p>
            )}
          </div>
          <div
            className="flex size-10 shrink-0 items-center justify-center rounded-xl"
            style={{ background: `${color}22` }}
          >
            <Icon size={18} style={{ color }} />
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
