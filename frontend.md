# Church Agents — Next.js Frontend Dashboard

A full-stack dashboard to visualise and interact with all 8 church agents.

---

## Tech Stack

| Tool | Purpose |
|------|---------|
| Next.js 15 (App Router) | Framework |
| TypeScript | Type safety |
| Tailwind CSS | Styling |
| shadcn/ui | UI components |
| Recharts | Charts |
| TanStack Query v5 | Data fetching & caching |
| Axios | HTTP client |
| next-themes | Dark/light mode |
| lucide-react | Icons |

---

## 1. Project Setup

```bash
# Create the project
npx create-next-app@latest church-agents-dashboard --typescript --tailwind --app --src-dir --import-alias "@/*"
cd church-agents-dashboard

# Install shadcn/ui
npx shadcn@latest init
# When prompted: style=Default, base color=Slate, CSS variables=yes

# Install shadcn components
npx shadcn@latest add card table badge button input tabs switch dialog skeleton separator scroll-area avatar dropdown-menu tooltip

# Install remaining deps
npm install axios @tanstack/react-query recharts next-themes lucide-react date-fns
```

---

## 2. Folder Structure

```
church-agents-dashboard/
├── src/
│   ├── app/
│   │   ├── layout.tsx                  ← root layout, sidebar, providers
│   │   ├── page.tsx                    ← Dashboard (overview)
│   │   ├── ask/page.tsx                ← Ask AI (OrchestratorAgent chat)
│   │   ├── subscriptions/page.tsx      ← SubscriptionWatchdogAgent
│   │   ├── treasury/page.tsx           ← TreasuryHealthAgent
│   │   ├── members/page.tsx            ← MemberCareAgent
│   │   ├── departments/page.tsx        ← DepartmentProgramAgent
│   │   ├── announcements/page.tsx      ← AnnouncementAgent
│   │   ├── security/page.tsx           ← AuditSecurityAgent
│   │   ├── secretariat/page.tsx        ← SecretariatAgent
│   │   ├── logs/page.tsx               ← All agent logs
│   │   ├── settings/page.tsx           ← Agent schedules on/off
│   │   └── api/
│   │       ├── agents/ask/route.ts     ← Proxy to Django
│   │       └── django/[...path]/route.ts ← Generic Django proxy
│   ├── components/
│   │   ├── sidebar.tsx
│   │   ├── stat-card.tsx
│   │   ├── agent-status-card.tsx
│   │   ├── data-table.tsx
│   │   ├── page-header.tsx
│   │   └── providers.tsx
│   └── lib/
│       ├── api.ts                      ← Axios + auth
│       ├── types.ts                    ← All TypeScript types
│       └── utils.ts                    ← shadcn utils (auto-generated)
├── .env.local
└── tailwind.config.ts
```

---

## 3. Environment Variables

```env
# .env.local
NEXT_PUBLIC_DJANGO_URL=http://localhost:8000
DJANGO_AGENT_EMAIL=agent-bot@yourdomain.com
DJANGO_AGENT_PASSWORD=your-bot-password
NEXTAUTH_SECRET=any-random-string-32-chars
```

---

## 4. TypeScript Types — `src/lib/types.ts`

```typescript
export interface Church {
  id: number
  name: string
  email: string
  admin_email: string
  plan: 'FREE' | 'TRIAL' | 'BASIC' | 'PREMIUM' | 'ENTERPRISE'
  subscription_status: 'ACTIVE' | 'TRIAL' | 'EXPIRED' | 'SUSPENDED'
  subscription_ends_at: string | null
  platform_access_enabled: boolean
  member_count: number
}

export interface AgentLog {
  id: number
  agent_name: string
  church: number | null
  church_name?: string
  action: string
  status: 'SUCCESS' | 'FAILED' | 'SKIPPED'
  triggered_by: 'SCHEDULED' | 'WEBHOOK' | 'ON_DEMAND' | 'EVENT'
  duration_ms: number
  error: string
  input_data: Record<string, unknown>
  output_data: Record<string, unknown>
  created_at: string
}

export interface AgentAlert {
  id: number
  agent_name: string
  church: number | null
  church_name?: string
  alert_type: string
  channel: 'EMAIL' | 'SMS' | 'IN_APP'
  recipient: string
  subject: string
  status: 'SENT' | 'FAILED' | 'SKIPPED'
  sent_at: string
}

export interface AgentSchedule {
  id: number
  agent_name: string
  is_enabled: boolean
  cron_expr: string
  last_run: string | null
  next_run: string | null
  last_status: string
}

export interface Member {
  id: number
  first_name: string
  last_name: string
  email: string
  phone: string
  church_name: string
  status: 'ACTIVE' | 'INACTIVE' | 'VISITOR' | 'TRANSFER' | 'NEW_CONVERT'
  date_of_birth: string | null
  created_at: string
}

export interface ExpenseRequest {
  id: number
  title: string
  amount: number
  church_name: string
  department_name: string
  approval_stage: string
  status: string
  created_at: string
  hours_stalled: number
}

export interface Announcement {
  id: number
  title: string
  content: string
  church_name: string
  category: string
  priority: 'LOW' | 'MEDIUM' | 'HIGH' | 'URGENT'
  status: 'DRAFT' | 'PENDING_REVIEW' | 'APPROVED' | 'PUBLISHED'
  created_at: string
}

export interface DocumentRequest {
  id: number
  member_name: string
  church_name: string
  doc_type: string
  purpose: string
  status: 'PENDING' | 'IN_PROGRESS' | 'COMPLETED'
  created_at: string
}

export interface AuditEntry {
  id: number
  user_email: string
  church_name: string
  action: string
  description: string
  ip_address: string
  created_at: string
}

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  timestamp: string
}

export interface TreasuryStats {
  total_income_month: number
  total_expenses_month: number
  pending_requests: number
  stalled_requests: number
}

export interface DashboardStats {
  total_churches: number
  active_subscriptions: number
  expiring_this_week: number
  failed_payments: number
  total_members: number
  agents_running: number
}
```

---

## 5. API Client — `src/lib/api.ts`

```typescript
import axios from 'axios'

const django = axios.create({
  baseURL: process.env.NEXT_PUBLIC_DJANGO_URL || 'http://localhost:8000',
  timeout: 30000,
})

// Token storage (client-side)
let accessToken: string | null = null

export async function loginBot(): Promise<void> {
  const res = await axios.post(`${process.env.NEXT_PUBLIC_DJANGO_URL}/api/auth/login/`, {
    email: process.env.NEXT_PUBLIC_BOT_EMAIL,
    password: process.env.NEXT_PUBLIC_BOT_PASSWORD,
  })
  accessToken = res.data.access
}

django.interceptors.request.use((config) => {
  if (accessToken) {
    config.headers.Authorization = `Bearer ${accessToken}`
  }
  return config
})

django.interceptors.response.use(
  (res) => res,
  async (error) => {
    if (error.response?.status === 401 && accessToken) {
      accessToken = null
      await loginBot()
      error.config.headers.Authorization = `Bearer ${accessToken}`
      return django(error.config)
    }
    return Promise.reject(error)
  }
)

export default django

// ── Typed API helpers ────────────────────────────────────────────

export const api = {
  // Dashboard
  getDashboardStats: () =>
    fetch('/api/django/agents/dashboard/').then(r => r.json()),

  // Agents
  getAgentLogs: (params?: Record<string, string>) =>
    fetch('/api/django/agents/logs/?' + new URLSearchParams(params)).then(r => r.json()),

  getAgentAlerts: () =>
    fetch('/api/django/agents/alerts/').then(r => r.json()),

  getAgentSchedules: () =>
    fetch('/api/django/agents/schedules/').then(r => r.json()),

  updateAgentSchedule: (id: number, data: Partial<AgentSchedule>) =>
    fetch(`/api/django/agents/schedules/${id}/`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    }).then(r => r.json()),

  runAgentNow: (agentName: string) =>
    fetch('/api/django/agents/run/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ agent_name: agentName }),
    }).then(r => r.json()),

  // Orchestrator Q&A
  askAgent: (question: string, sessionId: string) =>
    fetch('/api/agents/ask', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question, session_id: sessionId }),
    }).then(r => r.json()),

  // Churches / Subscriptions
  getChurches: (params?: Record<string, string>) =>
    fetch('/api/django/auth/churches/?' + new URLSearchParams(params)).then(r => r.json()),

  disableChurch: (id: number) =>
    fetch(`/api/django/auth/churches/${id}/platform-access/`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ platform_access_enabled: false }),
    }).then(r => r.json()),

  reinstateChurch: (id: number) =>
    fetch(`/api/django/auth/churches/${id}/platform-access/`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ platform_access_enabled: true }),
    }).then(r => r.json()),

  sendRenewalReminder: (churchId: number) =>
    fetch('/api/django/agents/run/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ agent_name: 'SubscriptionWatchdogAgent', church_id: churchId }),
    }).then(r => r.json()),

  // Treasury
  getTreasuryStats: () =>
    fetch('/api/django/treasury/statistics/').then(r => r.json()),

  getStalledExpenses: () =>
    fetch('/api/django/treasury/expense-requests/?stalled=true').then(r => r.json()),

  getIncomeChart: () =>
    fetch('/api/django/treasury/income-chart/').then(r => r.json()),

  // Members
  getMembers: (params?: Record<string, string>) =>
    fetch('/api/django/members/?' + new URLSearchParams(params)).then(r => r.json()),

  getVisitors: () =>
    fetch('/api/django/members/visitors/').then(r => r.json()),

  sendBirthdayEmail: (memberId: number) =>
    fetch('/api/django/agents/run/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ agent_name: 'MemberCareAgent', action: 'birthday', member_id: memberId }),
    }).then(r => r.json()),

  // Departments
  getStalledPrograms: () =>
    fetch('/api/django/programs/?stalled=true').then(r => r.json()),

  getUpcomingActivities: () =>
    fetch('/api/django/departments/activities/?days_ahead=7').then(r => r.json()),

  // Announcements
  getAnnouncements: (status?: string) =>
    fetch(`/api/django/announcements/${status ? `?status=${status}` : ''}`).then(r => r.json()),

  // Security
  getAuditLogs: (params?: Record<string, string>) =>
    fetch('/api/django/activity/?' + new URLSearchParams(params)).then(r => r.json()),

  getLockedAccounts: () =>
    fetch('/api/django/auth/users/?is_locked=true').then(r => r.json()),

  // Secretariat
  getDocumentRequests: (status?: string) =>
    fetch(`/api/django/secretariat/document-requests/${status ? `?status=${status}` : ''}`).then(r => r.json()),

  getMeetingMinutes: () =>
    fetch('/api/django/secretariat/minutes/').then(r => r.json()),

  generateTransferLetter: (data: { member_id: number; destination: string; church_id: number }) =>
    fetch('/api/django/secretariat/transfer-letters/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    }).then(r => r.json()),
}
```

