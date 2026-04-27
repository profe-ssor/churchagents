import { Suspense } from "react"

import { LoginForm } from "./login-form"

function LoginFallback() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-[#0f1117] p-4">
      <p className="text-sm text-slate-400">Loading sign-in…</p>
    </div>
  )
}

export default function LoginPage() {
  return (
    <Suspense fallback={<LoginFallback />}>
      <LoginForm />
    </Suspense>
  )
}
