"use client"

import Link from "next/link"
import { useQuery } from "@tanstack/react-query"
import { formatDistanceToNow } from "date-fns"
import { ArrowRight, FileText } from "lucide-react"

import { AgentInfoPanel } from "@/components/agent-info-panel"
import { AgentTaskFlow } from "@/components/agent-task-flow"
import { PageHeader } from "@/components/page-header"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { useDashboardChurchScope } from "@/hooks/use-dashboard-church-scope"
import { api } from "@/lib/api"
import type { AgentAlert, AgentLog } from "@/lib/types"
import { cn } from "@/lib/utils"

const ACCENT = "#e76f51"
const AGENT_NAME = "SecretariatAgent"

const SECRETARIAT_AGENT_BULLETS = [
  "Designed to integrate with Django models: MeetingMinutes, DocumentRequest, BaptismRecord, MarriageRecord, TransferLetter, CorrespondenceLog — the bundled `secretariat/` app may still be an empty scaffold until migrations land.",
  "Scheduled job (churchagents Celery): daily at 07:00 — polls pending document requests via MCP `secretariat.get_document_requests` / GET …/document-requests/ when routed.",
  "Creates INFO alerts (PENDING_DOCUMENT) per outstanding request once APIs exist.",
  "On-demand MCP flows: transfer letters (`create_transfer_letter`), meeting minutes (`create_meeting_minutes`), orchestrator prompts for certificates and correspondence.",
  "Emails / PDF generation depend on Django templates, storage (e.g. uploads), and notifications — configure before production sends.",
  "Orchestrator `handoff_to_agent` can target secretary / secretariat once tools are wired.",
] as const

const SECRETARIAT_TASK_STEPS = [
  {
    title: "Scheduled pulse",
    description:
      "Celery Beat runs SecretariatAgent daily at 07:00 (`scheduler/celery_app.py`) — pending document-request sweep when endpoints exist.",
  },
  {
    title: "Observe inbox",
    description:
      "Calls GET /api/secretariat/document-requests/ (planned) — same queue this dashboard will list once serializers ship.",
  },
  {
    title: "Classify & alert",
    description:
      "Raises AgentAlert rows for stalls and routes escalations to the human secretary via notifications.",
  },
  {
    title: "Generate & archive",
    description:
      "Transfer letters, certificates, minutes PDFs — stored under church-controlled paths with audit logging.",
  },
] as const

const TOOL_ROWS: { tool: string; purpose: string }[] = [
  { tool: "get_member_record(member_id)", purpose: "Full profile for document generation" },
  { tool: "generate_transfer_letter(member_id, dest_church)", purpose: "Official PDF transfer letter" },
  { tool: "generate_membership_certificate(member_id)", purpose: "Membership certificate PDF" },
  { tool: "generate_recommendation_letter(member_id, purpose)", purpose: "Formal recommendation letter" },
  { tool: "log_meeting_minutes(type, date, summary, decisions)", purpose: "Record board meeting minutes" },
  { tool: "get_meeting_minutes(date_range, meeting_type)", purpose: "Retrieve historical minutes" },
  { tool: "log_baptism_record(member_id, date, officiant)", purpose: "Sacrament record" },
  { tool: "log_marriage_record(member_ids, date, officiant)", purpose: "Marriage record" },
  { tool: "get_pending_document_requests()", purpose: "Outstanding document requests" },
  { tool: "send_document_by_email(member_id, doc_type)", purpose: "Deliver document via email" },
  { tool: "notify_secretary(message)", purpose: "Escalate to human secretary" },
]

const TRIGGER_ROWS: { label: string; tag: string; detail: string }[] = [
  {
    tag: "ON-DEMAND",
    label: "Generate transfer letter",
    detail: 'Natural-language or admin UI: "Generate a transfer letter for [Member Name]" — MCP → POST transfer-letters.',
  },
  {
    tag: "EVENT",
    label: "Member → TRANSFER",
    detail: "Lifecycle transition can auto-queue transfer letter generation when workflows connect member status to secretariat.",
  },
  {
    tag: "SCHEDULED",
    label: "Weekly pending sweep",
    detail: "Daily (07:00) today; align with weekly digest copy in product spec when digest tasks are added.",
  },
  {
    tag: "ON-DEMAND",
    label: "Minutes lookup",
    detail: '"Show me the minutes from the last elder meeting" — retrieve meeting-minutes API + RAG/church KB when indexed.',
  },
  {
    tag: "ON-DEMAND",
    label: "Sacrament logging",
    detail: '"Log baptism record for [Member] on [Date]" — POST sacrament endpoints once models exist.',
  },
]

