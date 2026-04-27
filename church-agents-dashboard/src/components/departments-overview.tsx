import { AlertTriangle, Building2, CalendarClock, ClipboardList } from "lucide-react"

import { StatCard } from "@/components/stat-card"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"

export interface DepartmentActivityRow extends Record<string, unknown> {
  department_name?: unknown
  department_id?: unknown
}

interface Props {
  departmentsCount: number
  submittedCount: number
  stalledCount: number
  upcomingCount: number
  stallHours: number
  upcomingDays: number
  stalledPrograms: Record<string, unknown>[]
  submittedPrograms: Record<string, unknown>[]
  upcomingActivities: DepartmentActivityRow[]
}

function cellStr(v: unknown): string {
  if (v === null || v === undefined) return "—"
  if (typeof v === "string" || typeof v === "number") return String(v)
  return "—"
}

export function DepartmentsOverview({
  departmentsCount,
  submittedCount,
  stalledCount,
  upcomingCount,
  stallHours,
  upcomingDays,
  stalledPrograms,
  submittedPrograms,
  upcomingActivities,
}: Props) {
  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          title="Departments"
          value={departmentsCount}
          subtitle="In this church"
          icon={Building2}
          color="#4ecdc4"
        />
        <StatCard
          title="Programs awaiting approval"
          value={submittedCount}
          subtitle="Status SUBMITTED"
          icon={ClipboardList}
          color="#8892b0"
        />
        <StatCard
          title="Stalled programs"
          value={stalledCount}
          subtitle={`Submitted ≥ ${stallHours}h ago`}
          icon={AlertTriangle}
          color="#ffd166"
        />
        <StatCard
          title="Upcoming activities"
          value={upcomingCount}
          subtitle={`Next ${upcomingDays} days`}
          icon={CalendarClock}
          color="#6c63ff"
        />
      </div>

      <Card className="border-slate-800 bg-[#1a1d27]">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-semibold text-white">Stalled programs</CardTitle>
        </CardHeader>
        <CardContent>
          {stalledPrograms.length === 0 ? (
            <p className="text-xs text-slate-500">
              No submitted programs passed the stall threshold — or none are pending approval.
            </p>
          ) : (
            <div className="overflow-hidden rounded-lg border border-slate-800">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-slate-800 bg-[#151824] text-slate-500">
                    <th className="px-3 py-2 font-medium">Program</th>
                    <th className="px-3 py-2 font-medium">Submitted</th>
                    <th className="px-3 py-2 font-medium text-right">Hours pending</th>
                  </tr>
                </thead>
                <tbody className="text-slate-300">
                  {stalledPrograms.map((p, i) => (
                    <tr key={`${cellStr(p.id)}-${i}`} className="border-b border-slate-800/80 last:border-0">
                      <td className="px-3 py-2">{cellStr(p.name ?? p.title)}</td>
                      <td className="px-3 py-2 font-mono text-[11px]">
                        {cellStr(p.submitted_at ?? p.created_at)}
                      </td>
                      <td className="px-3 py-2 text-right tabular-nums text-amber-200/90">
                        {cellStr(p.hours_pending)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      <Card className="border-slate-800 bg-[#1a1d27]">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-semibold text-white">
            Upcoming department activities ({upcomingDays}-day window)
          </CardTitle>
        </CardHeader>
        <CardContent>
          {upcomingActivities.length === 0 ? (
            <p className="text-xs text-slate-500">
              No upcoming activities in this window, or none returned from the API for your departments.
            </p>
          ) : (
            <div className="overflow-hidden rounded-lg border border-slate-800">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-slate-800 bg-[#151824] text-slate-500">
                    <th className="px-3 py-2 font-medium">Activity</th>
                    <th className="px-3 py-2 font-medium">Department</th>
                    <th className="px-3 py-2 font-medium">Date</th>
                  </tr>
                </thead>
                <tbody className="text-slate-300">
                  {upcomingActivities.map((a, i) => (
                    <tr key={`${cellStr(a.id)}-${i}`} className="border-b border-slate-800/80 last:border-0">
                      <td className="px-3 py-2">{cellStr(a.title ?? a.name)}</td>
                      <td className="px-3 py-2">{cellStr(a.department_name)}</td>
                      <td className="px-3 py-2 font-mono text-[11px]">{cellStr(a.date ?? a.event_date)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      <details className="rounded-lg border border-slate-800 bg-[#0d1117]/60">
        <summary className="cursor-pointer px-4 py-3 text-xs font-medium text-slate-500 hover:text-slate-400">
          Developer: all SUBMITTED programs (reference)
        </summary>
        <pre className="max-h-[240px] overflow-auto border-t border-slate-800 p-4 text-[11px] text-slate-400">
          {JSON.stringify(submittedPrograms, null, 2)}
        </pre>
      </details>
    </div>
  )
}