---

## 6. Django Proxy API Route — `src/app/api/django/[...path]/route.ts`

```typescript
import { NextRequest, NextResponse } from 'next/server'

const DJANGO_URL = process.env.NEXT_PUBLIC_DJANGO_URL || 'http://localhost:8000'
let cachedToken: string | null = null

async function getToken(): Promise<string> {
  if (cachedToken) return cachedToken
  const res = await fetch(`${DJANGO_URL}/api/auth/login/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      email: process.env.DJANGO_AGENT_EMAIL,
      password: process.env.DJANGO_AGENT_PASSWORD,
    }),
  })
  const data = await res.json()
  cachedToken = data.access
  return cachedToken!
}

async function proxyRequest(req: NextRequest, path: string): Promise<NextResponse> {
  const token = await getToken()
  const url = `${DJANGO_URL}/api/${path}${req.nextUrl.search}`

  const headers: Record<string, string> = {
    Authorization: `Bearer ${token}`,
    'Content-Type': 'application/json',
  }

  const body = req.method !== 'GET' ? await req.text() : undefined

  const res = await fetch(url, { method: req.method, headers, body })

  if (res.status === 401) {
    cachedToken = null
    return proxyRequest(req, path)
  }

  const data = await res.json().catch(() => ({}))
  return NextResponse.json(data, { status: res.status })
}

export async function GET(req: NextRequest, { params }: { params: { path: string[] } }) {
  return proxyRequest(req, params.path.join('/'))
}
export async function POST(req: NextRequest, { params }: { params: { path: string[] } }) {
  return proxyRequest(req, params.path.join('/'))
}
export async function PUT(req: NextRequest, { params }: { params: { path: string[] } }) {
  return proxyRequest(req, params.path.join('/'))
}
export async function DELETE(req: NextRequest, { params }: { params: { path: string[] } }) {
  return proxyRequest(req, params.path.join('/'))
}
```

---

## 7. Ask AI Proxy — `src/app/api/agents/ask/route.ts`

```typescript
import { NextRequest, NextResponse } from 'next/server'

const AGENTS_URL = process.env.AGENTS_API_URL || 'http://localhost:8001'

export async function POST(req: NextRequest) {
  const { question, session_id } = await req.json()

  // Call your Python OrchestratorAgent via a simple FastAPI wrapper
  // OR call Django directly if you expose an /api/agents/ask/ endpoint
  try {
    const res = await fetch(`${AGENTS_URL}/ask`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question, session_id }),
    })
    const data = await res.json()
    return NextResponse.json(data)
  } catch {
    // Fallback: call Django memory endpoint
    return NextResponse.json({
      answer: 'Agent service is not running. Start the agents server first.',
    })
  }
}
```

---

## 8. Providers — `src/components/providers.tsx`

```typescript
'use client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ThemeProvider } from 'next-themes'
import { useState } from 'react'

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(() => new QueryClient({
    defaultOptions: { queries: { staleTime: 30_000, refetchOnWindowFocus: false } },
  }))

  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider attribute="class" defaultTheme="dark" enableSystem={false}>
        {children}
      </ThemeProvider>
    </QueryClientProvider>
  )
}
```

---

## 9. Root Layout — `src/app/layout.tsx`

```typescript
import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import './globals.css'
import { Providers } from '@/components/providers'
import { Sidebar } from '@/components/sidebar'

const inter = Inter({ subsets: ['latin'] })

export const metadata: Metadata = {
  title: 'Church Agents Dashboard',
  description: 'Monitor and control your church management AI agents',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={`${inter.className} bg-[#0f1117] text-slate-100`}>
        <Providers>
          <div className="flex h-screen overflow-hidden">
            <Sidebar />
            <main className="flex-1 overflow-y-auto p-6">
              {children}
            </main>
          </div>
        </Providers>
      </body>
    </html>
  )
}
```

---

## 10. Sidebar — `src/components/sidebar.tsx`

```typescript
'use client'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { cn } from '@/lib/utils'
import {
  LayoutDashboard, MessageSquare, CreditCard, DollarSign,
  Users, Building2, Megaphone, Shield, FileText,
  ScrollText, Settings,
} from 'lucide-react'

const nav = [
  { href: '/',               label: 'Dashboard',      icon: LayoutDashboard, color: '#6c63ff', agent: 'Overview' },
  { href: '/ask',            label: 'Ask AI',         icon: MessageSquare,   color: '#6c63ff', agent: 'Orchestrator' },
  { href: '/subscriptions',  label: 'Subscriptions',  icon: CreditCard,      color: '#ff6b6b', agent: 'Watchdog' },
  { href: '/treasury',       label: 'Treasury',       icon: DollarSign,      color: '#00d4aa', agent: 'Finance' },
  { href: '/members',        label: 'Members',        icon: Users,           color: '#ffd166', agent: 'Care' },
  { href: '/departments',    label: 'Departments',    icon: Building2,       color: '#4ecdc4', agent: 'Programs' },
  { href: '/announcements',  label: 'Announcements',  icon: Megaphone,       color: '#a8dadc', agent: 'Comms' },
  { href: '/security',       label: 'Security',       icon: Shield,          color: '#f4a261', agent: 'Audit' },
  { href: '/secretariat',    label: 'Secretariat',    icon: FileText,        color: '#e76f51', agent: 'Records' },
  { href: '/logs',           label: 'Agent Logs',     icon: ScrollText,      color: '#8892b0', agent: 'All Agents' },
  { href: '/settings',       label: 'Settings',       icon: Settings,        color: '#8892b0', agent: 'Schedules' },
]

export function Sidebar() {
  const pathname = usePathname()

  return (
    <aside className="w-60 flex-shrink-0 border-r border-slate-800 bg-[#1a1d27] flex flex-col">
      {/* Logo */}
      <div className="p-5 border-b border-slate-800">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-[#6c63ff] flex items-center justify-content text-white text-sm font-bold flex items-center justify-center">
            CA
          </div>
          <div>
            <p className="text-sm font-bold text-white">Church Agents</p>
            <p className="text-xs text-slate-500">AI Support System</p>
          </div>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 p-3 space-y-0.5 overflow-y-auto">
        {nav.map((item) => {
          const Icon = item.icon
          const active = pathname === item.href
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-all group',
                active
                  ? 'bg-[#21253a] text-white'
                  : 'text-slate-400 hover:text-white hover:bg-[#21253a]'
              )}
            >
              <Icon
                size={16}
                style={{ color: active ? item.color : undefined }}
                className={active ? '' : 'group-hover:text-slate-300'}
              />
              <span className="flex-1">{item.label}</span>
              <span
                className="text-[10px] font-semibold px-1.5 py-0.5 rounded"
                style={{
                  background: active ? `${item.color}22` : 'transparent',
                  color: active ? item.color : 'transparent',
                }}
              >
                {item.agent}
              </span>
            </Link>
          )
        })}
      </nav>

      {/* Footer */}
      <div className="p-4 border-t border-slate-800">
        <p className="text-xs text-slate-600">8 agents active</p>
        <div className="flex gap-1 mt-2">
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="w-2 h-2 rounded-full bg-[#00d4aa]" />
          ))}
        </div>
      </div>
    </aside>
  )
}
```

---

## 11. Shared Components

### `src/components/stat-card.tsx`

```typescript
import { Card, CardContent } from '@/components/ui/card'
import { LucideIcon } from 'lucide-react'
import { cn } from '@/lib/utils'

interface StatCardProps {
  title: string
  value: string | number
  subtitle?: string
  icon: LucideIcon
  color: string
  trend?: { value: number; label: string }
}