const DOCUMENT_KINDS: { tag: string; title: string; detail: string }[] = [
  { tag: "TRANSFER", title: "Transfer letter", detail: "Member moving to another church" },
  { tag: "CERT", title: "Membership certificate", detail: "Proof of membership" },
  { tag: "RECOM", title: "Recommendation letter", detail: "Employment, school, travel" },
  { tag: "BAPTISM", title: "Baptism certificate", detail: "Sacrament record" },
  { tag: "MINUTES", title: "Meeting minutes PDF", detail: "Official board records" },
  { tag: "REPORT", title: "Membership report", detail: "Denominational / statistical returns" },
]

function tagTone(tag: string): string {
  switch (tag) {
    case "ON-DEMAND":
      return "border-amber-500/40 bg-amber-500/15 text-amber-200"
    case "EVENT":
      return "border-emerald-500/40 bg-emerald-500/15 text-emerald-300"
    case "SCHEDULED":
      return "border-sky-500/40 bg-sky-500/15 text-sky-300"
    default:
      return "border-slate-600 bg-slate-800 text-slate-400"
  }
}

function kindTone(tag: string): string {
  switch (tag) {
    case "TRANSFER":
      return "border-orange-400/50 bg-orange-500/15 text-orange-200"
    case "CERT":
      return "border-teal-400/50 bg-teal-500/15 text-teal-200"
    case "RECOM":
      return "border-indigo-400/50 bg-indigo-500/15 text-indigo-200"
    case "BAPTISM":
      return "border-cyan-400/50 bg-cyan-500/15 text-cyan-200"
    case "MINUTES":
      return "border-violet-400/50 bg-violet-500/15 text-violet-200"
    case "REPORT":
      return "border-lime-400/50 bg-lime-500/15 text-lime-200"
    default:
      return "border-slate-600 bg-slate-800 text-slate-400"
  }
}

function scopeFiltersSecretariatRow(
  row: { agent_name: string; church_id?: string | null },
  churchId: string
): boolean {
  if (row.agent_name !== AGENT_NAME) return false
  if (!churchId) return false
  return row.church_id === churchId || row.church_id === null
}

