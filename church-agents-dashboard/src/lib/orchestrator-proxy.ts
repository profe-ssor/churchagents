/**
 * Server-side calls to churchagents FastAPI (AGENTS_API_URL).
 * Azure / proxies often return HTML on 502/503 — never assume JSON.
 */

export type OrchestratorJsonResult =
  | { ok: true; status: number; data: Record<string, unknown> }
  | {
      ok: false
      status: number
      /** Human-readable explanation for dashboard / logs */
      parseError: string
      bodySnippet: string
    }

export async function fetchOrchestratorJson(
  url: string,
  init: RequestInit
): Promise<OrchestratorJsonResult> {
  const res = await fetch(url, init)
  const text = await res.text()
  const trimmed = text.trimStart()
  const snippet = text.slice(0, 400).replace(/\s+/g, " ").trim()

  if (trimmed.startsWith("<!DOCTYPE") || trimmed.startsWith("<html")) {
    return {
      ok: false,
      status: res.status,
      parseError:
        "Response was HTML, not JSON — usually an Azure Container Apps / proxy error page " +
        "(no healthy revision, app crash, wrong target port, or URL points at the wrong host). " +
        `Check HTTP ${res.status} and container logs; probe GET ${url.replace(/\/[^/]+$/, "")}/health`,
      bodySnippet: snippet,
    }
  }

  try {
    const data = JSON.parse(text) as Record<string, unknown>
    return { ok: true, status: res.status, data }
  } catch {
    return {
      ok: false,
      status: res.status,
      parseError: "Response was not valid JSON.",
      bodySnippet: snippet || "(empty body)",
    }
  }
}
