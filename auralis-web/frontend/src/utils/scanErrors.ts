/**
 * Shared scan-request error messages.
 *
 * The Library view's "Scan Folder" flow (useLibraryScan) and the Settings
 * "Scan Now" flow (useSettingsDialog) both POST /api/library/scan, whose route
 * answers with specific details (409 already scanning, 429 rate limit, 504
 * timeout, 500 handler error). Settings used to throw them away and report
 * "Failed to start scan" for all of them (#5914), so one helper owns the
 * mapping and the two flows cannot drift apart.
 */

import { APIRequestError } from '@/utils/apiRequestTypes';

/** HTTP status the scan route returns when a scan already holds the slot. */
const SCAN_ALREADY_RUNNING = 409;

export interface ScanErrorDescription {
  message: string;
  /** Not a fault (a scan is already running): show it as information. */
  informational: boolean;
}

export function describeScanError(err: unknown): ScanErrorDescription {
  // statusCode 0 is a network/timeout failure; a real status keeps the
  // backend's `detail`.
  if (err instanceof APIRequestError && err.statusCode !== 0) {
    if (err.statusCode === SCAN_ALREADY_RUNNING) {
      return { message: err.detail || 'Scan already in progress', informational: true };
    }
    return { message: `Scan failed: ${err.detail || 'Unknown error'}`, informational: false };
  }
  return {
    message: 'Error scanning folder — check the backend is reachable',
    informational: false,
  };
}
