/**
 * Every API call goes through fetchJson, so they all fail the same way:
 * with an ApiError whose message is fit to show the reader, after a
 * timeout instead of a spinner that never ends, and with one quiet retry
 * when a page load hits a brief outage (a deploy restarting the server).
 */

/** Long enough for the heaviest page payloads on a slow connection. */
export const DEFAULT_TIMEOUT_MS = 20_000;
/** The analyzer runs a model over up to 50,000 characters on CPU. */
export const ANALYZE_TIMEOUT_MS = 120_000;

const RETRY_STATUSES = new Set([502, 503, 504]);
const RETRY_DELAY_MS = 1_000;

export class ApiError extends Error {
  /** HTTP status; 0 for timeouts and network failures. */
  status: number;
  kind: "http" | "timeout" | "network";
  constructor(message: string, status: number, kind: ApiError["kind"] = "http") {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.kind = kind;
  }
}

/** A readable message for a failed response: the server's own `error`
 *  when it sent one (the API answers errors as {"error": "..."}). */
async function errorFor(res: Response): Promise<ApiError> {
  const body = await res.json().catch(() => null);
  const serverMessage = body && typeof body.error === "string" ? body.error : null;
  if (serverMessage) return new ApiError(serverMessage, res.status);
  if (res.status === 429) return new ApiError("Too many requests. Please wait a moment and try again.", 429);
  if (res.status === 404) return new ApiError("Not found.", 404);
  if (res.status >= 500) return new ApiError("The server ran into a problem. Please try again shortly.", res.status);
  return new ApiError(`Request failed (HTTP ${res.status}).`, res.status);
}

async function attempt(url: string, init: RequestInit, timeoutMs: number): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  // A caller's own signal (a component unmounting) cancels too.
  init.signal?.addEventListener("abort", () => controller.abort());
  try {
    return await fetch(url, { ...init, signal: controller.signal });
  } catch (e) {
    if (init.signal?.aborted) throw e;
    if (controller.signal.aborted) {
      throw new ApiError("The server took too long to respond. Please try again.", 0, "timeout");
    }
    throw new ApiError("Couldn't reach the server. Check your connection and try again.", 0, "network");
  } finally {
    clearTimeout(timer);
  }
}

export async function fetchJson<T>(
  url: string,
  { timeoutMs = DEFAULT_TIMEOUT_MS, ...init }: RequestInit & { timeoutMs?: number } = {},
): Promise<T> {
  // Only reads are retried: resending a POST could repeat its effect.
  const retries = (init.method ?? "GET").toUpperCase() === "GET" ? 1 : 0;
  for (let tries = 0; ; tries++) {
    let res: Response;
    try {
      res = await attempt(url, init, timeoutMs);
    } catch (e) {
      // Not after a timeout: that would double an already long wait.
      if (e instanceof ApiError && e.kind === "network" && tries < retries) {
        await new Promise(r => setTimeout(r, RETRY_DELAY_MS));
        continue;
      }
      throw e;
    }
    if (res.ok) {
      try {
        return (await res.json()) as T;
      } catch {
        throw new ApiError("The server sent a response we couldn't read.", res.status);
      }
    }
    if (RETRY_STATUSES.has(res.status) && tries < retries) {
      await new Promise(r => setTimeout(r, RETRY_DELAY_MS));
      continue;
    }
    throw await errorFor(res);
  }
}

export function errorMessage(e: unknown, fallback = "Something went wrong."): string {
  return e instanceof Error && e.message ? e.message : fallback;
}

let reportsSent = 0;
const MAX_REPORTS_PER_PAGE_LOAD = 5;

/** Sends a browser-side error to the server's log (/api/client-errors),
 *  where it would otherwise never show up. Never throws. */
export function reportClientError(error: unknown) {
  if (reportsSent >= MAX_REPORTS_PER_PAGE_LOAD) return;
  reportsSent++;
  const err = error instanceof Error ? error : new Error(String(error));
  fetch("/api/client-errors", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      page: window.location.pathname + window.location.search,
      message: `${err.name}: ${err.message}`.slice(0, 500),
      stack: (err.stack ?? "").slice(0, 4000),
    }),
    keepalive: true,
  }).catch(() => {});
}