export default function SecretariatPage() {
  const {
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
    sessionInfo,
  } = useDashboardChurchScope("churchagents_secretariat_church_scope")

  const scopeReady = Boolean(
    sessionReady && churchesReady && effectiveChurchId && sessionInfo?.authenticated
  )

  const {
    data: docReqData,
    isLoading: docLoading,
    error: docError,
    isError: docIsError,
  } = useQuery({
    queryKey: ["secretariat", "document-requests", effectiveChurchId ?? "none"],
    queryFn: () => api.getSecretariatDocumentRequests({ page_size: "50" }),
    enabled: scopeReady,
    retry: false,
  })

  const {
    data: minutesData,
    isLoading: minutesLoading,
    error: minutesError,
    isError: minutesIsError,
  } = useQuery({
    queryKey: ["secretariat", "minutes", effectiveChurchId ?? "none"],
    queryFn: () => api.getSecretariatMeetingMinutes({ page_size: "50" }),
    enabled: scopeReady,
    retry: false,
  })

  const { data: alertsData, isLoading: alertsLoading } = useQuery({
    queryKey: ["secretariat-agent-alerts", effectiveChurchId ?? "none"],
    queryFn: () => api.getAgentAlerts({ page_size: "200" }),
    enabled: scopeReady,
    refetchInterval: 60_000,
  })

  const { data: logsData, isLoading: logsLoading } = useQuery({
    queryKey: ["secretariat-agent-logs", effectiveChurchId ?? "none"],
    queryFn: () => api.getAgentLogs({ page_size: "80" }),
    enabled: scopeReady,
    refetchInterval: 60_000,
  })

  const alertList = (alertsData?.results ?? []) as AgentAlert[]
  const logList = (logsData?.results ?? []) as AgentLog[]

  const alertsForChurch = effectiveChurchId
    ? alertList.filter((a) => scopeFiltersSecretariatRow(a, effectiveChurchId))
    : []

  const selectedChurchName = churches.find((c) => c.id === effectiveChurchId)?.name

  const logsForChurch = effectiveChurchId
    ? logList.filter((log) => {
        if (log.agent_name !== AGENT_NAME) return false
        const cid = log.church_id ?? null
        if (cid === effectiveChurchId) return true
        if (selectedChurchName && log.church_name === selectedChurchName) return true
        return false
      })
    : []

  const logsSorted = [...logsForChurch].sort(
    (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
  )
  const latestRun = logsSorted[0]
  const lastRunLabel = latestRun
    ? formatDistanceToNow(new Date(latestRun.created_at), { addSuffix: true })
    : undefined

  const recentAlerts = [...alertsForChurch]
    .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
    .slice(0, 12)

  const monitorLoading = alertsLoading || logsLoading
  const apiLoading = docLoading || minutesLoading

  const backendLikelyMissing = docIsError || minutesIsError

  const docRows = Array.isArray((docReqData as { results?: unknown })?.results)
    ? ((docReqData as { results: unknown[] }).results ?? [])
    : Array.isArray(docReqData)
      ? (docReqData as unknown[])
      : []

  const minutesRows = Array.isArray((minutesData as { results?: unknown })?.results)
    ? ((minutesData as { results: unknown[] }).results ?? [])
    : Array.isArray(minutesData)
      ? (minutesData as unknown[])
      : []

  const severityClass: Record<string, string> = {
    CRITICAL: "border-[#ff6b6b44] bg-[#ff6b6b22] text-[#ff6b6b]",
    WARNING: "border-[#ffd16644] bg-[#ffd16622] text-[#ffd166]",
    INFO: "border-sky-500/40 bg-sky-500/15 text-sky-300",
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="📜 Secretariat"
        description={`${AGENT_NAME} · Official records, documents & correspondence — transfer letters, certificates, minutes, sacramental logs, and pending-request hygiene (APIs gated on Django).`}
        icon={FileText}
        color={ACCENT}
        agentName={AGENT_NAME}
        lastRun={lastRunLabel}
      />

      <div className="flex flex-wrap items-center gap-2">
        <Badge variant="outline" className="border-[#e76f5155] text-[11px] text-[#e76f51]">
          AGENT 8
        </Badge>
        <Badge variant="outline" className="border-slate-600 text-[11px] text-slate-400">
          MCP tools → /api/secretariat/* once routes & models ship
        </Badge>
      </div>

      <AgentTaskFlow accent={ACCENT} steps={SECRETARIAT_TASK_STEPS} />

      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="border-slate-800 bg-[#1a1d27]">
          <CardContent className="p-5">
            <h2 className="text-sm font-semibold text-white">Tools</h2>
            <p className="mt-1 text-[11px] text-slate-500">
              Target MCP / orchestrator surface — backend ViewSets must exist for writes.
            </p>
            <div className="mt-3 max-h-[340px] overflow-y-auto rounded-lg border border-slate-800">
              <table className="w-full text-left text-[11px]">
                <thead className="sticky top-0 border-b border-slate-800 bg-[#151824] text-slate-500">
                  <tr>
                    <th className="px-2 py-2 font-medium">Function</th>
                    <th className="px-2 py-2 font-medium">Role</th>
                  </tr>
                </thead>
                <tbody>
                  {TOOL_ROWS.map((row) => (
                    <tr key={row.tool} className="border-b border-slate-800/60 last:border-0">
                      <td className="px-2 py-2 font-mono text-[10px] text-[#e76f51]/95">{row.tool}</td>
                      <td className="px-2 py-2 text-slate-400">{row.purpose}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>

        <Card className="border-slate-800 bg-[#1a1d27]">
          <CardContent className="p-5">
            <h2 className="text-sm font-semibold text-white">Triggers</h2>
            <ul className="mt-3 space-y-3">
              {TRIGGER_ROWS.map((t) => (
                <li key={t.label} className="rounded-lg border border-slate-800 bg-[#151824] px-3 py-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge variant="outline" className={cn("text-[10px]", tagTone(t.tag))}>
                      {t.tag}
                    </Badge>
                    <span className="text-xs font-medium text-white">{t.label}</span>
                  </div>
                  <p className="mt-1 text-[11px] leading-snug text-slate-400">{t.detail}</p>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      </div>

      <Card className="border-slate-800 bg-[#1a1d27]">
        <CardContent className="p-5">
          <h2 className="text-sm font-semibold text-white">Documents generated</h2>
          <p className="mt-1 text-[11px] text-slate-500">
            Categories the agent is designed to produce once templates and storage are wired.
          </p>
          <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {DOCUMENT_KINDS.map((d) => (
              <div
                key={d.tag}
                className="rounded-lg border border-slate-800 bg-[#151824] px-3 py-3"
              >
                <Badge variant="outline" className={cn("mb-2 text-[10px]", kindTone(d.tag))}>
                  {d.tag}
                </Badge>
                <p className="text-xs font-medium text-white">{d.title}</p>
                <p className="mt-1 text-[11px] text-slate-400">{d.detail}</p>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      <AgentInfoPanel
        agentName={AGENT_NAME}
        schedule="Deployed beat: daily at 07:00 (`scheduler/celery_app.py`) — pending document-request polling when Django exposes routes."
        bullets={SECRETARIAT_AGENT_BULLETS}
        accent={ACCENT}
        defaultOpen
        footerNote="Until `secretariat` models and `/api/secretariat/*` are added in church-management-saas-backend, this page is observability + roadmap. See BUILD_PLAN.md § secretariat models and frontend.md § secretariat."
      />

      {showScopePicker && (
        <div className="flex max-w-xl flex-col gap-1.5 rounded-lg border border-slate-800 bg-[#1a1d27] p-4">
          <label htmlFor="secretariat-church-scope" className="text-xs font-medium text-slate-400">
            Platform admin: pick a church label for scoped widgets below.
          </label>
          <select
            id="secretariat-church-scope"
            value={scopeChurchId}
            onChange={(e) => setScopeChurchId(e.target.value)}
            className="rounded-lg border border-slate-700 bg-[#21253a] px-3 py-2 text-sm text-white outline-none focus:border-[#e76f51]"
          >
            <option value="">Select a church…</option>
            {churches.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </div>
      )}

      <Card className="border-slate-800 bg-[#1a1d27]">
        <CardContent className="space-y-4 p-6">
          <div>
            <h2 className="text-base font-semibold text-white">{AGENT_NAME} activity</h2>
            <p className="mt-1 text-xs text-slate-500">
              Alerts and AgentLog rows from `agents/secretariat_agent.py` when the scheduled job runs successfully.
            </p>
          </div>

          {bootLoading && <Skeleton className="h-24 bg-slate-800" />}
          {!bootLoading && waitingPlatformScope && (
            <p className="text-sm text-slate-400">Choose a church to load agent monitor data.</p>
          )}
          {!bootLoading && !waitingPlatformScope && needsChurch && (
            <p className="text-sm text-amber-200/90">
              No church on this account. Associate a congregation or ensure `/api/auth/churches/` returns data.
            </p>
          )}
          {!bootLoading && !waitingPlatformScope && scopeReady && monitorLoading && (
            <Skeleton className="h-32 bg-slate-800" />
          )}
          {!bootLoading && !waitingPlatformScope && scopeReady && !monitorLoading && (
            <>
              <div className="flex flex-wrap items-center gap-3 rounded-lg border border-slate-800 bg-[#151824] px-4 py-3 text-sm">
                <span className="text-slate-400">Latest scheduled check</span>
                {latestRun ? (
                  <>
                    <Badge variant="outline" className="border-slate-600 font-mono text-xs text-slate-300">
                      {latestRun.action}
                    </Badge>
                    <span
                      className={cn(
                        "rounded-full px-2 py-0.5 text-xs font-semibold",
                        latestRun.status === "SUCCESS"
                          ? "bg-[#e76f5122] text-[#e76f51]"
                          : latestRun.status === "FAILED"
                            ? "bg-[#ff6b6b22] text-[#ff6b6b]"
                            : "bg-slate-700 text-slate-300"
                      )}
                    >
                      {latestRun.status}
                    </span>
                    <span className="text-xs text-slate-500">
                      {formatDistanceToNow(new Date(latestRun.created_at), { addSuffix: true })} ·{" "}
                      {latestRun.duration_ms}ms
                    </span>
                  </>
                ) : (
                  <span className="text-slate-500">
                    No {AGENT_NAME} runs logged for this church yet — beat task may be idle or APIs returned errors.
                  </span>
                )}
                <Link
                  href="/logs"
                  className="ml-auto inline-flex items-center gap-1 text-xs font-medium text-[#e76f51] hover:underline"
                >
                  All agent logs <ArrowRight className="size-3" />
                </Link>
              </div>

              <div className="overflow-x-auto rounded-lg border border-slate-800">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-slate-800 bg-[#151824]">
                      <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                        When
                      </th>
                      <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                        Type
                      </th>
                      <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                        Severity
                      </th>
                      <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                        Message
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {recentAlerts.length === 0 ? (
                      <tr>
                        <td colSpan={4} className="px-3 py-6 text-center text-xs text-slate-500">
                          No secretariat alerts yet — pending document APIs will populate PENDING_DOCUMENT items.
                        </td>
                      </tr>
                    ) : (
                      recentAlerts.map((a) => (
                        <tr key={a.id} className="border-b border-slate-800/60 last:border-0">
                          <td className="whitespace-nowrap px-3 py-2 text-xs text-slate-500">
                            {formatDistanceToNow(new Date(a.created_at), { addSuffix: true })}
                          </td>
                          <td className="px-3 py-2 text-xs text-slate-300">{a.alert_type}</td>
                          <td className="px-3 py-2">
                            <span
                              className={cn(
                                "rounded-full border px-2 py-0.5 text-[11px] font-semibold",
                                severityClass[a.severity] ?? "border-slate-600 bg-slate-800 text-slate-400"
                              )}
                            >
                              {a.severity}
                            </span>
                          </td>
                          <td className="max-w-md px-3 py-2 text-xs text-slate-400">{a.message}</td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </CardContent>
      </Card>

      <Card className="border-slate-800 bg-[#1a1d27]">
        <CardContent className="space-y-4 p-6">
          <div>
            <h2 className="text-base font-semibold text-white">Backend connectivity</h2>
            <p className="mt-1 text-xs text-slate-500">
              Optional probes to planned Django routes. 404 / errors mean the secretariat app is still a scaffold — add
              ViewSets and mount them under <code className="text-slate-400">/api/secretariat/</code>.
            </p>
          </div>

          {!bootLoading && waitingPlatformScope && (
            <p className="text-sm text-slate-400">Select a church to probe APIs.</p>
          )}
          {scopeReady && apiLoading && <Skeleton className="h-24 bg-slate-800" />}
          {scopeReady && !apiLoading && backendLikelyMissing && (
            <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-[11px] leading-relaxed text-amber-100/90">
              <p className="font-medium text-amber-50/95">Secretariat APIs not mounted or returned an error.</p>
              <p className="mt-2 text-amber-100/85">
                {(docIsError || minutesIsError) && (
                  <>
                    {docIsError && (
                      <span className="block">
                        document-requests: {docError instanceof Error ? docError.message : String(docError)}
                      </span>
                    )}
                    {minutesIsError && (
                      <span className="mt-1 block">
                        meeting-minutes:{" "}
                        {minutesError instanceof Error ? minutesError.message : String(minutesError)}
                      </span>
                    )}
                  </>
                )}
              </p>
              <p className="mt-2 text-amber-100/80">
                Implement models in <code className="text-amber-50/90">church-management-saas-backend/secretariat/</code>,
                expose ViewSets, and include them under{" "}
                <code className="text-amber-50/90">api/secretariat/</code> in Django URLconf — see BUILD_PLAN Step 4 and{" "}
                <code className="text-amber-50/90">frontend.md</code> § secretariat.
              </p>
            </div>
          )}
          {scopeReady && !apiLoading && !backendLikelyMissing && (
            <div className="grid gap-4 lg:grid-cols-2">
              <div>
                <h3 className="mb-2 text-xs font-medium uppercase tracking-wide text-slate-500">
                  Document requests ({docRows.length})
                </h3>
                <p className="text-[11px] text-slate-500">
                  Raw rows returned from GET secretariat/document-requests/
                </p>
                <pre className="mt-2 max-h-[200px] overflow-auto rounded-lg bg-[#0d1117] p-3 text-[10px] text-slate-400">
                  {JSON.stringify(docReqData, null, 2)}
                </pre>
              </div>
              <div>
                <h3 className="mb-2 text-xs font-medium uppercase tracking-wide text-slate-500">
                  Meeting minutes ({minutesRows.length})
                </h3>
                <p className="text-[11px] text-slate-500">
                  Raw rows returned from GET secretariat/meeting-minutes/
                </p>
                <pre className="mt-2 max-h-[200px] overflow-auto rounded-lg bg-[#0d1117] p-3 text-[10px] text-slate-400">
                  {JSON.stringify(minutesData, null, 2)}
                </pre>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
