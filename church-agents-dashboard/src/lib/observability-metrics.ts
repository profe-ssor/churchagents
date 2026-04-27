import { format, startOfDay, subDays } from "date-fns"

import type { AgentLog } from "@/lib/types"

function numMs(v: unknown): number {
  const n = typeof v === "number" ? v : Number(v)
  return Number.isFinite(n) && n >= 0 ? n : 0
}

function percentile(sorted: number[], p: number): number {
  if (sorted.length === 0) return 0
  const i = Math.min(sorted.length - 1, Math.max(0, Math.ceil((p / 100) * sorted.length) - 1))
  return sorted[i]
}

export interface LatencySummary {
  totalRuns: number
  /** Rows where duration_ms parses to a value &gt; 0 (used for avg / p95 charts). */
  runsWithDuration: number
  /** Rows where duration is 0 or missing — typical for logs written before the API stored timing. */
  runsWithoutTiming: number
  avgMs: number
  medianMs: number
  p95Ms: number
  maxMs: number
}

export function summarizeLatency(logs: AgentLog[]): LatencySummary {
  const all = logs.map((l) => numMs(l.duration_ms))
  const sorted = all.filter((d) => d > 0).sort((a, b) => a - b)
  const sum = sorted.reduce((a, b) => a + b, 0)
  const timed = sorted.length
  return {
    totalRuns: logs.length,
    runsWithDuration: timed,
    runsWithoutTiming: logs.length - timed,
    avgMs: timed ? Math.round(sum / timed) : 0,
    medianMs: timed ? percentile(sorted, 50) : 0,
    p95Ms: timed ? percentile(sorted, 95) : 0,
    maxMs: timed ? sorted[sorted.length - 1] : 0,
  }
}

export interface DayLatencyRow {
  day: string
  dateLabel: string
  count: number
  avgMs: number
  medianMs: number
}

/** Last `days` calendar days (including today); days with no logs show avg 0, count 0. */
export function latencyTrendByDay(logs: AgentLog[], days: number = 14): DayLatencyRow[] {
  const end = startOfDay(new Date())
  const keys: string[] = []
  for (let i = days - 1; i >= 0; i--) {
    keys.push(format(subDays(end, i), "yyyy-MM-dd"))
  }
  const byDay = new Map<string, number[]>()
  for (const k of keys) byDay.set(k, [])
  for (const log of logs) {
    const d = new Date(log.created_at)
    if (Number.isNaN(d.getTime())) continue
    const k = format(d, "yyyy-MM-dd")
    if (!byDay.has(k)) continue
    const ms = numMs(log.duration_ms)
    if (ms > 0) byDay.get(k)!.push(ms)
  }
  return keys.map((day) => {
    const arr = (byDay.get(day) ?? []).sort((a, b) => a - b)
    const sum = arr.reduce((a, b) => a + b, 0)
    return {
      day,
      dateLabel: format(new Date(day + "T12:00:00"), "MMM d"),
      count: arr.length,
      avgMs: arr.length ? Math.round(sum / arr.length) : 0,
      medianMs: arr.length ? percentile(arr, 50) : 0,
    }
  })
}

export interface AgentLatencyRow {
  agent: string
  runs: number
  avgMs: number
  medianMs: number
}

export function avgLatencyByAgent(logs: AgentLog[], minRuns = 1): AgentLatencyRow[] {
  const map = new Map<string, number[]>()
  for (const log of logs) {
    const ms = numMs(log.duration_ms)
    if (ms <= 0) continue
    const name = (log.agent_name || "unknown").replace(/Agent$/, "").trim() || log.agent_name
    if (!map.has(name)) map.set(name, [])
    map.get(name)!.push(ms)
  }
  const rows: AgentLatencyRow[] = []
  for (const [agent, arr] of map) {
    if (arr.length < minRuns) continue
    const sorted = [...arr].sort((a, b) => a - b)
    const sum = sorted.reduce((a, b) => a + b, 0)
    rows.push({
      agent,
      runs: sorted.length,
      avgMs: Math.round(sum / sorted.length),
      medianMs: percentile(sorted, 50),
    })
  }
  return rows.sort((a, b) => b.avgMs - a.avgMs)
}

export function statusCounts(logs: AgentLog[]): Record<string, number> {
  const out: Record<string, number> = {}
  for (const log of logs) {
    const s = log.status || "UNKNOWN"
    out[s] = (out[s] ?? 0) + 1
  }
  return out
}

export function triggerCounts(logs: AgentLog[]): Record<string, number> {
  const out: Record<string, number> = {}
  for (const log of logs) {
    const t = log.triggered_by || "UNKNOWN"
    out[t] = (out[t] ?? 0) + 1
  }
  return out
}

export function slowestRuns(logs: AgentLog[], limit = 12): AgentLog[] {
  return [...logs]
    .filter((l) => numMs(l.duration_ms) > 0)
    .sort((a, b) => numMs(b.duration_ms) - numMs(a.duration_ms))
    .slice(0, limit)
}
