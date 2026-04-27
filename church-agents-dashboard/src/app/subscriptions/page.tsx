"use client"

import { useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import {
  AlertTriangle,
  CheckCircle,
  CreditCard,
  Lock,
  Send,
  Unlock,
  XCircle,
} from "lucide-react"

import { PageHeader } from "@/components/page-header"
import { StatCard } from "@/components/stat-card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { api } from "@/lib/api"
import type { Church } from "@/lib/types"
import { cn } from "@/lib/utils"

/** Align `days_left` with SubscriptionWatchdogAgent reminder copy (calendar-day horizon). */
function reminderDaysLeft(subscriptionEndsAt: string | null | undefined): number {
  if (!subscriptionEndsAt) return 7
  const d = Math.ceil(
    (new Date(subscriptionEndsAt).getTime() - Date.now()) / 86400000
  )
  return Math.min(365, Math.max(1, d))
}

function planBadge(plan: string) {
  const map: Record<string, string> = {
    FREE: "bg-slate-700 text-slate-300",
    TRIAL: "border border-[#ffd16644] bg-[#ffd16622] text-[#ffd166]",
    BASIC: "border border-[#6c63ff44] bg-[#6c63ff22] text-[#6c63ff]",
    PREMIUM: "border border-[#00d4aa44] bg-[#00d4aa22] text-[#00d4aa]",
    ENTERPRISE: "border border-[#f4a26144] bg-[#f4a26122] text-[#f4a261]",
  }
  return map[plan] || "bg-slate-700 text-slate-300"
}

export default function SubscriptionsPage() {
  const [filter, setFilter] = useState("all")
  const qc = useQueryClient()

  const { data, isLoading } = useQuery({
    queryKey: ["churches"],
    queryFn: () => api.getChurches({ page_size: "500" }),
    refetchInterval: 60_000,
  })

  const disable = useMutation({
    mutationFn: (id: string) => api.disableChurch(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["churches"] }),
  })

  const reinstate = useMutation({
    mutationFn: (id: string) => api.reinstateChurch(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["churches"] }),
  })

  const remind = useMutation({
    mutationFn: ({ id, daysLeft }: { id: string; daysLeft: number }) =>
      api.sendRenewalReminder(id, daysLeft),
  })

  const all: Church[] = data?.results ?? []
  const now = Date.now()

  const filtered = all.filter((c) => {
    const plan = c.subscription_plan ?? ""
    if (filter === "trial") return plan === "TRIAL"
    if (filter === "expiring") {
      const days = c.subscription_ends_at
        ? (new Date(c.subscription_ends_at).getTime() - now) / 86400000
        : Infinity
      return days <= 7 && days >= 0
    }
    if (filter === "suspended") return c.platform_access_enabled === false
    return true
  })

  const stats = {
    total: all.length,
    active: all.filter((c) => c.subscription_status === "ACTIVE" || c.status === "ACTIVE").length,
    trial: all.filter((c) => (c.subscription_plan ?? "") === "TRIAL").length,
    expiring: all.filter((c) => {
      const days = c.subscription_ends_at
        ? (new Date(c.subscription_ends_at).getTime() - now) / 86400000
        : Infinity
      return days <= 7 && days >= 0
    }).length,
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Subscriptions"
        description="SubscriptionWatchdogAgent monitors plans on a schedule; Remind sends the same renewal email template for one church."
        icon={CreditCard}
        color="#ff6b6b"
        agentName="SubscriptionWatchdogAgent"
      />

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {isLoading ? (
          Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-24 bg-slate-800" />)
        ) : (
          <>
            <StatCard title="Total Churches" value={stats.total} icon={CreditCard} color="#6c63ff" />
            <StatCard title="Active" value={stats.active} icon={CheckCircle} color="#00d4aa" />
            <StatCard title="Trial" value={stats.trial} icon={AlertTriangle} color="#ffd166" />
            <StatCard title="Expiring ≤7 days" value={stats.expiring} icon={XCircle} color="#ff6b6b" />
          </>
        )}
      </div>

      <Card className="border-slate-800 bg-[#1a1d27]">
        <CardContent className="p-0">
          <div className="border-b border-slate-800 p-4">
            <Tabs value={filter} onValueChange={setFilter}>
              <TabsList className="bg-[#21253a]">
                <TabsTrigger value="all">All ({all.length})</TabsTrigger>
                <TabsTrigger value="trial">Trial</TabsTrigger>
                <TabsTrigger value="expiring">Expiring</TabsTrigger>
                <TabsTrigger value="suspended">Suspended</TabsTrigger>
              </TabsList>
            </Tabs>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-800">
                  {["Church", "Plan", "Status", "Expires", "Email", "Actions"].map((h) => (
                    <th
                      key={h}
                      className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-500"
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {isLoading
                  ? Array.from({ length: 6 }).map((_, i) => (
                      <tr key={i}>
                        <td colSpan={6} className="px-4 py-3">
                          <Skeleton className="h-6 bg-slate-800" />
                        </td>
                      </tr>
                    ))
                  : filtered.map((church) => {
                      const plan = church.subscription_plan ?? "—"
                      const status = church.subscription_status ?? church.status ?? "—"
                      const daysLeft = church.subscription_ends_at
                        ? Math.ceil(
                            (new Date(church.subscription_ends_at).getTime() - now) / 86400000
                          )
                        : null

                      return (
                        <tr
                          key={church.id}
                          className="border-b border-slate-800/50 transition-colors hover:bg-[#21253a]"
                        >
                          <td className="px-4 py-3">
                            <div>
                              <p className="font-medium text-white">{church.name}</p>
                              <p className="text-xs text-slate-500">{church.user_count ?? 0} users</p>
                            </div>
                          </td>
                          <td className="px-4 py-3">
                            <span
                              className={cn(
                                "rounded-full px-2 py-1 text-xs font-semibold",
                                planBadge(plan)
                              )}
                            >
                              {plan}
                            </span>
                          </td>
                          <td className="px-4 py-3">
                            <Badge variant="outline" className="border-slate-600 text-slate-300">
                              {status}
                            </Badge>
                          </td>
                          <td className="px-4 py-3 text-slate-400">
                            {church.subscription_ends_at
                              ? `${church.subscription_ends_at.slice(0, 10)}${
                                  daysLeft !== null ? ` (${daysLeft}d)` : ""
                                }`
                              : "—"}
                          </td>
                          <td className="max-w-[200px] truncate px-4 py-3 text-xs text-slate-500">
                            {church.email ?? "—"}
                          </td>
                          <td className="space-x-2 px-4 py-3">
                            <Button
                              size="sm"
                              variant="outline"
                              className="h-7 border-slate-600 text-xs"
                              onClick={() =>
                                remind.mutate({
                                  id: church.id,
                                  daysLeft: reminderDaysLeft(church.subscription_ends_at),
                                })
                              }
                              disabled={remind.isPending}
                            >
                              <Send size={12} className="mr-1" />
                              Remind
                            </Button>
                            {church.platform_access_enabled !== false ? (
                              <Button
                                size="sm"
                                variant="outline"
                                className="h-7 border-red-900/50 text-xs text-red-400"
                                onClick={() => disable.mutate(church.id)}
                                disabled={disable.isPending}
                              >
                                <Lock size={12} className="mr-1" />
                                Suspend
                              </Button>
                            ) : (
                              <Button
                                size="sm"
                                variant="outline"
                                className="h-7 border-emerald-900/50 text-xs text-emerald-400"
                                onClick={() => reinstate.mutate(church.id)}
                                disabled={reinstate.isPending}
                              >
                                <Unlock size={12} className="mr-1" />
                                Enable
                              </Button>
                            )}
                          </td>
                        </tr>
                      )
                    })}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
