"use client"

import { useQuery } from "@tanstack/react-query"
import { Building2 } from "lucide-react"

import { AgentInfoPanel } from "@/components/agent-info-panel"
import { AgentTaskFlow } from "@/components/agent-task-flow"
import {
  DepartmentsOverview,
  type DepartmentActivityRow,
} from "@/components/departments-overview"
import { PageHeader } from "@/components/page-header"
import { Card, CardContent } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { useDashboardChurchScope } from "@/hooks/use-dashboard-church-scope"
import { api } from "@/lib/api"

/** Align with `PROGRAM_STALL_HOURS` in churchagents / agent logic (default 72). */
const STALL_HOURS = 72
const UPCOMING_DAYS = 7

const DEPARTMENT_AGENT_BULLETS = [
  "Loads programs still in SUBMITTED status and flags those pending longer than the stall threshold as stalled.",
  "Creates WARNING alerts for each stalled program (with hours pending).",
  "Walks each department’s upcoming activities and creates INFO alerts for items in the next few days.",
  "Writes a summary to Agent Logs after each scheduled run.",
  "Orchestrator (admin chat) can also call department tools: upcoming activities, pending approvals, budget pressure, members, program detail/history, activity detail, and gated emails to the department head or activity reminders.",
] as const

const DEPARTMENT_TASK_STEPS = [
  {
    title: "Scheduled run",
    description:
      "Celery Beat runs DepartmentProgramAgent on a fixed interval (see churchagents scheduler) for all active churches or your deployment’s policy.",
  },
  {
    title: "Load programs & activities",
    description:
      "Fetches programs and each department’s activities, then applies the same stall and “upcoming” windows the code uses for alerts.",
  },
  {
    title: "Classify work",
    description:
      "Stalled programs (long-pending approval) get WARNING-style attention; soon activities get reminder-style signals in the agent pipeline.",
  },
  {
    title: "Act & log",
    description:
      "Raises AgentAlert rows, may email or notify per your rules, and writes an AgentLog summary so dashboards can show what happened.",
  },
] as const

function hoursPending(iso: string | undefined): number | null {
  if (!iso) return null
  const t = Date.parse(iso)
  if (Number.isNaN(t)) return null
  return Math.floor((Date.now() - t) / 3600000)
}

async function loadDepartmentsOverview(churchId: string) {
  const [deptData, progData] = await Promise.all([
    api.getDepartments({ church_id: churchId, page_size: "200" }),
    api.getPrograms({ church_id: churchId, page_size: "200" }),
  ])

  const departments = (deptData.results ?? []) as Record<string, unknown>[]
  const programs = (progData.results ?? []) as Record<string, unknown>[]

  const submitted = programs.filter(
    (p) => String(p.status ?? "").toUpperCase() === "SUBMITTED"
  )

  const stalledPrograms = submitted
    .map((p) => {
      const iso = String(p.submitted_at ?? p.created_at ?? "")
      const h = hoursPending(iso)
      return { ...p, hours_pending: h }
    })
    .filter(
      (p) =>
        typeof p.hours_pending === "number" && p.hours_pending >= STALL_HOURS
    ) as Record<string, unknown>[]

  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const horizon = new Date(today.getTime() + UPCOMING_DAYS * 86400000)

  const upcomingActivities: DepartmentActivityRow[] = []

  await Promise.all(
    departments.map(async (d) => {
      const id = String(d.id ?? "")
      if (!id) return
      try {
        const acts = await api.getDepartmentActivities(id, { time_filter: "upcoming" })
        const rows = (acts.results ?? []) as Record<string, unknown>[]
        for (const a of rows) {
          const raw = String(a.date ?? a.event_date ?? "")
          const day = raw.slice(0, 10)
          if (!day) continue
          const dt = new Date(day + "T12:00:00")
          if (Number.isNaN(dt.getTime())) continue
          if (dt >= today && dt <= horizon) {
            upcomingActivities.push({
              ...a,
              department_name: d.name,
              department_id: id,
            })
          }
        }
      } catch {
        /* dept may have no activities route permission */
      }
    })
  )

  upcomingActivities.sort((a, b) =>
    String(a.date ?? a.event_date ?? "").localeCompare(String(b.date ?? b.event_date ?? ""))
  )

  return {
    departmentsCount: departments.length,
    submittedCount: submitted.length,
    stalledCount: stalledPrograms.length,
    upcomingCount: upcomingActivities.length,
    stalledPrograms,
    submittedPrograms: submitted,
    upcomingActivities,
    stallHours: STALL_HOURS,
    upcomingDays: UPCOMING_DAYS,
  }
}

