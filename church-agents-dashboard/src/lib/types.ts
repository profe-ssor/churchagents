/** Django-aligned shapes (churchagents + church-management-saas-backend). */

export interface Church {
  id: string
  name: string
  email?: string
  subscription_plan?: string
  subscription_status?: string
  status?: string
  subscription_ends_at?: string | null
  platform_access_enabled?: boolean
  user_count?: number
}

export interface AgentLog {
  id: string
  agent_name: string
  church?: string | null
  church_id?: string | null
  church_name?: string | null
  action: string
  status: string
  triggered_by: string
  duration_ms: number
  error: string
  input_data: Record<string, unknown>
  output_data: Record<string, unknown>
  created_at: string
}

export interface AgentAlert {
  id: string
  agent_name: string
  alert_type: string
  message: string
  severity: string
  church_id?: string | null
  church_name?: string | null
  created_at: string
}

export interface AgentSchedule {
  id: string | number
  agent_name: string
  is_enabled: boolean
  cron_expr: string
  last_run: string | null
  next_run: string | null
  last_status: string
}

export interface ChatMessage {
  role: "user" | "assistant"
  content: string
  timestamp: string
}

export interface DashboardStats {
  total_churches: number
  active_subscriptions: number
  expiring_this_week: number
  suspended: number
}

/** Django `GET /api/treasury/statistics/` when successful */
export interface TreasuryStatistics {
  total_income: string
  total_expenses: string
  net_balance: string
  income_by_category: CategoryBreakdownRow[]
  expenses_by_category: CategoryBreakdownRow[]
  expenses_by_department: DepartmentBreakdownRow[]
  pending_expense_requests: number
  total_assets_value: string
}

export interface CategoryBreakdownRow {
  category__name?: string | null
  total?: string | number | null
  count?: number | null
}

export interface DepartmentBreakdownRow {
  department__name?: string | null
  total?: string | number | null
  count?: number | null
}
