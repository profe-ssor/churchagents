import type { AgentLog } from "@/lib/types"

/** YYYY-MM-DD in local timezone */
function localDateKey(d: Date): string {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, "0")
  const day = String(d.getDate()).padStart(2, "0")
  return `${y}-${m}-${day}`
}

/** Last 7 calendar days ending today (local), oldest first */
export function last7LocalDayKeys(): string[] {
  const keys: string[] = []
  for (let i = 6; i >= 0; i--) {
    const d = new Date()
    d.setHours(0, 0, 0, 0)
    d.setDate(d.getDate() - i)
    keys.push(localDateKey(d))
  }
  return keys
}

/** Count agent logs per day for the given date keys (must be contiguous window). */
export function countAgentLogsByDay(logs: AgentLog[], dayKeys: string[]): number[] {
  const counts: Record<string, number> = Object.fromEntries(dayKeys.map((k) => [k, 0]))
  for (const log of logs) {
    const d = new Date(log.created_at)
    const k = localDateKey(d)
    if (k in counts) counts[k]++
  }
  return dayKeys.map((k) => counts[k] ?? 0)
}

export type ChartPoint = { day: string; actions: number; dateLabel: string }

/** Build Recharts rows: short weekday + optional date for tooltip */
export function buildAgentActionsChartData(logs: AgentLog[]): ChartPoint[] {
  const dayKeys = last7LocalDayKeys()
  const totals = countAgentLogsByDay(logs, dayKeys)
  return dayKeys.map((_, i) => {
    const d = new Date()
    d.setHours(0, 0, 0, 0)
    d.setDate(d.getDate() - (6 - i))
    const weekday = d.toLocaleDateString(undefined, { weekday: "short" })
    const dateLabel = d.toLocaleDateString(undefined, {
      month: "short",
      day: "numeric",
    })
    return {
      day: weekday,
      actions: totals[i] ?? 0,
      dateLabel,
    }
  })
}
