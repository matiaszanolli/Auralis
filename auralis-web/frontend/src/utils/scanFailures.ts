/**
 * Shared scan-failure summary helpers.
 *
 * Extracted from useLibraryScan.ts (#4841) so the Library view's "Scan
 * Folder" flow and the Settings "Scan Now" / auto-scan flow (ScanStatusCard,
 * #5466) render failed-file details identically instead of drifting apart —
 * only the Library view surfaced them before this.
 */

import type { ScanFailure } from '@/types/ws/library';

/** How many failed filenames a summary names before summarising the rest. */
export const MAX_FAILURES_SHOWN = 3;

/**
 * Describe failed files for a scan summary (#4841).
 *
 * Shows a few names rather than all of them: a folder of corrupt files would
 * otherwise produce a message nobody can read. The count passed in is
 * already exact, so this is about making the failures *findable*.
 */
export function describeFailures(failures: ScanFailure[] | undefined, failedCount: number): string {
  if (!failures?.length) return '';

  const shown = failures.slice(0, MAX_FAILURES_SHOWN);
  const names = shown.map((f) => f.filename).join(', ');
  const remaining = failedCount - shown.length;

  return `\n${names}${remaining > 0 ? ` and ${remaining} more` : ''}`;
}