export function StatCard({ title, value, subtitle, icon: Icon, color, trend }: StatCardProps) {
  return (
    <Card className="bg-[#1a1d27] border-slate-800">
      <CardContent className="p-5">
        <div className="flex items-start justify-between">
          <div>
            <p className="text-xs text-slate-500 uppercase tracking-wider font-semibold">{title}</p>
            <p className="text-2xl font-bold text-white mt-1">{value}</p>
            {subtitle && <p className="text-xs text-slate-500 mt-1">{subtitle}</p>}
            {trend && (
              <p className={cn('text-xs mt-2 font-medium', trend.value >= 0 ? 'text-[#00d4aa]' : 'text-[#ff6b6b]')}>
                {trend.value >= 0 ? '↑' : '↓'} {Math.abs(trend.value)}% {trend.label}
              </p>
            )}
          </div>
          <div
            className="w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0"
            style={{ background: `${color}22` }}
          >
            <Icon size={18} style={{ color }} />
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
```

### `src/components/page-header.tsx`

```typescript
import { LucideIcon } from 'lucide-react'
import { Badge } from '@/components/ui/badge'

interface PageHeaderProps {
  title: string
  description: string
  icon: LucideIcon
  color: string
  agentName: string
  lastRun?: string
}

export function PageHeader({ title, description, icon: Icon, color, agentName, lastRun }: PageHeaderProps) {
  return (
    <div className="flex items-start justify-between mb-6">
      <div className="flex items-center gap-4">
        <div
          className="w-11 h-11 rounded-xl flex items-center justify-center"
          style={{ background: `${color}22`, border: `1px solid ${color}44` }}
        >
          <Icon size={20} style={{ color }} />
        </div>
        <div>
          <h1 className="text-xl font-bold text-white">{title}</h1>
          <p className="text-sm text-slate-400 mt-0.5">{description}</p>
        </div>
      </div>
      <div className="flex items-center gap-2">
        <Badge variant="outline" className="text-xs border-slate-700 text-slate-400">
          {agentName}
        </Badge>
        {lastRun && (
          <span className="text-xs text-slate-600">Last run: {lastRun}</span>
        )}
      </div>
    </div>
  )
}
```

### `src/components/agent-status-card.tsx`

```typescript
import { Card, CardContent } from '@/components/ui/card'
import { AgentSchedule } from '@/lib/types'
import { formatDistanceToNow } from 'date-fns'
import { cn } from '@/lib/utils'

const AGENT_COLORS: Record<string, string> = {
  OrchestratorAgent:          '#6c63ff',
  SubscriptionWatchdogAgent:  '#ff6b6b',
  TreasuryHealthAgent:        '#00d4aa',
  MemberCareAgent:            '#ffd166',
  DepartmentProgramAgent:     '#4ecdc4',
  AnnouncementAgent:          '#a8dadc',
  AuditSecurityAgent:         '#f4a261',
  SecretariatAgent:           '#e76f51',
}

export function AgentStatusCard({ schedule }: { schedule: AgentSchedule }) {
  const color = AGENT_COLORS[schedule.agent_name] || '#8892b0'
  const isOk = schedule.last_status === 'SUCCESS' || !schedule.last_status
  const shortName = schedule.agent_name.replace('Agent', '').replace(/([A-Z])/g, ' $1').trim()

  return (
    <Card className={cn('bg-[#1a1d27] border-slate-800', !schedule.is_enabled && 'opacity-50')}>
      <CardContent className="p-4">
        <div className="flex items-center gap-2 mb-3">
          <div
            className={cn('w-2 h-2 rounded-full', schedule.is_enabled ? 'animate-pulse' : '')}
            style={{ background: schedule.is_enabled ? color : '#4b5563' }}
          />
          <p className="text-xs font-semibold text-white truncate">{shortName}</p>
        </div>
        <div className="space-y-1">
          <div className="flex justify-between text-xs">
            <span className="text-slate-500">Status</span>
            <span className={isOk ? 'text-[#00d4aa]' : 'text-[#ff6b6b]'}>
              {schedule.last_status || 'Never run'}
            </span>
          </div>
          <div className="flex justify-between text-xs">
            <span className="text-slate-500">Last run</span>
            <span className="text-slate-400">
              {schedule.last_run
                ? formatDistanceToNow(new Date(schedule.last_run), { addSuffix: true })
                : '—'}
            </span>
          </div>
          <div className="flex justify-between text-xs">
            <span className="text-slate-500">Schedule</span>
            <span className="text-slate-400 font-mono text-[10px]">{schedule.cron_expr}</span>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
```

---

## 12. Dashboard Page — `src/app/page.tsx`

```typescript
'use client'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { StatCard } from '@/components/stat-card'
import { AgentStatusCard } from '@/components/agent-status-card'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { LayoutDashboard, Church, CreditCard, AlertTriangle, XCircle, Users } from 'lucide-react'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts'
import { formatDistanceToNow } from 'date-fns'
import { AgentLog, AgentSchedule } from '@/lib/types'

const mockChartData = [
  { day: 'Mon', actions: 42 }, { day: 'Tue', actions: 58 },
  { day: 'Wed', actions: 35 }, { day: 'Thu', actions: 71 },
  { day: 'Fri', actions: 49 }, { day: 'Sat', actions: 28 },
  { day: 'Sun', actions: 63 },
]

export default function DashboardPage() {
  const { data: churches, isLoading: loadingChurches } = useQuery({
    queryKey: ['churches'],
    queryFn: () => api.getChurches(),
  })

  const { data: logs, isLoading: loadingLogs } = useQuery({
    queryKey: ['agent-logs'],
    queryFn: () => api.getAgentLogs({ limit: '10' }),
    refetchInterval: 30_000,
  })

  const { data: schedules, isLoading: loadingSchedules } = useQuery({
    queryKey: ['agent-schedules'],
    queryFn: () => api.getAgentSchedules(),
  })

  const churchList = churches?.results || []
  const logList: AgentLog[] = logs?.results || []
  const scheduleList: AgentSchedule[] = schedules?.results || []

  const stats = {
    total: churchList.length,
    active: churchList.filter((c: any) => c.subscription_status === 'ACTIVE').length,
    expiring: churchList.filter((c: any) => {
      if (!c.subscription_ends_at) return false
      const days = (new Date(c.subscription_ends_at).getTime() - Date.now()) / 86400000
      return days <= 7 && days >= 0
    }).length,
    suspended: churchList.filter((c: any) => !c.platform_access_enabled).length,
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl bg-[#6c63ff22] border border-[#6c63ff44] flex items-center justify-center">
          <LayoutDashboard size={18} className="text-[#6c63ff]" />
        </div>
        <div>
          <h1 className="text-xl font-bold text-white">Dashboard</h1>
          <p className="text-sm text-slate-400">Platform overview — all agents</p>
        </div>
      </div>

      {/* Stat Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {loadingChurches ? (
          Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-24 bg-slate-800" />)
        ) : (
          <>
            <StatCard title="Total Churches" value={stats.total} icon={Church} color="#6c63ff" />
            <StatCard title="Active Subscriptions" value={stats.active} icon={CreditCard} color="#00d4aa" />
            <StatCard title="Expiring This Week" value={stats.expiring} icon={AlertTriangle} color="#ffd166" />
            <StatCard title="Suspended" value={stats.suspended} icon={XCircle} color="#ff6b6b" />
          </>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Agent Actions Chart */}
        <Card className="lg:col-span-2 bg-[#1a1d27] border-slate-800">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-semibold text-white">Agent Actions — Last 7 Days</CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={200}>
              <LineChart data={mockChartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#2e3250" />
                <XAxis dataKey="day" tick={{ fill: '#8892b0', fontSize: 11 }} />
                <YAxis tick={{ fill: '#8892b0', fontSize: 11 }} />
                <Tooltip
                  contentStyle={{ background: '#21253a', border: '1px solid #2e3250', borderRadius: 8 }}
                  labelStyle={{ color: '#fff' }}
                />
                <Line type="monotone" dataKey="actions" stroke="#6c63ff" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        {/* Recent Alerts */}
        <Card className="bg-[#1a1d27] border-slate-800">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-semibold text-white">Recent Activity</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {loadingLogs
              ? Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-8 bg-slate-800" />)
              : logList.slice(0, 6).map((log) => (
                  <div key={log.id} className="flex items-center gap-2 py-1">
                    <div className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${
                      log.status === 'SUCCESS' ? 'bg-[#00d4aa]' :
                      log.status === 'FAILED' ? 'bg-[#ff6b6b]' : 'bg-[#8892b0]'
                    }`} />
                    <div className="min-w-0 flex-1">
                      <p className="text-xs text-slate-300 truncate">{log.agent_name.replace('Agent', '')}</p>
                      <p className="text-[10px] text-slate-600 truncate">{log.action}</p>
                    </div>
                    <span className="text-[10px] text-slate-600 flex-shrink-0">
                      {formatDistanceToNow(new Date(log.created_at), { addSuffix: true })}
                    </span>
                  </div>
                ))
            }
          </CardContent>
        </Card>
      </div>

      {/* Agent Status Grid */}
      <div>
        <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-3">Agent Status</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {loadingSchedules
            ? Array.from({ length: 8 }).map((_, i) => <Skeleton key={i} className="h-28 bg-slate-800" />)
            : scheduleList.map((s) => <AgentStatusCard key={s.id} schedule={s} />)
          }
        </div>
      </div>
    </div>
  )
}
```

---

## 13. Ask AI Page — `src/app/ask/page.tsx`

```typescript
'use client'
import { useState, useRef, useEffect } from 'react'
import { api } from '@/lib/api'
import { ChatMessage } from '@/lib/types'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card } from '@/components/ui/card'
import { MessageSquare, Send, Loader2, Bot, User } from 'lucide-react'
import { cn } from '@/lib/utils'

const SUGGESTIONS = [
  'Which churches are expiring this week?',
  'How many members joined last month?',
  'Show me the financial health summary',
  'Are there any security alerts today?',
  'Which programs are waiting for approval?',
  'Generate a daily briefing',
]

export default function AskPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const sessionId = useRef(`session-${Date.now()}`)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  async function send(question: string) {
    if (!question.trim() || loading) return
    const q = question.trim()
    setInput('')
    setMessages(prev => [...prev, { role: 'user', content: q, timestamp: new Date().toISOString() }])
    setLoading(true)
    try {
      const res = await api.askAgent(q, sessionId.current)
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: res.answer || res.response || 'No response from agent.',
        timestamp: new Date().toISOString(),
      }])
    } catch {
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: 'Error: Could not reach the agent. Make sure the agents server is running.',
        timestamp: new Date().toISOString(),
      }])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex flex-col h-[calc(100vh-3rem)] space-y-4">
      {/* Header */}
      <div className="flex items-center gap-3 flex-shrink-0">
        <div className="w-10 h-10 rounded-xl bg-[#6c63ff22] border border-[#6c63ff44] flex items-center justify-center">
          <MessageSquare size={18} className="text-[#6c63ff]" />
        </div>
        <div>
          <h1 className="text-xl font-bold text-white">Ask AI</h1>
          <p className="text-sm text-slate-400">OrchestratorAgent — ask anything about your platform</p>
        </div>
      </div>

      {/* Chat window */}
      <Card className="flex-1 bg-[#1a1d27] border-slate-800 flex flex-col min-h-0">
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {messages.length === 0 && (
            <div className="flex flex-col items-center justify-center h-full text-center gap-4">
              <div className="w-16 h-16 rounded-2xl bg-[#6c63ff22] flex items-center justify-center">
                <Bot size={28} className="text-[#6c63ff]" />
              </div>
              <div>
                <p className="text-white font-semibold">Church Agent AI</p>
                <p className="text-slate-400 text-sm mt-1">Ask me anything about your churches, members, finances, or agents.</p>
              </div>
              <div className="flex flex-wrap gap-2 justify-center max-w-lg">
                {SUGGESTIONS.map((s) => (
                  <button
                    key={s}
                    onClick={() => send(s)}
                    className="text-xs px-3 py-1.5 rounded-full border border-slate-700 text-slate-400 hover:border-[#6c63ff] hover:text-[#6c63ff] transition-colors"
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((msg, i) => (
            <div key={i} className={cn('flex gap-3', msg.role === 'user' ? 'justify-end' : 'justify-start')}>
              {msg.role === 'assistant' && (
                <div className="w-7 h-7 rounded-lg bg-[#6c63ff22] flex items-center justify-center flex-shrink-0 mt-0.5">
                  <Bot size={14} className="text-[#6c63ff]" />
                </div>
              )}
              <div className={cn(
                'max-w-[75%] rounded-2xl px-4 py-2.5 text-sm',
                msg.role === 'user'
                  ? 'bg-[#6c63ff] text-white rounded-tr-sm'
                  : 'bg-[#21253a] text-slate-200 rounded-tl-sm'
              )}>
                <p className="whitespace-pre-wrap">{msg.content}</p>
              </div>
              {msg.role === 'user' && (
                <div className="w-7 h-7 rounded-lg bg-slate-700 flex items-center justify-center flex-shrink-0 mt-0.5">
                  <User size={14} className="text-slate-300" />
                </div>
              )}
            </div>
          ))}

          {loading && (
            <div className="flex gap-3">
              <div className="w-7 h-7 rounded-lg bg-[#6c63ff22] flex items-center justify-center flex-shrink-0">
                <Bot size={14} className="text-[#6c63ff]" />
              </div>
              <div className="bg-[#21253a] rounded-2xl rounded-tl-sm px-4 py-3">
                <Loader2 size={14} className="animate-spin text-[#6c63ff]" />
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        {/* Input */}
        <div className="p-4 border-t border-slate-800">
          <form onSubmit={(e) => { e.preventDefault(); send(input) }} className="flex gap-2">
            <Input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask anything about your church platform..."
              className="flex-1 bg-[#21253a] border-slate-700 text-white placeholder:text-slate-600"
            />
            <Button type="submit" disabled={!input.trim() || loading}
              className="bg-[#6c63ff] hover:bg-[#5a52e8] text-white">
              <Send size={15} />
            </Button>
          </form>
        </div>
      </Card>
    </div>
  )
}
```

---

## 14. Subscriptions Page — `src/app/subscriptions/page.tsx`

```typescript
'use client'
import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { Church } from '@/lib/types'
import { StatCard } from '@/components/stat-card'
import { PageHeader } from '@/components/page-header'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { CreditCard, AlertTriangle, XCircle, CheckCircle, Send, Lock, Unlock } from 'lucide-react'
import { formatDistanceToNow } from 'date-fns'

function planBadge(plan: string) {
  const map: Record<string, string> = {
    FREE: 'bg-slate-700 text-slate-300',
    TRIAL: 'bg-[#ffd16622] text-[#ffd166] border border-[#ffd16644]',
    BASIC: 'bg-[#6c63ff22] text-[#6c63ff] border border-[#6c63ff44]',
    PREMIUM: 'bg-[#00d4aa22] text-[#00d4aa] border border-[#00d4aa44]',
    ENTERPRISE: 'bg-[#f4a26122] text-[#f4a261] border border-[#f4a26144]',
  }
  return map[plan] || 'bg-slate-700 text-slate-300'
}

function statusBadge(status: string, enabled: boolean) {
  if (!enabled) return 'bg-[#ff6b6b22] text-[#ff6b6b] border border-[#ff6b6b44]'
  const map: Record<string, string> = {
    ACTIVE: 'bg-[#00d4aa22] text-[#00d4aa] border border-[#00d4aa44]',
    TRIAL: 'bg-[#ffd16622] text-[#ffd166] border border-[#ffd16644]',
    EXPIRED: 'bg-[#ff6b6b22] text-[#ff6b6b] border border-[#ff6b6b44]',
  }
  return map[status] || 'bg-slate-700 text-slate-300'
}

export default function SubscriptionsPage() {
  const [filter, setFilter] = useState('all')
  const qc = useQueryClient()

  const { data, isLoading } = useQuery({
    queryKey: ['churches'],
    queryFn: () => api.getChurches(),
    refetchInterval: 60_000,
  })

  const disable = useMutation({
    mutationFn: (id: number) => api.disableChurch(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['churches'] }),
  })

  const reinstate = useMutation({
    mutationFn: (id: number) => api.reinstateChurch(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['churches'] }),
  })

  const remind = useMutation({
    mutationFn: (id: number) => api.sendRenewalReminder(id),
  })

  const all: Church[] = data?.results || []
  const now = Date.now()

  const filtered = all.filter((c) => {
    if (filter === 'trial') return c.plan === 'TRIAL'
    if (filter === 'expiring') {
      const days = c.subscription_ends_at
        ? (new Date(c.subscription_ends_at).getTime() - now) / 86400000
        : Infinity
      return days <= 7 && days >= 0
    }
    if (filter === 'suspended') return !c.platform_access_enabled
    return true
  })

  const stats = {
    total: all.length,
    active: all.filter(c => c.subscription_status === 'ACTIVE').length,
    trial: all.filter(c => c.plan === 'TRIAL').length,
    expiring: all.filter(c => {
      const days = c.subscription_ends_at
        ? (new Date(c.subscription_ends_at).getTime() - now) / 86400000 : Infinity
      return days <= 7 && days >= 0
    }).length,
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Subscriptions"
        description="SubscriptionWatchdogAgent — monitor church plans and billing"
        icon={CreditCard}
        color="#ff6b6b"
        agentName="SubscriptionWatchdogAgent"
      />

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {isLoading ? Array.from({length:4}).map((_,i) => <Skeleton key={i} className="h-24 bg-slate-800"/>) : <>
          <StatCard title="Total Churches" value={stats.total} icon={CreditCard} color="#6c63ff" />
          <StatCard title="Active" value={stats.active} icon={CheckCircle} color="#00d4aa" />
          <StatCard title="Trial" value={stats.trial} icon={AlertTriangle} color="#ffd166" />
          <StatCard title="Expiring ≤7 days" value={stats.expiring} icon={XCircle} color="#ff6b6b" />
        </>}
      </div>

      <Card className="bg-[#1a1d27] border-slate-800">
        <CardContent className="p-0">
          <div className="p-4 border-b border-slate-800">
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
                  {['Church', 'Plan', 'Status', 'Expires', 'Admin Email', 'Actions'].map(h => (
                    <th key={h} className="text-left text-xs text-slate-500 uppercase tracking-wider px-4 py-3 font-semibold">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {isLoading
                  ? Array.from({length:6}).map((_,i) => (
                      <tr key={i}><td colSpan={6} className="px-4 py-3"><Skeleton className="h-6 bg-slate-800"/></td></tr>
                    ))
                  : filtered.map((church) => {
                      const daysLeft = church.subscription_ends_at
                        ? Math.ceil((new Date(church.subscription_ends_at).getTime() - now) / 86400000) : null

                      return (
                        <tr key={church.id} className="border-b border-slate-800/50 hover:bg-[#21253a] transition-colors">
                          <td className="px-4 py-3">
                            <div>
                              <p className="text-white font-medium">{church.name}</p>
                              <p className="text-xs text-slate-500">{church.member_count} members</p>
                            </div>
                          </td>
                          <td className="px-4 py-3">
                            <span className={`text-xs font-semibold px-2 py-1 rounded-full ${planBadge(church.plan)}`}>
                              {church.plan}
                            </span>
                          </td>
                          <td className="px-4 py-3">
                            <span className={`text-xs font-semibold px-2 py-1 rounded-full ${statusBadge(church.subscription_status, church.platform_access_enabled)}`}>
                              {!church.platform_access_enabled ? 'SUSPENDED' : church.subscription_status}
                            </span>
                          </td>
                          <td className="px-4 py-3 text-xs text-slate-400">
                            {daysLeft !== null ? (
                              <span className={daysLeft <= 3 ? 'text-[#ff6b6b]' : daysLeft <= 7 ? 'text-[#ffd166]' : 'text-slate-400'}>
                                {daysLeft > 0 ? `${daysLeft}d left` : 'Expired'}
                              </span>
                            ) : '—'}
                          </td>
                          <td className="px-4 py-3 text-xs text-slate-400">{church.admin_email}</td>
                          <td className="px-4 py-3">
                            <div className="flex gap-1">
                              <Button size="sm" variant="ghost"
                                className="h-7 px-2 text-xs text-slate-400 hover:text-white"
                                onClick={() => remind.mutate(church.id)}>
                                <Send size={11} className="mr-1" /> Remind
                              </Button>
                              {church.platform_access_enabled ? (
                                <Button size="sm" variant="ghost"
                                  className="h-7 px-2 text-xs text-[#ff6b6b] hover:text-white hover:bg-[#ff6b6b22]"
                                  onClick={() => disable.mutate(church.id)}>
                                  <Lock size={11} className="mr-1" /> Disable
                                </Button>
                              ) : (
                                <Button size="sm" variant="ghost"
                                  className="h-7 px-2 text-xs text-[#00d4aa] hover:text-white hover:bg-[#00d4aa22]"
                                  onClick={() => reinstate.mutate(church.id)}>
                                  <Unlock size={11} className="mr-1" /> Reinstate
                                </Button>
                              )}
                            </div>
                          </td>
                        </tr>
                      )
                    })
                }
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
```

---

## 15. Treasury Page — `src/app/treasury/page.tsx`

```typescript
'use client'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { StatCard } from '@/components/stat-card'
import { PageHeader } from '@/components/page-header'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { DollarSign, TrendingUp, Clock, AlertCircle, Send } from 'lucide-react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Legend } from 'recharts'

const mockIncomeExpense = [
  { month: 'Nov', income: 12400, expenses: 8200 },
  { month: 'Dec', income: 18900, expenses: 11300 },
  { month: 'Jan', income: 14200, expenses: 9800 },
  { month: 'Feb', income: 16700, expenses: 10100 },
  { month: 'Mar', income: 21300, expenses: 12800 },
  { month: 'Apr', income: 19500, expenses: 11900 },
]

export default function TreasuryPage() {
  const { data: stats, isLoading: loadingStats } = useQuery({
    queryKey: ['treasury-stats'],
    queryFn: () => api.getTreasuryStats(),
  })

  const { data: stalled, isLoading: loadingStalled } = useQuery({
    queryKey: ['stalled-expenses'],
    queryFn: () => api.getStalledExpenses(),
  })

  const stalledList = stalled?.results || []

  return (
    <div className="space-y-6">
      <PageHeader
        title="Treasury Health"
        description="TreasuryHealthAgent — financial monitoring and expense approvals"
        icon={DollarSign}
        color="#00d4aa"
        agentName="TreasuryHealthAgent"
      />

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {loadingStats ? Array.from({length:4}).map((_,i) => <Skeleton key={i} className="h-24 bg-slate-800"/>) : <>
          <StatCard title="Income This Month" value={`GHS ${(stats?.total_income_month || 0).toLocaleString()}`} icon={TrendingUp} color="#00d4aa" />
          <StatCard title="Expenses This Month" value={`GHS ${(stats?.total_expenses_month || 0).toLocaleString()}`} icon={DollarSign} color="#ffd166" />
          <StatCard title="Pending Requests" value={stats?.pending_requests || 0} icon={Clock} color="#f4a261" />
          <StatCard title="Stalled (>48h)" value={stats?.stalled_requests || 0} icon={AlertCircle} color="#ff6b6b" />
        </>}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Income vs Expenses Chart */}
        <Card className="bg-[#1a1d27] border-slate-800">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-semibold text-white">Income vs Expenses — 6 Months</CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={mockIncomeExpense} barGap={4}>
                <CartesianGrid strokeDasharray="3 3" stroke="#2e3250" />
                <XAxis dataKey="month" tick={{ fill: '#8892b0', fontSize: 11 }} />
                <YAxis tick={{ fill: '#8892b0', fontSize: 11 }} tickFormatter={v => `${(v/1000).toFixed(0)}k`} />
                <Tooltip
                  contentStyle={{ background: '#21253a', border: '1px solid #2e3250', borderRadius: 8 }}
                  formatter={(v: number) => [`GHS ${v.toLocaleString()}`, '']}
                />
                <Legend wrapperStyle={{ fontSize: 11, color: '#8892b0' }} />
                <Bar dataKey="income" fill="#00d4aa" radius={[4,4,0,0]} name="Income" />
                <Bar dataKey="expenses" fill="#ff6b6b" radius={[4,4,0,0]} name="Expenses" />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        {/* Stalled Requests */}
        <Card className="bg-[#1a1d27] border-slate-800">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-semibold text-white">Stalled Expense Requests</CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            {loadingStalled ? (
              <div className="p-4 space-y-2">{Array.from({length:4}).map((_,i)=><Skeleton key={i} className="h-12 bg-slate-800"/>)}</div>
            ) : stalledList.length === 0 ? (
              <div className="p-8 text-center text-sm text-slate-500">No stalled requests</div>
            ) : (
              <div className="divide-y divide-slate-800">
                {stalledList.map((req: any) => (
                  <div key={req.id} className="flex items-center gap-3 px-4 py-3 hover:bg-[#21253a]">
                    <div className="flex-1 min-w-0">
                      <p className="text-sm text-white truncate">{req.title}</p>
                      <p className="text-xs text-slate-500">{req.church_name} · {req.department_name}</p>
                    </div>
                    <div className="text-right flex-shrink-0">
                      <p className="text-sm font-semibold text-[#ffd166]">GHS {Number(req.amount).toLocaleString()}</p>
                      <p className="text-xs text-[#ff6b6b]">{req.hours_stalled}h stalled</p>
                    </div>
                    <Button size="sm" variant="ghost" className="h-7 px-2 text-xs text-slate-400">
                      <Send size={11} />
                    </Button>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
```

---

## 16. Members Page — `src/app/members/page.tsx`

```typescript
'use client'
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { StatCard } from '@/components/stat-card'
import { PageHeader } from '@/components/page-header'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Users, UserPlus, UserX, Gift, Send } from 'lucide-react'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts'

const growthData = [
  { month: 'Nov', members: 840 }, { month: 'Dec', members: 890 },
  { month: 'Jan', members: 920 }, { month: 'Feb', members: 968 },
  { month: 'Mar', members: 1010 }, { month: 'Apr', members: 1054 },
]

const statusColor: Record<string, string> = {
  ACTIVE: 'bg-[#00d4aa22] text-[#00d4aa]',
  INACTIVE: 'bg-[#ff6b6b22] text-[#ff6b6b]',
  VISITOR: 'bg-[#ffd16622] text-[#ffd166]',
  TRANSFER: 'bg-[#f4a26122] text-[#f4a261]',
  NEW_CONVERT: 'bg-[#6c63ff22] text-[#6c63ff]',
}

export default function MembersPage() {
  const [tab, setTab] = useState('active')

  const { data: members, isLoading } = useQuery({
    queryKey: ['members', tab],
    queryFn: () => {
      if (tab === 'visitors') return api.getVisitors()
      if (tab === 'inactive') return api.getMembers({ inactive_days: '30' })
      return api.getMembers({ status: 'ACTIVE' })
    },
  })

  const list = members?.results || []

  return (
    <div className="space-y-6">
      <PageHeader
        title="Member Care"
        description="MemberCareAgent — birthdays, visitors, inactive member engagement"
        icon={Users}
        color="#ffd166"
        agentName="MemberCareAgent"
      />

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard title="Total Members" value={members?.count || 0} icon={Users} color="#ffd166" />
        <StatCard title="New This Month" value="42" icon={UserPlus} color="#6c63ff" />
        <StatCard title="Visitors" value="18" icon={Gift} color="#f4a261" />
        <StatCard title="Inactive (30d+)" value="31" icon={UserX} color="#ff6b6b" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card className="lg:col-span-1 bg-[#1a1d27] border-slate-800">
          <div className="p-4 border-b border-slate-800">
            <p className="text-sm font-semibold text-white">Member Growth</p>
          </div>
          <CardContent className="pt-4">
            <ResponsiveContainer width="100%" height={160}>
              <LineChart data={growthData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#2e3250" />
                <XAxis dataKey="month" tick={{ fill: '#8892b0', fontSize: 10 }} />
                <YAxis tick={{ fill: '#8892b0', fontSize: 10 }} />
                <Tooltip contentStyle={{ background: '#21253a', border: '1px solid #2e3250', borderRadius: 8 }} />
                <Line type="monotone" dataKey="members" stroke="#ffd166" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        <Card className="lg:col-span-2 bg-[#1a1d27] border-slate-800">
          <div className="p-4 border-b border-slate-800">
            <Tabs value={tab} onValueChange={setTab}>
              <TabsList className="bg-[#21253a]">
                <TabsTrigger value="active">Active Members</TabsTrigger>
                <TabsTrigger value="visitors">Visitors</TabsTrigger>
                <TabsTrigger value="inactive">Inactive</TabsTrigger>
              </TabsList>
            </Tabs>
          </div>
          <CardContent className="p-0">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-800">
                  {['Name', 'Church', 'Status', 'Joined', 'Action'].map(h => (
                    <th key={h} className="text-left text-xs text-slate-500 uppercase tracking-wider px-4 py-3 font-semibold">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {isLoading
                  ? Array.from({length:5}).map((_,i)=>(
                      <tr key={i}><td colSpan={5} className="px-4 py-3"><Skeleton className="h-6 bg-slate-800"/></td></tr>
                    ))
                  : list.map((m: any) => (
                      <tr key={m.id} className="border-b border-slate-800/50 hover:bg-[#21253a]">
                        <td className="px-4 py-3">
                          <p className="text-white font-medium">{m.first_name} {m.last_name}</p>
                          <p className="text-xs text-slate-500">{m.email}</p>
                        </td>
                        <td className="px-4 py-3 text-xs text-slate-400">{m.church_name}</td>
                        <td className="px-4 py-3">
                          <span className={`text-xs font-semibold px-2 py-1 rounded-full ${statusColor[m.status] || 'bg-slate-700 text-slate-300'}`}>
                            {m.status}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-xs text-slate-400">
                          {m.created_at ? new Date(m.created_at).toLocaleDateString() : '—'}
                        </td>
                        <td className="px-4 py-3">
                          <Button size="sm" variant="ghost" className="h-7 px-2 text-xs text-slate-400"
                            onClick={() => api.sendBirthdayEmail(m.id)}>
                            <Send size={11} className="mr-1" />
                            {tab === 'inactive' ? 'Follow Up' : tab === 'visitors' ? 'Follow Up' : 'Email'}
                          </Button>
                        </td>
                      </tr>
                    ))
                }
              </tbody>
            </table>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
```

---

## 17. Departments Page — `src/app/departments/page.tsx`

```typescript
'use client'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { StatCard } from '@/components/stat-card'
import { PageHeader } from '@/components/page-header'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { Building2, Clock, Calendar, CheckCircle, Send } from 'lucide-react'

export default function DepartmentsPage() {
  const { data: stalled, isLoading: loadingStalled } = useQuery({
    queryKey: ['stalled-programs'],
    queryFn: () => api.getStalledPrograms(),
  })
  const { data: activities, isLoading: loadingAct } = useQuery({
    queryKey: ['upcoming-activities'],
    queryFn: () => api.getUpcomingActivities(),
  })

  const stalledList = stalled?.results || []
  const actList = activities?.results || []

  return (
    <div className="space-y-6">
      <PageHeader
        title="Departments & Programs"
        description="DepartmentProgramAgent — program approvals and activity reminders"
        icon={Building2}
        color="#4ecdc4"
        agentName="DepartmentProgramAgent"
      />

      <div className="grid grid-cols-3 gap-4">
        <StatCard title="Active Programs" value={stalled?.active_count || 0} icon={CheckCircle} color="#4ecdc4" />
        <StatCard title="Stalled Programs" value={stalledList.length} icon={Clock} color="#ff6b6b" />
        <StatCard title="Activities This Week" value={actList.length} icon={Calendar} color="#ffd166" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Stalled Programs */}
        <Card className="bg-[#1a1d27] border-slate-800">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-semibold text-white">Stalled Program Approvals</CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            {loadingStalled
              ? <div className="p-4 space-y-2">{Array.from({length:4}).map((_,i)=><Skeleton key={i} className="h-12 bg-slate-800"/>)}</div>
              : stalledList.length === 0
              ? <div className="p-8 text-center text-sm text-slate-500">No stalled programs</div>
              : <div className="divide-y divide-slate-800">
                  {stalledList.map((p: any) => (
                    <div key={p.id} className="flex items-center gap-3 px-4 py-3 hover:bg-[#21253a]">
                      <div className="flex-1 min-w-0">
                        <p className="text-sm text-white truncate">{p.title}</p>
                        <p className="text-xs text-slate-500">{p.church_name} · {p.department_name}</p>
                      </div>
                      <div className="text-right flex-shrink-0">
                        <p className="text-xs text-slate-400">{p.approval_stage}</p>
                        <p className="text-xs text-[#ff6b6b]">{p.hours_stalled}h stalled</p>
                      </div>
                      <Button size="sm" variant="ghost" className="h-7 px-2 text-slate-400 hover:text-white">
                        <Send size={11} />
                      </Button>
                    </div>
                  ))}
                </div>
            }
          </CardContent>
        </Card>

        {/* Upcoming Activities */}
        <Card className="bg-[#1a1d27] border-slate-800">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-semibold text-white">Upcoming Activities (7 days)</CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            {loadingAct
              ? <div className="p-4 space-y-2">{Array.from({length:4}).map((_,i)=><Skeleton key={i} className="h-12 bg-slate-800"/>)}</div>
              : actList.length === 0
              ? <div className="p-8 text-center text-sm text-slate-500">No upcoming activities</div>
              : <div className="divide-y divide-slate-800">
                  {actList.map((a: any) => (
                    <div key={a.id} className="flex items-center gap-3 px-4 py-3 hover:bg-[#21253a]">
                      <div className="w-10 h-10 rounded-lg bg-[#4ecdc422] flex flex-col items-center justify-center flex-shrink-0">
                        <p className="text-[10px] text-[#4ecdc4] font-bold leading-none">
                          {new Date(a.date).toLocaleDateString('en', { month: 'short' })}
                        </p>
                        <p className="text-sm text-[#4ecdc4] font-bold leading-none">
                          {new Date(a.date).getDate()}
                        </p>
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm text-white truncate">{a.title}</p>
                        <p className="text-xs text-slate-500">{a.church_name} · {a.department_name}</p>
                      </div>
                      <Button size="sm" variant="ghost" className="h-7 px-2 text-slate-400">
                        <Send size={11} />
                      </Button>
                    </div>
                  ))}
                </div>
            }
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
```

---

## 18. Announcements Page — `src/app/announcements/page.tsx`

```typescript
'use client'
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { StatCard } from '@/components/stat-card'
import { PageHeader } from '@/components/page-header'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Megaphone, Clock, CheckCircle, AlertTriangle, Send } from 'lucide-react'

const priorityColor: Record<string, string> = {
  LOW: 'bg-slate-700 text-slate-300',
  MEDIUM: 'bg-[#6c63ff22] text-[#6c63ff]',
  HIGH: 'bg-[#ffd16622] text-[#ffd166]',
  URGENT: 'bg-[#ff6b6b22] text-[#ff6b6b]',
}
const statusColor: Record<string, string> = {
  DRAFT: 'bg-slate-700 text-slate-400',
  PENDING_REVIEW: 'bg-[#ffd16622] text-[#ffd166]',
  APPROVED: 'bg-[#4ecdc422] text-[#4ecdc4]',
  PUBLISHED: 'bg-[#00d4aa22] text-[#00d4aa]',
}

export default function AnnouncementsPage() {
  const [filter, setFilter] = useState('PENDING_REVIEW')

  const { data, isLoading } = useQuery({
    queryKey: ['announcements', filter],
    queryFn: () => api.getAnnouncements(filter === 'ALL' ? undefined : filter),
    refetchInterval: 30_000,
  })

  const list = data?.results || []

  return (
    <div className="space-y-6">
      <PageHeader
        title="Announcements"
        description="AnnouncementAgent — publishing workflow, approval reminders, weekly digest"
        icon={Megaphone}
        color="#a8dadc"
        agentName="AnnouncementAgent"
      />

      <div className="grid grid-cols-3 gap-4">
        <StatCard title="Pending Review" value={data?.pending_count || 0} icon={Clock} color="#ffd166" />
        <StatCard title="Published This Week" value={data?.published_count || 0} icon={CheckCircle} color="#00d4aa" />
        <StatCard title="Urgent" value={data?.urgent_count || 0} icon={AlertTriangle} color="#ff6b6b" />
      </div>

      <Card className="bg-[#1a1d27] border-slate-800">
        <div className="p-4 border-b border-slate-800">
          <Tabs value={filter} onValueChange={setFilter}>
            <TabsList className="bg-[#21253a]">
              <TabsTrigger value="PENDING_REVIEW">Pending</TabsTrigger>
              <TabsTrigger value="PUBLISHED">Published</TabsTrigger>
              <TabsTrigger value="ALL">All</TabsTrigger>
            </TabsList>
          </Tabs>
        </div>
        <CardContent className="p-0">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-800">
                {['Title', 'Church', 'Category', 'Priority', 'Status', 'Created', 'Actions'].map(h => (
                  <th key={h} className="text-left text-xs text-slate-500 uppercase tracking-wider px-4 py-3 font-semibold">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {isLoading
                ? Array.from({length:5}).map((_,i)=>(
                    <tr key={i}><td colSpan={7} className="px-4 py-3"><Skeleton className="h-6 bg-slate-800"/></td></tr>
                  ))
                : list.map((ann: any) => (
                    <tr key={ann.id} className="border-b border-slate-800/50 hover:bg-[#21253a]">
                      <td className="px-4 py-3">
                        <p className="text-white font-medium truncate max-w-[180px]">{ann.title}</p>
                      </td>
                      <td className="px-4 py-3 text-xs text-slate-400">{ann.church_name}</td>
                      <td className="px-4 py-3 text-xs text-slate-400">{ann.category}</td>
                      <td className="px-4 py-3">
                        <span className={`text-xs font-semibold px-2 py-1 rounded-full ${priorityColor[ann.priority]}`}>
                          {ann.priority}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <span className={`text-xs font-semibold px-2 py-1 rounded-full ${statusColor[ann.status]}`}>
                          {ann.status.replace('_', ' ')}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-xs text-slate-400">
                        {new Date(ann.created_at).toLocaleDateString()}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex gap-1">
                          <Button size="sm" variant="ghost" className="h-7 px-2 text-xs text-[#00d4aa]">Approve</Button>
                          <Button size="sm" variant="ghost" className="h-7 px-2 text-xs text-slate-400">
                            <Send size={11} />
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))
              }
            </tbody>
          </table>
        </CardContent>
      </Card>
    </div>
  )
}
```

---

## 19. Security Page — `src/app/security/page.tsx`

```typescript
'use client'
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { StatCard } from '@/components/stat-card'
import { PageHeader } from '@/components/page-header'
import { Card, CardContent } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { Shield, Lock, AlertTriangle, UserX, Activity } from 'lucide-react'
import { formatDistanceToNow } from 'date-fns'

const actionColor: Record<string, string> = {
  DELETE: 'text-[#ff6b6b]',
  LOGIN_FAIL: 'text-[#ffd166]',
  PERMISSION_CHANGE: 'text-[#f4a261]',
  BULK_DELETE: 'text-[#ff6b6b]',
  LOGIN: 'text-[#00d4aa]',
  CREATE: 'text-[#6c63ff]',
  UPDATE: 'text-[#a8dadc]',
}

export default function SecurityPage() {
  const [actionFilter, setActionFilter] = useState('')

  const { data: logs, isLoading } = useQuery({
    queryKey: ['audit-logs', actionFilter],
    queryFn: () => api.getAuditLogs(actionFilter ? { action: actionFilter } : undefined),
    refetchInterval: 30_000,
  })

  const { data: locked } = useQuery({
    queryKey: ['locked-accounts'],
    queryFn: () => api.getLockedAccounts(),
  })

  const list = logs?.results || []
  const lockedList = locked?.results || []

  const filters = ['All', 'DELETE', 'LOGIN_FAIL', 'PERMISSION_CHANGE', 'BULK_DELETE']

  return (
    <div className="space-y-6">
      <PageHeader
        title="Audit & Security"
        description="AuditSecurityAgent — suspicious activity, locked accounts, compliance"
        icon={Shield}
        color="#f4a261"
        agentName="AuditSecurityAgent"
      />

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard title="Locked Accounts" value={lockedList.length} icon={Lock} color="#ff6b6b" />
        <StatCard title="Suspicious (24h)" value={list.filter((l: any) => ['DELETE','BULK_DELETE'].includes(l.action)).length} icon={AlertTriangle} color="#f4a261" />
        <StatCard title="Permission Changes" value={list.filter((l: any) => l.action === 'PERMISSION_CHANGE').length} icon={UserX} color="#ffd166" />
        <StatCard title="Total Events (today)" value={list.length} icon={Activity} color="#6c63ff" />
      </div>

      {/* Filter Bar */}
      <div className="flex gap-2">
        {filters.map((f) => (
          <button
            key={f}
            onClick={() => setActionFilter(f === 'All' ? '' : f)}
            className={`text-xs px-3 py-1.5 rounded-full border transition-colors ${
              (f === 'All' && !actionFilter) || actionFilter === f
                ? 'border-[#f4a261] text-[#f4a261] bg-[#f4a26122]'
                : 'border-slate-700 text-slate-400 hover:border-slate-600'
            }`}
          >
            {f}
          </button>
        ))}
      </div>

      <Card className="bg-[#1a1d27] border-slate-800">
        <CardContent className="p-0">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-800">
                {['User', 'Church', 'Action', 'Description', 'IP', 'Time'].map(h => (
                  <th key={h} className="text-left text-xs text-slate-500 uppercase tracking-wider px-4 py-3 font-semibold">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {isLoading
                ? Array.from({length:6}).map((_,i)=>(
                    <tr key={i}><td colSpan={6} className="px-4 py-3"><Skeleton className="h-6 bg-slate-800"/></td></tr>
                  ))
                : list.map((entry: any) => (
                    <tr key={entry.id} className="border-b border-slate-800/50 hover:bg-[#21253a]">
                      <td className="px-4 py-3 text-xs text-white">{entry.user_email || 'System'}</td>
                      <td className="px-4 py-3 text-xs text-slate-400">{entry.church_name || '—'}</td>
                      <td className={`px-4 py-3 text-xs font-semibold font-mono ${actionColor[entry.action] || 'text-slate-400'}`}>
                        {entry.action}
                      </td>
                      <td className="px-4 py-3 text-xs text-slate-400 max-w-[200px] truncate">{entry.description}</td>
                      <td className="px-4 py-3 text-xs text-slate-500 font-mono">{entry.ip_address || '—'}</td>
                      <td className="px-4 py-3 text-xs text-slate-500">
                        {formatDistanceToNow(new Date(entry.created_at), { addSuffix: true })}
                      </td>
                    </tr>
                  ))
              }
            </tbody>
          </table>
        </CardContent>
      </Card>
    </div>
  )
}
```

---

## 20. Secretariat Page — `src/app/secretariat/page.tsx`

```typescript
'use client'
import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { StatCard } from '@/components/stat-card'
import { PageHeader } from '@/components/page-header'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog'
import { FileText, Clock, Send, BookOpen, Plus } from 'lucide-react'

const docTypeLabel: Record<string, string> = {
  TRANSFER: 'Transfer Letter',
  CERTIFICATE: 'Membership Cert',
  RECOMMENDATION: 'Recommendation',
  BAPTISM: 'Baptism Cert',
  MARRIAGE: 'Marriage Record',
}
const statusColor: Record<string, string> = {
  PENDING: 'bg-[#ffd16622] text-[#ffd166]',
  IN_PROGRESS: 'bg-[#6c63ff22] text-[#6c63ff]',
  COMPLETED: 'bg-[#00d4aa22] text-[#00d4aa]',
}

export default function SecretariatPage() {
  const [tab, setTab] = useState('requests')
  const [destination, setDestination] = useState('')
  const [memberId, setMemberId] = useState('')
  const [churchId, setChurchId] = useState('')
  const qc = useQueryClient()

  const { data: requests, isLoading: loadingReq } = useQuery({
    queryKey: ['doc-requests'],
    queryFn: () => api.getDocumentRequests(),
  })

  const { data: minutes, isLoading: loadingMin } = useQuery({
    queryKey: ['meeting-minutes'],
    queryFn: () => api.getMeetingMinutes(),
  })

  const genLetter = useMutation({
    mutationFn: () => api.generateTransferLetter({
      member_id: Number(memberId),
      destination,
      church_id: Number(churchId),
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['doc-requests'] })
      setDestination('')
      setMemberId('')
    },
  })

  const reqList = requests?.results || []
  const minList = minutes?.results || []

  return (
    <div className="space-y-6">
      <PageHeader
        title="Secretariat"
        description="SecretariatAgent — official records, letters, meeting minutes, documents"
        icon={FileText}
        color="#e76f51"
        agentName="SecretariatAgent"
      />

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard title="Pending Requests" value={reqList.filter((r: any) => r.status === 'PENDING').length} icon={Clock} color="#ffd166" />
        <StatCard title="Meeting Minutes" value={minList.length} icon={BookOpen} color="#e76f51" />
        <StatCard title="Transfer Letters" value={requests?.transfer_count || 0} icon={FileText} color="#6c63ff" />
        <StatCard title="Completed" value={reqList.filter((r: any) => r.status === 'COMPLETED').length} icon={Send} color="#00d4aa" />
      </div>

      <Card className="bg-[#1a1d27] border-slate-800">
        <div className="p-4 border-b border-slate-800 flex items-center justify-between">
          <Tabs value={tab} onValueChange={setTab}>
            <TabsList className="bg-[#21253a]">
              <TabsTrigger value="requests">Document Requests</TabsTrigger>
              <TabsTrigger value="minutes">Meeting Minutes</TabsTrigger>
            </TabsList>
          </Tabs>

          {tab === 'requests' && (
            <Dialog>
              <DialogTrigger asChild>
                <Button size="sm" className="bg-[#e76f51] hover:bg-[#d4623d] text-white h-8">
                  <Plus size={13} className="mr-1.5" /> Transfer Letter
                </Button>
              </DialogTrigger>
              <DialogContent className="bg-[#1a1d27] border-slate-700">
                <DialogHeader>
                  <DialogTitle className="text-white">Generate Transfer Letter</DialogTitle>
                </DialogHeader>
                <div className="space-y-3 mt-2">
                  <div>
                    <label className="text-xs text-slate-400 mb-1 block">Member ID</label>
                    <Input value={memberId} onChange={e => setMemberId(e.target.value)}
                      placeholder="e.g. 42" className="bg-[#21253a] border-slate-700 text-white" />
                  </div>
                  <div>
                    <label className="text-xs text-slate-400 mb-1 block">Church ID</label>
                    <Input value={churchId} onChange={e => setChurchId(e.target.value)}
                      placeholder="e.g. 5" className="bg-[#21253a] border-slate-700 text-white" />
                  </div>
                  <div>
                    <label className="text-xs text-slate-400 mb-1 block">Destination Church Name</label>
                    <Input value={destination} onChange={e => setDestination(e.target.value)}
                      placeholder="e.g. Grace SDA Church, Kumasi"
                      className="bg-[#21253a] border-slate-700 text-white" />
                  </div>
                  <Button onClick={() => genLetter.mutate()} disabled={genLetter.isPending || !destination || !memberId}
                    className="w-full bg-[#e76f51] hover:bg-[#d4623d] text-white">
                    {genLetter.isPending ? 'Generating...' : 'Generate Letter'}
                  </Button>
                </div>
              </DialogContent>
            </Dialog>
          )}
        </div>

        <CardContent className="p-0">
          {tab === 'requests' && (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-800">
                  {['Member', 'Church', 'Type', 'Purpose', 'Status', 'Requested', 'Action'].map(h => (
                    <th key={h} className="text-left text-xs text-slate-500 uppercase tracking-wider px-4 py-3 font-semibold">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {loadingReq
                  ? Array.from({length:5}).map((_,i)=>(
                      <tr key={i}><td colSpan={7} className="px-4 py-3"><Skeleton className="h-6 bg-slate-800"/></td></tr>
                    ))
                  : reqList.map((r: any) => (
                      <tr key={r.id} className="border-b border-slate-800/50 hover:bg-[#21253a]">
                        <td className="px-4 py-3 text-sm text-white">{r.member_name}</td>
                        <td className="px-4 py-3 text-xs text-slate-400">{r.church_name}</td>
                        <td className="px-4 py-3 text-xs text-[#e76f51] font-semibold">{docTypeLabel[r.doc_type] || r.doc_type}</td>
                        <td className="px-4 py-3 text-xs text-slate-400 max-w-[140px] truncate">{r.purpose || '—'}</td>
                        <td className="px-4 py-3">
                          <span className={`text-xs font-semibold px-2 py-1 rounded-full ${statusColor[r.status]}`}>
                            {r.status.replace('_', ' ')}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-xs text-slate-400">{new Date(r.created_at).toLocaleDateString()}</td>
                        <td className="px-4 py-3">
                          <Button size="sm" variant="ghost" className="h-7 px-2 text-xs text-[#e76f51]">
                            Generate
                          </Button>
                        </td>
                      </tr>
                    ))
                }
              </tbody>
            </table>
          )}

          {tab === 'minutes' && (
            loadingMin
              ? <div className="p-4 space-y-2">{Array.from({length:4}).map((_,i)=><Skeleton key={i} className="h-16 bg-slate-800"/>)}</div>
              : minList.length === 0
              ? <div className="p-8 text-center text-sm text-slate-500">No meeting minutes recorded yet</div>
              : <div className="divide-y divide-slate-800">
                  {minList.map((m: any) => (
                    <div key={m.id} className="px-4 py-4 hover:bg-[#21253a]">
                      <div className="flex items-center justify-between mb-1">
                        <p className="text-sm font-semibold text-white">{m.meeting_type.replace('_',' ')} Meeting</p>
                        <span className="text-xs text-slate-500">{new Date(m.date).toLocaleDateString()}</span>
                      </div>
                      <p className="text-xs text-slate-400 truncate">{m.summary}</p>
                      <p className="text-xs text-[#e76f51] mt-1">Decisions: {m.decisions?.slice(0,80)}...</p>
                    </div>
                  ))}
                </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
```

---

## 21. Agent Logs Page — `src/app/logs/page.tsx`

```typescript
'use client'
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { PageHeader } from '@/components/page-header'
import { Card, CardContent } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { ScrollText, ChevronDown, ChevronRight } from 'lucide-react'
import { formatDistanceToNow } from 'date-fns'
import { AgentLog } from '@/lib/types'

const AGENTS = ['All','OrchestratorAgent','SubscriptionWatchdogAgent','TreasuryHealthAgent',
  'MemberCareAgent','DepartmentProgramAgent','AnnouncementAgent','AuditSecurityAgent','SecretariatAgent']

const statusColor: Record<string, string> = {
  SUCCESS: 'bg-[#00d4aa22] text-[#00d4aa]',
  FAILED: 'bg-[#ff6b6b22] text-[#ff6b6b]',
  SKIPPED: 'bg-slate-700 text-slate-400',
}

export default function LogsPage() {
  const [agentFilter, setAgentFilter] = useState('All')
  const [statusFilter, setStatusFilter] = useState('All')
  const [expanded, setExpanded] = useState<number | null>(null)

  const { data, isLoading } = useQuery({
    queryKey: ['agent-logs', agentFilter, statusFilter],
    queryFn: () => {
      const params: Record<string, string> = {}
      if (agentFilter !== 'All') params.agent_name = agentFilter
      if (statusFilter !== 'All') params.status = statusFilter
      return api.getAgentLogs(params)
    },
    refetchInterval: 30_000,
  })

  const list: AgentLog[] = data?.results || []

  return (
    <div className="space-y-6">
      <PageHeader
        title="Agent Logs"
        description="Every action taken by every agent — live, auto-refreshes every 30s"
        icon={ScrollText}
        color="#8892b0"
        agentName="All Agents"
      />

      {/* Filters */}
      <div className="flex gap-3 flex-wrap">
        <div className="flex gap-1.5 flex-wrap">
          {AGENTS.map(a => (
            <button key={a} onClick={() => setAgentFilter(a)}
              className={`text-xs px-2.5 py-1.5 rounded-full border transition-colors ${
                agentFilter === a
                  ? 'border-[#6c63ff] text-[#6c63ff] bg-[#6c63ff22]'
                  : 'border-slate-700 text-slate-500 hover:border-slate-600'
              }`}>
              {a.replace('Agent','').replace(/([A-Z])/g, ' $1').trim() || 'All'}
            </button>
          ))}
        </div>
        <div className="flex gap-1.5">
          {['All','SUCCESS','FAILED','SKIPPED'].map(s => (
            <button key={s} onClick={() => setStatusFilter(s)}
              className={`text-xs px-2.5 py-1.5 rounded-full border transition-colors ${
                statusFilter === s
                  ? 'border-[#00d4aa] text-[#00d4aa] bg-[#00d4aa22]'
                  : 'border-slate-700 text-slate-500 hover:border-slate-600'
              }`}>
              {s}
            </button>
          ))}
        </div>
      </div>

      <Card className="bg-[#1a1d27] border-slate-800">
        <CardContent className="p-0">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-800">
                {['','Agent','Action','Church','Status','Trigger','Duration','Time'].map(h => (
                  <th key={h} className="text-left text-xs text-slate-500 uppercase tracking-wider px-4 py-3 font-semibold">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {isLoading
                ? Array.from({length:8}).map((_,i)=>(
                    <tr key={i}><td colSpan={8} className="px-4 py-3"><Skeleton className="h-6 bg-slate-800"/></td></tr>
                  ))
                : list.map((log) => (
                    <>
                      <tr
                        key={log.id}
                        className="border-b border-slate-800/50 hover:bg-[#21253a] cursor-pointer"
                        onClick={() => setExpanded(expanded === log.id ? null : log.id)}
                      >
                        <td className="px-3 py-3 text-slate-600">
                          {expanded === log.id ? <ChevronDown size={13}/> : <ChevronRight size={13}/>}
                        </td>
                        <td className="px-4 py-3 text-xs text-white font-medium">
                          {log.agent_name.replace('Agent','').replace(/([A-Z])/g,' $1').trim()}
                        </td>
                        <td className="px-4 py-3 text-xs text-slate-400 max-w-[180px] truncate">{log.action}</td>
                        <td className="px-4 py-3 text-xs text-slate-500">{log.church_name || '—'}</td>
                        <td className="px-4 py-3">
                          <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${statusColor[log.status]}`}>
                            {log.status}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-xs text-slate-500">{log.triggered_by}</td>
                        <td className="px-4 py-3 text-xs text-slate-500">{log.duration_ms}ms</td>
                        <td className="px-4 py-3 text-xs text-slate-500">
                          {formatDistanceToNow(new Date(log.created_at), { addSuffix: true })}
                        </td>
                      </tr>
                      {expanded === log.id && (
                        <tr key={`${log.id}-detail`} className="bg-[#21253a]">
                          <td colSpan={8} className="px-6 py-4">
                            <div className="grid grid-cols-2 gap-4">
                              <div>
                                <p className="text-xs text-slate-500 mb-1 font-semibold uppercase">Input</p>
                                <pre className="text-xs text-slate-400 bg-[#0d1117] p-3 rounded-lg overflow-auto max-h-32">
                                  {JSON.stringify(log.input_data, null, 2)}
                                </pre>
                              </div>
                              <div>
                                <p className="text-xs text-slate-500 mb-1 font-semibold uppercase">
                                  {log.status === 'FAILED' ? 'Error' : 'Output'}
                                </p>
                                <pre className={`text-xs p-3 rounded-lg overflow-auto max-h-32 bg-[#0d1117] ${log.status === 'FAILED' ? 'text-[#ff6b6b]' : 'text-slate-400'}`}>
                                  {log.status === 'FAILED' ? log.error : JSON.stringify(log.output_data, null, 2)}
                                </pre>
                              </div>
                            </div>
                          </td>
                        </tr>
                      )}
                    </>
                  ))
              }
            </tbody>
          </table>
        </CardContent>
      </Card>
    </div>
  )
}
```

---

## 22. Settings Page — `src/app/settings/page.tsx`

```typescript
'use client'
import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { AgentSchedule } from '@/lib/types'
import { PageHeader } from '@/components/page-header'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Switch } from '@/components/ui/switch'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { Settings, Play, Edit2, Check, X } from 'lucide-react'
import { formatDistanceToNow } from 'date-fns'

const AGENT_COLORS: Record<string, string> = {
  OrchestratorAgent:          '#6c63ff',
  SubscriptionWatchdogAgent:  '#ff6b6b',
  TreasuryHealthAgent:        '#00d4aa',
  MemberCareAgent:            '#ffd166',
  DepartmentProgramAgent:     '#4ecdc4',
  AnnouncementAgent:          '#a8dadc',
  AuditSecurityAgent:         '#f4a261',
  SecretariatAgent:           '#e76f51',
}

const AGENT_DESC: Record<string, string> = {
  OrchestratorAgent:          'Admin Q&A, daily briefing, task routing',
  SubscriptionWatchdogAgent:  'Expiry alerts, payment failures, access control',
  TreasuryHealthAgent:        'Finance monitoring, stalled expense approvals',
  MemberCareAgent:            'Birthday greetings, visitor follow-ups, inactive alerts',
  DepartmentProgramAgent:     'Program approval nudges, activity reminders',
  AnnouncementAgent:          'Pending review nudges, weekly digest',
  AuditSecurityAgent:         'Suspicious activity, lockouts, compliance scan',
  SecretariatAgent:           'Document requests, meeting minutes reminders',
}

function AgentCard({ schedule }: { schedule: AgentSchedule }) {
  const qc = useQueryClient()
  const color = AGENT_COLORS[schedule.agent_name] || '#8892b0'
  const [editing, setEditing] = useState(false)
  const [cron, setCron] = useState(schedule.cron_expr)

  const toggle = useMutation({
    mutationFn: (enabled: boolean) => api.updateAgentSchedule(schedule.id, { is_enabled: enabled }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['agent-schedules'] }),
  })

  const saveCron = useMutation({
    mutationFn: () => api.updateAgentSchedule(schedule.id, { cron_expr: cron }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['agent-schedules'] }); setEditing(false) },
  })

  const runNow = useMutation({
    mutationFn: () => api.runAgentNow(schedule.agent_name),
  })

  const shortName = schedule.agent_name.replace('Agent','').replace(/([A-Z])/g,' $1').trim()

  return (
    <Card className="bg-[#1a1d27] border-slate-800">
      <CardContent className="p-5">
        <div className="flex items-start justify-between mb-3">
          <div className="flex items-center gap-2">
            <div
              className="w-3 h-3 rounded-full flex-shrink-0"
              style={{ background: schedule.is_enabled ? color : '#374151' }}
            />
            <p className="text-sm font-semibold text-white">{shortName}</p>
          </div>
          <Switch
            checked={schedule.is_enabled}
            onCheckedChange={(v) => toggle.mutate(v)}
          />
        </div>

        <p className="text-xs text-slate-500 mb-4 leading-relaxed">
          {AGENT_DESC[schedule.agent_name]}
        </p>

        <div className="space-y-2 text-xs">
          <div className="flex justify-between">
            <span className="text-slate-500">Last run</span>
            <span className="text-slate-400">
              {schedule.last_run ? formatDistanceToNow(new Date(schedule.last_run), { addSuffix: true }) : 'Never'}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-500">Last status</span>
            <span className={schedule.last_status === 'SUCCESS' ? 'text-[#00d4aa]' : schedule.last_status === 'FAILED' ? 'text-[#ff6b6b]' : 'text-slate-500'}>
              {schedule.last_status || '—'}
            </span>
          </div>
          <div className="flex items-center justify-between gap-2">
            <span className="text-slate-500 flex-shrink-0">Schedule</span>
            {editing ? (
              <div className="flex items-center gap-1 flex-1 justify-end">
                <Input value={cron} onChange={e => setCron(e.target.value)}
                  className="h-6 text-xs bg-[#21253a] border-slate-700 text-white w-32 font-mono px-2" />
                <button onClick={() => saveCron.mutate()} className="text-[#00d4aa] hover:text-white"><Check size={12}/></button>
                <button onClick={() => { setEditing(false); setCron(schedule.cron_expr) }} className="text-[#ff6b6b]"><X size={12}/></button>
              </div>
            ) : (
              <div className="flex items-center gap-1">
                <span className="text-slate-400 font-mono text-[10px]">{schedule.cron_expr}</span>
                <button onClick={() => setEditing(true)} className="text-slate-600 hover:text-slate-400 ml-1"><Edit2 size={10}/></button>
              </div>
            )}
          </div>
        </div>

        <Button
          size="sm"
          variant="outline"
          className="w-full mt-4 h-7 text-xs border-slate-700 hover:border-slate-600 text-slate-400 hover:text-white"
          onClick={() => runNow.mutate()}
          disabled={runNow.isPending}
          style={runNow.isPending ? {} : { borderColor: `${color}44`, color }}
        >
          <Play size={11} className="mr-1.5" />
          {runNow.isPending ? 'Running...' : 'Run Now'}
        </Button>
      </CardContent>
    </Card>
  )
}

