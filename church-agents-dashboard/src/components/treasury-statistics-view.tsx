import {
  ArrowDownRight,
  ArrowUpRight,
  Building2,
  ClipboardList,
  Landmark,
  Scale,
} from "lucide-react"

import { StatCard } from "@/components/stat-card"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import type { TreasuryStatistics } from "@/lib/types"

function fmtAmount(n: string | number | undefined | null) {
  if (n === undefined || n === null) return "—"
  const v = typeof n === "string" ? parseFloat(n) : n
  if (Number.isNaN(v)) return "—"
  return v.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function BreakdownTable({
  title,
  rows,
  nameKey,
}: {
  title: string
  rows: { name: string; total: string; count: number }[]
  nameKey: string
}) {
  if (rows.length === 0) {
    return (
      <div className="rounded-lg border border-slate-800/80 bg-[#0d1117]/50 px-3 py-6 text-center text-xs text-slate-500">
        No data for {title.toLowerCase()} in the current API period.
      </div>
    )
  }

  return (
    <div className="overflow-hidden rounded-lg border border-slate-800">
      <table className="w-full text-left text-xs">
        <thead>
          <tr className="border-b border-slate-800 bg-[#151824] text-slate-500">
            <th className="px-3 py-2 font-medium">{nameKey}</th>
            <th className="px-3 py-2 font-medium">Amount</th>
            <th className="px-3 py-2 font-medium text-right">Count</th>
          </tr>
        </thead>
        <tbody className="text-slate-300">
          {rows.map((row, i) => (
            <tr key={`${row.name}-${i}`} className="border-b border-slate-800/80 last:border-0">
              <td className="px-3 py-2">{row.name || "—"}</td>
              <td className="px-3 py-2 font-mono tabular-nums">{row.total}</td>
              <td className="px-3 py-2 text-right tabular-nums text-slate-500">{row.count}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function TreasuryStatisticsView({ data }: { data: TreasuryStatistics }) {
  const incomeRows = (data.income_by_category ?? []).map((r) => ({
    name: r.category__name ?? "Uncategorized",
    total: fmtAmount(r.total),
    count: r.count ?? 0,
  }))
  const expenseCatRows = (data.expenses_by_category ?? []).map((r) => ({
    name: r.category__name ?? "Uncategorized",
    total: fmtAmount(r.total),
    count: r.count ?? 0,
  }))
  const deptRows = (data.expenses_by_department ?? []).map((r) => ({
    name: r.department__name ?? "—",
    total: fmtAmount(r.total),
    count: r.count ?? 0,
  }))

  const net = parseFloat(String(data.net_balance))
  const netPositive = !Number.isNaN(net) && net >= 0

  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
        <StatCard
          title="Total income"
          value={fmtAmount(data.total_income)}
          icon={ArrowDownRight}
          color="#00d4aa"
        />
        <StatCard
          title="Total expenses"
          value={fmtAmount(data.total_expenses)}
          icon={ArrowUpRight}
          color="#ff6b6b"
        />
        <StatCard
          title="Net balance"
          value={fmtAmount(data.net_balance)}
          subtitle={netPositive ? "Income exceeds expenses" : "Expenses exceed income"}
          icon={Scale}
          color={netPositive ? "#00d4aa" : "#ffd166"}
        />
        <StatCard
          title="Pending expense requests"
          value={data.pending_expense_requests ?? 0}
          icon={ClipboardList}
          color="#8892b0"
        />
        <StatCard
          title="Assets (book value)"
          value={fmtAmount(data.total_assets_value)}
          icon={Landmark}
          color="#6c63ff"
        />
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="border-slate-800 bg-[#1a1d27]">
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-sm font-semibold text-white">
              <Building2 size={14} className="text-[#00d4aa]" />
              Income by category
            </CardTitle>
          </CardHeader>
          <CardContent>
            <BreakdownTable title="Income by category" rows={incomeRows} nameKey="Category" />
          </CardContent>
        </Card>

        <Card className="border-slate-800 bg-[#1a1d27]">
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-sm font-semibold text-white">
              <Building2 size={14} className="text-[#ff6b6b]" />
              Expenses by category
            </CardTitle>
          </CardHeader>
          <CardContent>
            <BreakdownTable title="Expenses by category" rows={expenseCatRows} nameKey="Category" />
          </CardContent>
        </Card>

        <Card className="border-slate-800 bg-[#1a1d27]">
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-sm font-semibold text-white">
              <Building2 size={14} className="text-[#ffd166]" />
              Expenses by department
            </CardTitle>
          </CardHeader>
          <CardContent>
            <BreakdownTable title="Expenses by department" rows={deptRows} nameKey="Department" />
          </CardContent>
        </Card>
      </div>

      <details className="rounded-lg border border-slate-800 bg-[#0d1117]/60">
        <summary className="cursor-pointer px-4 py-3 text-xs font-medium text-slate-500 hover:text-slate-400">
          Developer: raw JSON response
        </summary>
        <pre className="max-h-[280px] overflow-auto border-t border-slate-800 p-4 text-[11px] text-slate-400">
          {JSON.stringify(data, null, 2)}
        </pre>
      </details>
    </div>
  )
}
