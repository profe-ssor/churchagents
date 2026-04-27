"use client"

import { useEffect, useMemo, useRef, useState } from "react"
import { useQuery } from "@tanstack/react-query"

import { api } from "@/lib/api"

export interface SessionInfo {
  authenticated: boolean
  is_platform_admin: boolean
  church_id: string | null
}

export function useDashboardChurchScope(localStorageKey: string) {
  const [scopeChurchId, setScopeChurchId] = useState("")
  const scopeHydrated = useRef(false)

  const { data: sessionInfo, isSuccess: sessionReady } = useQuery({
    queryKey: ["session-info"],
    queryFn: async (): Promise<SessionInfo> => {
      const r = await fetch("/api/auth/session")
      return r.json()
    },
  })

  const { data: churchesData, isSuccess: churchesReady } = useQuery({
    queryKey: ["churches", "list", "500"],
    queryFn: () => api.getChurches({ page_size: "500" }),
    enabled: Boolean(sessionInfo?.authenticated),
  })

  const churches = churchesData?.results ?? []

  useEffect(() => {
    if (scopeHydrated.current || typeof window === "undefined") return
    const saved = localStorage.getItem(localStorageKey)
    if (saved !== null) setScopeChurchId(saved)
    scopeHydrated.current = true
  }, [localStorageKey])

  useEffect(() => {
    if (!scopeHydrated.current || typeof window === "undefined") return
    localStorage.setItem(localStorageKey, scopeChurchId)
  }, [localStorageKey, scopeChurchId])

  const effectiveChurchId = useMemo(() => {
    if (!sessionInfo?.authenticated) return null
    if (sessionInfo.is_platform_admin) {
      return scopeChurchId.trim() !== "" ? scopeChurchId.trim() : null
    }
    return sessionInfo.church_id || churches[0]?.id || null
  }, [sessionInfo, scopeChurchId, churches])

  const waitingPlatformScope =
    Boolean(sessionInfo?.authenticated) &&
    Boolean(sessionInfo?.is_platform_admin) &&
    !scopeChurchId.trim()

  const needsChurch =
    churchesReady &&
    Boolean(sessionInfo?.authenticated) &&
    !sessionInfo?.is_platform_admin &&
    !effectiveChurchId

  const showScopePicker =
    Boolean(sessionInfo?.authenticated) && Boolean(sessionInfo?.is_platform_admin)

  const bootLoading = !sessionReady || !churchesReady

  return {
    sessionInfo,
    sessionReady,
    churches,
    churchesReady,
    scopeChurchId,
    setScopeChurchId,
    effectiveChurchId,
    waitingPlatformScope,
    needsChurch,
    showScopePicker,
    bootLoading,
  }
}