export default function SettingsPage() {
  const { data, isLoading } = useQuery({
    queryKey: ['agent-schedules'],
    queryFn: () => api.getAgentSchedules(),
  })

  const list: AgentSchedule[] = data?.results || []

  return (
    <div className="space-y-6">
      <PageHeader
        title="Agent Settings"
        description="Enable/disable agents, edit schedules, trigger manual runs"
        icon={Settings}
        color="#8892b0"
        agentName="Configuration"
      />

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {isLoading
          ? Array.from({length:8}).map((_,i) => <Skeleton key={i} className="h-52 bg-slate-800"/>)
          : list.map(s => <AgentCard key={s.id} schedule={s}/>)
        }
      </div>
    </div>
  )
}
```

---

## 23. Tailwind Config — `tailwind.config.ts`

```typescript
import type { Config } from 'tailwindcss'

const config: Config = {
  darkMode: ['class'],
  content: ['./src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        border: 'hsl(var(--border))',
        background: 'hsl(var(--background))',
        foreground: 'hsl(var(--foreground))',
        primary: { DEFAULT: '#6c63ff', foreground: '#ffffff' },
      },
      borderRadius: {
        lg: 'var(--radius)',
        md: 'calc(var(--radius) - 2px)',
        sm: 'calc(var(--radius) - 4px)',
      },
    },
  },
  plugins: [require('tailwindcss-animate')],
}
export default config
```

---

## 24. Global CSS — `src/app/globals.css`

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

@layer base {
  :root {
    --background: 222 47% 7%;
    --foreground: 210 40% 89%;
    --border: 217 32% 17%;
    --radius: 0.75rem;
  }
  * { @apply border-border; }
  body { @apply bg-background text-foreground; }
  ::-webkit-scrollbar { width: 4px; height: 4px; }
  ::-webkit-scrollbar-track { background: transparent; }
  ::-webkit-scrollbar-thumb { background: #2e3250; border-radius: 4px; }
}
```

