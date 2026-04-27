import { ChevronDown } from "lucide-react"

import { CardDescription, CardTitle } from "@/components/ui/card"
import { cn } from "@/lib/utils"

interface AgentInfoPanelProps {
  agentName: string
  schedule: string
  bullets: readonly string[]
  accent: string
  /** Shown under the list (defaults to API vs scheduled job explanation). */
  footerNote?: string
  /** When false, panel is collapsed by default so the page stays scannable. */
  defaultOpen?: boolean
}

const DEFAULT_FOOTER =
  "Numbers on this page come straight from Django when you choose a church. Scheduled agents run separately to send alerts and emails."

export function AgentInfoPanel({
  agentName,
  schedule,
  bullets,
  accent,
  footerNote = DEFAULT_FOOTER,
  defaultOpen = false,
}: AgentInfoPanelProps) {
  return (
    <details
      open={defaultOpen}
      className="group overflow-hidden rounded-xl border border-slate-800 bg-[#151824] ring-offset-[#0f1117]"
      style={{ borderLeftWidth: 3, borderLeftColor: accent }}
    >
      <summary
        className={cn(
          "flex cursor-pointer list-none items-center justify-between gap-3 px-4 py-3 text-sm text-slate-200 outline-none hover:bg-[#1a1d27]",
          "[&::-webkit-details-marker]:hidden"
        )}
      >
        <span className="font-medium text-white">Scheduled agent — {agentName}</span>
        <ChevronDown className="size-4 shrink-0 text-slate-500 transition-transform duration-200 group-open:rotate-180" />
      </summary>
      <div className="border-t border-slate-800 px-4 pb-4 pt-2">
        <CardTitle className="sr-only">{agentName}</CardTitle>
        <CardDescription className="text-xs text-slate-500">{schedule}</CardDescription>
        <ul className="mt-3 list-disc space-y-1.5 pl-5 text-xs text-slate-300">
          {bullets.map((b, i) => (
            <li key={`${agentName}-${i}`}>{b}</li>
          ))}
        </ul>
        <p className="mt-3 border-t border-slate-800 pt-3 text-[11px] leading-relaxed text-slate-500">
          {footerNote}
        </p>
      </div>
    </details>
  )
}
