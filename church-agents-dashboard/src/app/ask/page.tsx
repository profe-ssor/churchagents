"use client"

import { useEffect, useRef, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { Bot, Loader2, MessageSquare, Send, User } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { api } from "@/lib/api"
import { AI_ASK_PAGE_TITLE, AI_ASSISTANT_HEADLINE, AI_NAME_SHORT } from "@/lib/branding"
import type { ChatMessage } from "@/lib/types"
import { cn } from "@/lib/utils"

const SCOPE_STORAGE_KEY = "churchagents_ask_church_scope"

const SUGGESTIONS = [
  "Which churches are expiring this week?",
  "How many members joined last month?",
  "Summarize treasury health signals",
  "Are there any security alerts?",
]

interface SessionInfo {
  authenticated: boolean
  is_platform_admin: boolean
  church_id: string | null
  church_name: string | null
}

export default function AskPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState("")
  const [loading, setLoading] = useState(false)
  const [scopeChurchId, setScopeChurchId] = useState("")
  /** Avoid SSR/client mismatch on submit disabled (input + loading vs first paint). */
  const [hydrated, setHydrated] = useState(false)
  const sessionId = useRef(`session-${Date.now()}`)
  const bottomRef = useRef<HTMLDivElement>(null)
  const scopeHydrated = useRef(false)

  const { data: sessionInfo } = useQuery({
    queryKey: ["session-info"],
    queryFn: async (): Promise<SessionInfo> => {
      const r = await fetch("/api/auth/session")
      return r.json()
    },
  })

  const { data: churchesData } = useQuery({
    queryKey: ["churches", "ask-scope"],
    queryFn: () => api.getChurches({ page_size: "500" }),
    enabled: Boolean(sessionInfo?.authenticated && sessionInfo.is_platform_admin),
  })

  const churches = churchesData?.results ?? []

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages])

  useEffect(() => {
    setHydrated(true)
  }, [])

  useEffect(() => {
    if (scopeHydrated.current || typeof window === "undefined") return
    const saved = localStorage.getItem(SCOPE_STORAGE_KEY)
    if (saved !== null) {
      setScopeChurchId(saved)
    }
    scopeHydrated.current = true
  }, [])

  useEffect(() => {
    if (!scopeHydrated.current || typeof window === "undefined") return
    localStorage.setItem(SCOPE_STORAGE_KEY, scopeChurchId)
  }, [scopeChurchId])

  async function send(question: string) {
    if (!question.trim() || loading) return
    const q = question.trim()
    setInput("")
    setMessages((prev) => [
      ...prev,
      { role: "user", content: q, timestamp: new Date().toISOString() },
    ])
    setLoading(true)
    try {
      const opts =
        sessionInfo?.is_platform_admin && scopeChurchId
          ? { church_id: scopeChurchId }
          : undefined
      const res = await api.askAgent(q, sessionId.current, opts)
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: res.answer || res.response || "No response from agent service.",
          timestamp: new Date().toISOString(),
        },
      ])
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content:
            "Could not reach the dashboard Ask API. Check your network and that the dev server is running.",
          timestamp: new Date().toISOString(),
        },
      ])
    } finally {
      setLoading(false)
    }
  }

  const showScopePicker =
    Boolean(sessionInfo?.authenticated) && Boolean(sessionInfo?.is_platform_admin)

  const canSubmit = hydrated && input.trim().length > 0 && !loading

  return (
    <div className="flex h-[calc(100vh-3rem)] flex-col space-y-4">
      <div className="flex shrink-0 flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div className="flex items-start gap-3">
          <div className="flex size-10 shrink-0 items-center justify-center rounded-xl border border-[#6c63ff44] bg-[#6c63ff22]">
            <MessageSquare size={18} className="text-[#6c63ff]" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-white">{AI_ASK_PAGE_TITLE}</h1>
          </div>
        </div>

        {showScopePicker && (
          <div className="flex min-w-[240px] flex-col gap-1.5">
            <label htmlFor="ask-church-scope" className="text-xs font-medium text-slate-400">
              Which church is this question about?
            </label>
            <select
              id="ask-church-scope"
              value={scopeChurchId}
              onChange={(e) => setScopeChurchId(e.target.value)}
              aria-describedby="ask-church-scope-hint"
              className="rounded-lg border border-slate-700 bg-[#21253a] px-3 py-2 text-sm text-white outline-none focus:border-[#6c63ff]"
            >
              <option value="">Platform-wide — subscriptions, treasury, alerts</option>
              {churches.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
            <p id="ask-church-scope-hint" className="text-[11px] leading-snug text-slate-500">
              Choose a congregation for member counts and church-only data. Leave the first option for platform-wide questions. Your choice is remembered on this device.
            </p>
          </div>
        )}
      </div>

      <Card className="flex min-h-0 flex-1 flex-col border-slate-800 bg-[#1a1d27]">
        <div className="flex-1 space-y-4 overflow-y-auto p-4">
          {messages.length === 0 && (
            <div className="flex h-full flex-col items-center justify-center gap-4 text-center">
              <div className="flex size-16 items-center justify-center rounded-2xl bg-[#6c63ff22]">
                <Bot size={28} className="text-[#6c63ff]" />
              </div>
              <div>
                <p className="font-semibold text-white">{AI_ASSISTANT_HEADLINE}</p>
                <p className="mt-1 max-w-md text-sm leading-relaxed text-slate-400">
                  Ask in plain language about members, finances, subscriptions, or day-to-day church
                  operations—answers respect your sign-in and permissions, so you see what is
                  relevant to you.
                </p>
              </div>
              <div className="flex max-w-lg flex-wrap justify-center gap-2">
                {SUGGESTIONS.map((s) => (
                  <button
                    key={s}
                    type="button"
                    onClick={() => send(s)}
                    className="rounded-full border border-slate-700 px-3 py-1.5 text-xs text-slate-400 transition-colors hover:border-[#6c63ff] hover:text-[#6c63ff]"
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((msg, i) => (
            <div
              key={i}
              className={cn("flex gap-3", msg.role === "user" ? "justify-end" : "justify-start")}
            >
              {msg.role === "assistant" && (
                <div className="mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-lg bg-[#6c63ff22]">
                  <Bot size={14} className="text-[#6c63ff]" />
                </div>
              )}
              <div
                className={cn(
                  "max-w-[75%] rounded-2xl px-4 py-2.5 text-sm",
                  msg.role === "user"
                    ? "rounded-tr-sm bg-[#6c63ff] text-white"
                    : "rounded-tl-sm bg-[#21253a] text-slate-200"
                )}
              >
                <p className="whitespace-pre-wrap">{msg.content}</p>
              </div>
              {msg.role === "user" && (
                <div className="mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-lg bg-slate-700">
                  <User size={14} className="text-slate-300" />
                </div>
              )}
            </div>
          ))}

          {loading && (
            <div className="flex gap-3">
              <div className="flex size-7 shrink-0 items-center justify-center rounded-lg bg-[#6c63ff22]">
                <Bot size={14} className="text-[#6c63ff]" />
              </div>
              <div className="rounded-2xl rounded-tl-sm bg-[#21253a] px-4 py-3">
                <Loader2 size={14} className="animate-spin text-[#6c63ff]" />
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        <div className="border-t border-slate-800 p-4">
          <form
            onSubmit={(e) => {
              e.preventDefault()
              send(input)
            }}
            className="flex gap-2"
          >
            <Input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={`Ask ${AI_NAME_SHORT} anything about your church platform…`}
              className="flex-1 border-slate-700 bg-[#21253a] text-white placeholder:text-slate-600"
            />
            <Button
              type="submit"
              disabled={!canSubmit}
              className="bg-[#6c63ff] text-white hover:bg-[#5a52e8]"
            >
              <Send size={15} />
            </Button>
          </form>
        </div>
      </Card>
    </div>
  )
}
