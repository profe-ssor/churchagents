import { cn } from "@/lib/utils"

export interface AgentTaskStep {
  title: string
  description: string
}

interface AgentTaskFlowProps {
  /** Accent color matching the agent (hex). */
  accent: string
  /** Short heading — default emphasizes this is the agent’s job loop, not generic reporting. */
  headline?: string
  steps: readonly AgentTaskStep[]
  className?: string
}

/**
 * Always-visible strip that maps dashboard pages to the agent’s concrete task pipeline.
 * Complements AgentInfoPanel (detail + env vars), which stays collapsible elsewhere.
 */
export function AgentTaskFlow({
  accent,
  headline = "What this agent does each run",
  steps,
  className,
}: AgentTaskFlowProps) {
  return (
    <div
      className={cn(
        "rounded-xl border border-slate-800 bg-[#151824] p-4 ring-offset-[#0f1117]",
        className
      )}
      style={{ borderLeftWidth: 3, borderLeftColor: accent }}
    >
      <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">{headline}</p>
      <div className="mt-4 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {steps.map((s, i) => (
          <div key={s.title} className="relative flex gap-3">
            <span
              className="flex size-8 shrink-0 items-center justify-center rounded-full text-xs font-bold text-[#0f1117]"
              style={{ backgroundColor: accent }}
            >
              {i + 1}
            </span>
            <div className="min-w-0 pt-0.5">
              <p className="text-sm font-medium leading-snug text-white">{s.title}</p>
              <p className="mt-1 text-[11px] leading-relaxed text-slate-400">{s.description}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
