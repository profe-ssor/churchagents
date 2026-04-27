import type { Metadata } from "next"
import { Geist, Geist_Mono } from "next/font/google"
import { cookies } from "next/headers"

import { Providers } from "@/components/providers"
import { Sidebar } from "@/components/sidebar"
import { parseSession, SESSION_COOKIE } from "@/lib/auth"

import "./globals.css"

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
})

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
})

export const metadata: Metadata = {
  title: "Church Agents Dashboard",
  description:
    "Monitor church operations with CTO (Church Technician Officer) and specialist agents",
}

export default async function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  const cookieStore = await cookies()
  const session = parseSession(cookieStore.get(SESSION_COOKIE)?.value)

  return (
    <html lang="en" className="dark" suppressHydrationWarning>
      <body
        className={`${geistSans.variable} ${geistMono.variable} min-h-screen bg-[#0f1117] text-slate-100 antialiased`}
      >
        <Providers>
          {session ? (
            <div className="flex h-screen overflow-hidden">
              <Sidebar user={session} />
              <main className="flex-1 overflow-y-auto p-6">{children}</main>
            </div>
          ) : (
            <main className="min-h-screen">{children}</main>
          )}
        </Providers>
      </body>
    </html>
  )
}