---

## 25. Running the Frontend

```bash
# Development
npm run dev
# Opens at http://localhost:3000

# Build for production
npm run build
npm start
```

### Start everything together

```bash
# Terminal 1 — Django backend
cd /home/professor/Desktop/church-management-saas-backend
source .venv/bin/activate
python manage.py runserver

# Terminal 2 — Celery worker
cd /home/professor/projects/churchagents
source .venv/bin/activate
celery -A scheduler.tasks worker --loglevel=info

# Terminal 3 — Celery beat
celery -A scheduler.tasks beat --loglevel=info

# Terminal 4 — Next.js frontend
cd church-agents-dashboard
npm run dev
```

---

## 26. Navigation Summary — All 11 Tabs

| URL | Tab | Agent | Key Features |
|-----|-----|-------|-------------|
| `/` | Dashboard | Overview | Stats, agent status grid, activity chart, recent logs |
| `/ask` | Ask AI | Orchestrator | Chat interface, suggested questions, conversation memory |
| `/subscriptions` | Subscriptions | Watchdog | Church table, filter by status, send reminder, disable/reinstate |
| `/treasury` | Treasury | Finance | Income/expense chart, stalled expense requests |
| `/members` | Members | Care | Member growth chart, active/visitors/inactive tabs |
| `/departments` | Departments | Programs | Stalled programs, upcoming activities |
| `/announcements` | Announcements | Comms | Pending/published tabs, approve, distribute |
| `/security` | Security | Audit | Audit log with action filters, locked accounts |
| `/secretariat` | Secretariat | Records | Document requests, meeting minutes, generate transfer letter |
| `/logs` | Agent Logs | All | Filterable log table, expandable rows with JSON |
| `/settings` | Settings | Config | Toggle agents on/off, edit cron, run manually |
