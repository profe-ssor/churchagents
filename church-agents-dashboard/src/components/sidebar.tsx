"use client"

import { useRouter } from "next/navigation"
import Link from "next/link"
import { usePathname } from "next/navigation"
import {
  LayoutDashboard,
  MessageSquare,
  CreditCard,
  DollarSign,
  Users,
  Building2,
  Megaphone,
  Shield,
  FileText,
  ScrollText,
  Settings,
  LogOut,
  ShieldCheck,
  Church,
  Activity,
} from "lucide-react"

import { AI_NAME_SHORT, AI_NAV_BADGE } from "@/lib/branding"
import { cn } from "@/lib/utils"
import type { SessionUser } from "@/lib/auth"

const ALL_NAV = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard, color: "#6c63ff", agent: "Overview", adminOnly: false },
  {
    href: "/ask",
    label: `Ask ${AI_NAME_SHORT}`,
    icon: MessageSquare,
    color: "#6c63ff",
    agent: AI_NAV_BADGE,
    adminOnly: false,
  },
  { href: "/subscriptions", label: "Subscriptions", icon: CreditCard, color: "#ff6b6b", agent: "Watchdog", adminOnly: true },
  { href: "/treasury", label: "Treasury", icon: DollarSign, color: "#00d4aa", agent: "Finance", adminOnly: false },
  { href: "/members", label: "Members", icon: Users, color: "#ffd166", agent: "Care", adminOnly: false },
  { href: "/departments", label: "Departments", icon: Building2, color: "#4ecdc4", agent: "Programs", adminOnly: false },
  { href: "/announcements", label: "Announcements", icon: Megaphone, color: "#a8dadc", agent: "Comms", adminOnly: false },
  { href: "/security", label: "Security", icon: Shield, color: "#f4a261", agent: "Audit", adminOnly: false },
  { href: "/secretariat", label: "Secretariat", icon: FileText, color: "#e76f51", agent: "Records", adminOnly: false },
  { href: "/logs", label: "Agent Logs", icon: ScrollText, color: "#8892b0", agent: "All Agents", adminOnly: false },
  {
    href: "/observability",
    label: "Observability",
    icon: Activity,
    color: "#a8b2ff",
    agent: "Metrics",
    adminOnly: false,
  },
  { href: "/settings", label: "Settings", icon: Settings, color: "#8892b0", agent: "Schedules", adminOnly: true },
]

interface Props {
  user: SessionUser
}

export function Sidebar({ user }: Props) {
  const pathname = usePathname()
  const router = useRouter()

  const nav = ALL_NAV.filter((item) => !item.adminOnly || user.is_platform_admin)

  function isActive(href: string) {
    if (href === "/") return pathname === "/"
    return pathname === href || pathname.startsWith(`${href}/`)
  }

  async function handleLogout() {
    await fetch("/api/auth/logout", { method: "POST" })
    router.push("/login")
    router.refresh()
  }

  const displayName = user.full_name || user.email || "User"
  const initials = user.full_name
    ? user.full_name.split(" ").map((n) => n[0]).join("").slice(0, 2).toUpperCase()
    : (user.email || "??").slice(0, 2).toUpperCase()

  return (
    <aside className="flex h-screen w-60 shrink-0 flex-col border-r border-slate-800 bg-[#1a1d27]">
      <div className="border-b border-slate-800 p-5">
        <div className="flex items-center gap-3">
          <div className="flex size-8 items-center justify-center rounded-lg bg-[#6c63ff] text-sm font-bold text-white">
            CT
          </div>
          <div>
            <p className="text-sm font-bold text-white">Church Agents</p>
            <p className="text-xs text-slate-500">{AI_NAME_SHORT} · Church Technician Officer</p>
          </div>
        </div>
      </div>

      <nav className="flex-1 space-y-0.5 overflow-y-auto p-3">
        {nav.map((item) => {
          const Icon = item.icon
          const active = isActive(item.href)
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "group flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition-all",
                active ? "bg-[#21253a] text-white" : "text-slate-400 hover:bg-[#21253a] hover:text-white"
              )}
            >
              <Icon
                size={16}
                style={{ color: active ? item.color : undefined }}
                className={cn(!active && "group-hover:text-slate-300")}
              />
              <span className="flex-1">{item.label}</span>
              <span
                className="rounded px-1.5 py-0.5 text-[10px] font-semibold"
                style={{
                  background: active ? `${item.color}22` : "transparent",
                  color: active ? item.color : "transparent",
                }}
              >
                {item.agent}
              </span>
            </Link>
          )
        })}
      </nav>

      {/* User identity + role */}
      <div className="border-t border-slate-800 p-4 space-y-3">
        <div className="flex items-center gap-3">
          <div className="flex size-8 shrink-0 items-center justify-center rounded-full bg-[#6c63ff22] text-xs font-bold text-[#6c63ff]">
            {initials}
          </div>
          <div className="min-w-0">
            <p className="truncate text-xs font-semibold text-white">{displayName}</p>
            <div className="mt-0.5 flex items-center gap-1">
              {user.is_platform_admin ? (
                <>
                  <ShieldCheck size={10} className="text-[#6c63ff]" />
                  <span className="text-[10px] text-[#6c63ff]">Platform Admin</span>
                </>
              ) : (
                <>
                  <Church size={10} className="text-[#00d4aa]" />
                  <span className="truncate text-[10px] text-[#00d4aa]">
                    {user.church_name || "Church Admin"}
                  </span>
                </>
              )}
            </div>
          </div>
        </div>

        <button
          onClick={handleLogout}
          className="flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-xs text-slate-500 transition-colors hover:bg-[#21253a] hover:text-slate-300"
        >
          <LogOut size={12} />
          Sign out
        </button>
      </div>
    </aside>
  )
}
