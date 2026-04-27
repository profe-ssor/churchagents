"use client"

import { useEffect, useState } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import { LogIn, Loader2, Building2 } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Card } from "@/components/ui/card"

export function LoginForm() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const next = searchParams.get("next") || "/"

  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState("")
  const [loading, setLoading] = useState(false)
  /** Avoid SSR/client mismatch on submit disabled (Base UI + empty fields). */
  const [mounted, setMounted] = useState(false)
  useEffect(() => setMounted(true), [])

  const canSubmit = Boolean(email.trim() && password)
  const submitDisabled = loading || (mounted && !canSubmit)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError("")
    setLoading(true)

    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      })
      const data = await res.json()

      if (!res.ok) {
        setError(data.detail || "Login failed")
        return
      }

      router.push(next.startsWith("/") ? next : "/")
      router.refresh()
    } catch {
      setError("Cannot reach the server. Is Django running?")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-[#0f1117] p-4">
      <div className="w-full max-w-sm space-y-6">
        <div className="flex flex-col items-center gap-3 text-center">
          <div className="flex size-12 items-center justify-center rounded-2xl bg-[#6c63ff]">
            <Building2 size={24} className="text-white" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-white">Church Agents</h1>
            <p className="mt-1 text-sm text-slate-400">
              Sign in — chat with CTO (Church Technician Officer) and dashboards
            </p>
          </div>
        </div>

        <Card className="border-slate-800 bg-[#1a1d27] p-6">
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="email" className="text-slate-300">
                Email
              </Label>
              <Input
                id="email"
                type="email"
                autoComplete="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="admin@churchsaas.com"
                className="border-slate-700 bg-[#21253a] text-white placeholder:text-slate-600"
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="password" className="text-slate-300">
                Password
              </Label>
              <Input
                id="password"
                type="password"
                autoComplete="current-password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="border-slate-700 bg-[#21253a] text-white placeholder:text-slate-600"
              />
            </div>

            {error && (
              <p className="rounded-lg border border-red-900 bg-red-950/40 px-3 py-2 text-sm text-red-400">
                {error}
              </p>
            )}

            <Button
              type="submit"
              disabled={submitDisabled}
              className="w-full bg-[#6c63ff] text-white hover:bg-[#5a52e8]"
            >
              {loading ? (
                <Loader2 size={16} className="animate-spin" />
              ) : (
                <>
                  <LogIn size={16} />
                  Sign in
                </>
              )}
            </Button>
          </form>
        </Card>

        <p className="text-center text-xs text-slate-600">
          Platform admins and church admins can sign in here.
          <br />
          Your access level is determined by your Django account.
        </p>
      </div>
    </div>
  )
}
