/**
 * The client-side bound for POST /api/library/scan, derived from the server's own (#6576).
 *
 * Since #4820 an aborted scan request is the "stop the scan" signal, so the client must never give
 * up before the server does. The server's bound is `AURALIS_SCAN_TIMEOUT`, which an operator can
 * raise above the 1h default; a client bound hard-coded to the default then cut large imports at
 * 61 minutes as a client disconnect. GET /api/library/scan/status reports `scan_timeout_s`; the
 * client bound is that plus SCAN_TIMEOUT_MARGIN_MS, so the server's 504 always comes first while
 * the request stays bounded for a wedged backend (#5019).
 */
import { ENDPOINTS, SCAN_TIMEOUT_MARGIN_MS, SCAN_TIMEOUT_MS } from '@/config/api';
import { get } from '@/utils/apiRequest';
import { isAbortError } from '@/utils/errorGuards';

let serverBoundSeconds: number | null = null;

/** Record the server's scan bound from a scan-status payload (the resync does, on every connect). */
export function recordScanTimeout(seconds: unknown): void {
  if (typeof seconds === 'number' && Number.isFinite(seconds) && seconds > 0) {
    serverBoundSeconds = seconds;
  }
}

/** The scan request bound if the server's has been reported, else null (no request is made). */
export function knownScanRequestTimeoutMs(): number | null {
  return serverBoundSeconds === null ? null : serverBoundSeconds * 1000 + SCAN_TIMEOUT_MARGIN_MS;
}

/**
 * The timeoutMs to pass with a scan request: the known bound at once, or else one read of the
 * server's. When that read fails, the bound for a default-configured server; the next scan asks
 * again. Callers that must not yield when the bound is known use
 * `knownScanRequestTimeoutMs() ?? (await scanRequestTimeoutMs())`.
 */
export async function scanRequestTimeoutMs(signal?: AbortSignal): Promise<number> {
  if (serverBoundSeconds === null) {
    try {
      const status = await get<{ scan_timeout_s?: number }>(ENDPOINTS.LIBRARY_SCAN_STATUS, { signal });
      recordScanTimeout(status?.scan_timeout_s);
    } catch (err) {
      if (isAbortError(err)) throw err;
    }
  }
  return knownScanRequestTimeoutMs() ?? SCAN_TIMEOUT_MS;
}
