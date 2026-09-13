import { useState, useCallback, useEffect, useRef } from 'react';
import { useToast } from '@/components/shared/Toast';
import { isElectron, getElectronAPI } from '@/utils/electron';
import type { ScanFailure } from '@/types/ws/library';
import { post, APIRequestError } from '@/utils/apiRequest';
import { isAbortError } from '@/utils/errorGuards';

/** Wire shape of POST /api/library/scan's summary. */
interface ScanSummary {
  files_added?: number;
  files_failed?: number;
  files_skipped?: number;
  failures?: ScanFailure[];
}

export interface UseLibraryScanOptions {
  includeStats: boolean;
  fetchTracks: (resetPagination?: boolean) => Promise<void>;
  refetchStats: () => Promise<void>;
}

export interface UseLibraryScanReturn {
  scanning: boolean;
  webFolderPath: string;
  setWebFolderPath: (path: string) => void;
  handleScanFolder: () => Promise<void>;
  scanAbortRef: React.MutableRefObject<AbortController | null>;
}

/** How many failed filenames a toast names before summarising the rest. */
const MAX_FAILURES_IN_TOAST = 3;


/** Basename of a path, for a toast that must stay readable. */
function baseName(filepath: string): string {
  const parts = filepath.split(/[/\\]/);
  return parts[parts.length - 1] || filepath;
}

/**
 * Append the failed filenames to a scan summary (#4841).
 *
 * Shows a few names rather than all of them: a folder of corrupt files would
 * otherwise produce a toast nobody can read. The count in the summary is
 * already exact, so this is about making the failures *findable*.
 */
function describeFailures(failures: ScanFailure[] | undefined, failedCount: number): string {
  if (!failures?.length) return '';

  const shown = failures.slice(0, MAX_FAILURES_IN_TOAST);
  const names = shown.map((f) => baseName(f.filepath)).join(', ');
  const remaining = failedCount - shown.length;

  return `\n${names}${remaining > 0 ? ` and ${remaining} more` : ''}`;
}


export const useLibraryScan = ({
  includeStats,
  fetchTracks,
  refetchStats,
}: UseLibraryScanOptions): UseLibraryScanReturn => {
  const [scanning, setScanning] = useState(false);
  const [webFolderPath, setWebFolderPath] = useState('');
  const scanAbortRef = useRef<AbortController | null>(null);
  const mountedRef = useRef(true);

  const { success, error: toastError, info } = useToast();
  // useToast returns fresh identities every render; mirror them through a ref
  // so handleScanFolder stays stable (#4195; mirrors useLibraryPagination #3943).
  const toastRef = useRef({ success, toastError, info });
  toastRef.current = { success, toastError, info };

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      scanAbortRef.current?.abort();
    };
  }, []);

  const handleScanFolder = useCallback(async () => {
    let folderPath: string | undefined;

    if (isElectron()) {
      try {
        const result = await getElectronAPI()!.selectFolder();
        if (result && result.length > 0) {
          folderPath = result[0];
        } else {
          return;
        }
      } catch (err) {
        console.error('Failed to open folder picker:', err);
        toastRef.current.toastError('Failed to open folder picker');
        return;
      }
    } else {
      // Web browser: read from the controlled input (set via setWebFolderPath).
      folderPath = webFolderPath.trim() || undefined;
      if (!folderPath) {
        toastRef.current.info('Enter a folder path in the scan field and try again');
        return;
      }
    }

    setScanning(true);
    // Abort any prior in-flight scan and make this one cancellable (#3987).
    scanAbortRef.current?.abort();
    const controller = new AbortController();
    scanAbortRef.current = controller;
    try {
      // #5019: routed through the shared transport, which composes
      // DEFAULT_TIMEOUT_MS with the cancellation signal below. The raw fetch()
      // this replaces had no upper bound, so a hung backend left `scanning`
      // true (and the button disabled) indefinitely.
      const result = await post<ScanSummary>(
        '/api/library/scan',
        { directories: [folderPath] },
        { signal: controller.signal }
      );

      // Guard post-success work against unmount (#3987).
      if (!mountedRef.current) return;
      // Surface partial failures instead of a silent "Added 0 tracks" (#4412).
      const added = result?.files_added || 0;
      const failed = result?.files_failed || 0;
      const skipped = result?.files_skipped || 0;
      const extras = [
        failed > 0 ? `${failed} failed` : null,
        skipped > 0 ? `${skipped} skipped` : null,
      ].filter(Boolean).join(', ');
      const summary = `Scan complete! Added ${added} tracks${extras ? ` (${extras})` : ''}`;
      // #4841: name the files that failed. "3 failed" told the user something
      // was wrong but gave them no way to find out what, short of reading
      // backend logs a desktop end user generally cannot see. The backend caps
      // the list, so it may be shorter than `failed`.
      if (failed > 0) toastRef.current.toastError(`${summary}${describeFailures(result?.failures, failed)}`);
      else toastRef.current.success(summary);
      await fetchTracks();
      if (includeStats) await refetchStats();
    } catch (err) {
      // Swallow abort errors (unmount / superseded scan) — not user-facing.
      // post() wraps an abort into an APIRequestError rather than preserving
      // AbortError's `.name`, so the signal is checked first.
      if (controller.signal.aborted || isAbortError(err)) return;
      // post() throws on non-2xx instead of returning a response to branch on.
      // A real HTTP status keeps the backend's `detail` (the old `else` arm);
      // statusCode 0 is a network/timeout failure (the old outer catch).
      if (err instanceof APIRequestError && err.statusCode !== 0) {
        toastRef.current.toastError(`Scan failed: ${err.detail || 'Unknown error'}`);
        return;
      }
      console.error('Scan error:', err);
      toastRef.current.toastError('Error scanning folder — check the backend is reachable');
    } finally {
      if (mountedRef.current) {
        setScanning(false);
      }
    }
  }, [includeStats, fetchTracks, refetchStats, webFolderPath]);

  return { scanning, webFolderPath, setWebFolderPath, handleScanFolder, scanAbortRef };
};
