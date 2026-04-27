import type { ReactNode } from "react"

/** Avoid edge/CDN serving a stale shell for this route after deploys. */
export const dynamic = "force-dynamic"
export const revalidate = 0

export default function SecurityLayout({ children }: { children: ReactNode }) {
  return children
}
