import { NextRequest, NextResponse } from "next/server"

import { proxyRequest } from "@/lib/django-proxy-request"

type Ctx = { params: Promise<{ path: string[] }> }

export async function GET(req: NextRequest, ctx: Ctx) {
  const { path } = await ctx.params
  return proxyRequest(req, path, false)
}

export async function POST(req: NextRequest, ctx: Ctx) {
  const { path } = await ctx.params
  return proxyRequest(req, path, false)
}

export async function PUT(req: NextRequest, ctx: Ctx) {
  const { path } = await ctx.params
  return proxyRequest(req, path, false)
}

export async function PATCH(req: NextRequest, ctx: Ctx) {
  const { path } = await ctx.params
  return proxyRequest(req, path, false)
}

export async function DELETE(req: NextRequest, ctx: Ctx) {
  const { path } = await ctx.params
  return proxyRequest(req, path, false)
}