export default function DepartmentsPage() {
  const {
    sessionInfo,
    churches,
    scopeChurchId,
    setScopeChurchId,
    effectiveChurchId,
    waitingPlatformScope,
    needsChurch,
    showScopePicker,
    bootLoading,
    sessionReady,
    churchesReady,
  } = useDashboardChurchScope("churchagents_departments_church_scope")

  const overview = useQuery({
    queryKey: ["departments-overview", effectiveChurchId ?? "none"],
    queryFn: () => loadDepartmentsOverview(effectiveChurchId!),
    enabled:
      Boolean(sessionReady && churchesReady && effectiveChurchId && sessionInfo?.authenticated),
  })

  return (
    <div className="space-y-6">
      <PageHeader
        title="Departments"
        description="DepartmentProgramAgent + this view share the same program/activity data: the table below mirrors what the job inspects; the task flow shows the agent’s loop end to end."
        icon={Building2}
        color="#4ecdc4"
        agentName="DepartmentProgramAgent"
      />

      <AgentTaskFlow accent="#4ecdc4" steps={DEPARTMENT_TASK_STEPS} />

      <AgentInfoPanel
        agentName="DepartmentProgramAgent"
        schedule="Typical schedule (Celery Beat): every 12 hours — see churchagents `scheduler/celery_app.py`. The agent uses a ~3-day window for activity reminders; this page shows a 7-day upcoming list."
        bullets={DEPARTMENT_AGENT_BULLETS}
        accent="#4ecdc4"
        defaultOpen
        footerNote="The overview table is client-computed from the same APIs the agent uses. Orchestrator “department tools” in chat are separate interactive calls, not the beat job."
      />

      {showScopePicker && (
        <div className="flex max-w-xl flex-col gap-1.5 rounded-lg border border-slate-800 bg-[#1a1d27] p-4">
          <label htmlFor="departments-church-scope" className="text-xs font-medium text-slate-400">
            Which church should these lists use?
          </label>
          <select
            id="departments-church-scope"
            value={scopeChurchId}
            onChange={(e) => setScopeChurchId(e.target.value)}
            className="rounded-lg border border-slate-700 bg-[#21253a] px-3 py-2 text-sm text-white outline-none focus:border-[#4ecdc4]"
          >
            <option value="">Select a church…</option>
            {churches.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
          <p className="text-[11px] leading-snug text-slate-500">
            Departments and programs are filtered by <code className="text-slate-400">church_id</code>. Remembered on
            this device.
          </p>
        </div>
      )}

      <Card className="border-slate-800 bg-[#1a1d27]">
        <CardContent className="p-6">
          {bootLoading && <Skeleton className="min-h-[200px] bg-slate-800" />}
          {!bootLoading && waitingPlatformScope && (
            <p className="text-sm text-slate-400">Choose a church to load departments and programs.</p>
          )}
          {!bootLoading && needsChurch && (
            <p className="text-sm text-amber-200/90">
              No church on this account. Ensure `/api/auth/churches/` returns your congregation or sign in as a platform
              admin and pick a church.
            </p>
          )}
          {!bootLoading && !waitingPlatformScope && overview.isLoading && Boolean(effectiveChurchId) && (
            <Skeleton className="min-h-[240px] bg-slate-800" />
          )}
          {!bootLoading && !waitingPlatformScope && overview.error && (
            <p className="text-sm text-slate-400">
              Could not load departments data. Confirm your user can access{" "}
              <code className="text-slate-300">/api/departments/</code>,{" "}
              <code className="text-slate-300">/api/programs/</code>, and department activities.
            </p>
          )}
          {!bootLoading &&
            !waitingPlatformScope &&
            !overview.isLoading &&
            !overview.error &&
            !needsChurch &&
            effectiveChurchId &&
            overview.data && <DepartmentsOverview {...overview.data} />}
        </CardContent>
      </Card>
    </div>
  )
}
