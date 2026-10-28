import { useState, useCallback, useEffect, useRef } from 'react';
import { useToast } from '@/components/shared/Toast';
import { SCAN_TIMEOUT_MS } from '@/config/api';
import { isElectron, getElectronAPI } from '@/utils/electron';
import type { ScanFailure } from '@/types/ws/library';
import { post } from '@/utils/apiRequest';
import { isAbortError } from '@/utils/errorGuards';
import { describeFailures } from '@/utils/scanFailures';
import { describeScanError } from '@/utils/scanErrors';

/** Wire shape of POST /api/library/scan's summary. */
interface ScanSummary {
  files_added?: number;
  files_failed?: number;
  files_skipped?: number;
  failures?: ScanFailure[];
  /** Folders the scan could not read (#5877). */
  directory_errors?: ScanFailure[];
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
  /** With a path (the folder a DropZone click already picked) the picker is skipped. */
  handleScanFolder: (selectedFolder?: string) => Promise<void>;
  scanAbortRef: React.MutableRefObject<AbortController | null>;
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
      // Since #4820 this abort reaches the backend: the scan handler watches
      // its receive channel and stops the scanner thread (releasing the scan
      // slot) when the request's client goes away. Before that it was
      // client-side only — the scan ran on to completion or its 1h timeout.
      scanAbortRef.current?.abort();
    };
  }, []);

  const handleScanFolder = useCallback(async (selectedFolder?: string) => {
    let folderPath: string | undefined;

    // Callers also bind this straight to onClick, so only a string is a path.
    if (typeof selectedFolder === 'string' && selectedFolder.trim()) {
      folderPath = selectedFolder.trim();
    } else if (isElectron()) {
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
      // #5865: register the folder in the path allowlist. The manual scan
      // route accepts any readable directory but never touches the
      // allowlist, so tracks imported from outside the default roots
      // (~Music/~Documents) listed fine and then streamed as "Audio file
      // not found". Routing through the settings endpoint — the same one
      // Settings > Scan folders uses — keeps ONE registration code path,
      // and it also persists the folder to scan_folders so startup
      // re-seeds it and wakes the auto-scanner. Dispatched alongside the
      // scan (bounded, failure non-fatal): registration is a millisecond
      // endpoint and streaming needs it only after the scan completes.
      const registration = post(
        '/api/settings/scan-folders',
        { folder: folderPath },
        { signal: controller.signal, timeoutMs: 5_000 }
      ).catch(() => {
        // Already registered or the backend rejected the add — the scan
        // below surfaces whatever actually matters to the user.
      });

      // #5019: routed through the shared transport, which composes a timeout
      // with the cancellation signal below. The raw fetch() this replaces had
      // no upper bound, so a hung backend left `scanning` true (and the button
      // disabled) indefinitely. The timeout is scan-specific (see
      // SCAN_TIMEOUT_MS) because aborting now really does stop the scan.
      const result = await post<ScanSummary>(
        '/api/library/scan',
        { directories: [folderPath] },
        { signal: controller.signal, timeoutMs: SCAN_TIMEOUT_MS }
      );
      await registration;

      // Guard post-success work against unmount (#3987).
      if (!mountedRef.current) return;
      // Surface partial failures instead of a silent "Added 0 tracks" (#4412).
      const added = result?.files_added || 0;
      const failed = result?.files_failed || 0;
      const skipped = result?.files_skipped || 0;
      const unreadable = result?.directory_errors ?? [];
      const extras = [
        failed > 0 ? `${failed} failed` : null,
        skipped > 0 ? `${skipped} skipped` : null,
        unreadable.length > 0 ? `${unreadable.length} folder${unreadable.length === 1 ? '' : 's'} unreadable` : null,
      ].filter(Boolean).join(', ');
      const summary = `Scan complete! Added ${added} tracks${extras ? ` (${extras})` : ''}`;
      // #4841: name the files that failed. "3 failed" told the user something
      // was wrong but gave them no way to find out what, short of reading
      // backend logs a desktop end user generally cannot see. The backend caps
      // the list, so it may be shorter than `failed`.
      // #5877: an unreadable folder means tracks are missing, not "complete".
      if (failed > 0 || unreadable.length > 0) {
        toastRef.current.toastError(
          `${summary}${describeFailures(result?.failures, failed)}${describeFailures(unreadable, unreadable.length)}`
        );
      } else toastRef.current.success(summary);
      await fetchTracks();
      if (includeStats) await refetchStats();
    } catch (err) {
      // Swallow abort errors (unmount / superseded scan) — not user-facing.
      // post() wraps an abort into an APIRequestError rather than preserving
      // AbortError's `.name`, so the signal is checked first.
      if (controller.signal.aborted || isAbortError(err)) return;
      // post() throws on non-2xx instead of returning a response to branch on.
      const { message, informational } = describeScanError(err);
      if (informational) {
        toastRef.current.info(message);
        return;
      }
      console.error('Scan error:', err);
      toastRef.current.toastError(message);
    } finally {
      if (mountedRef.current) {
        setScanning(false);
      }
    }
  }, [includeStats, fetchTracks, refetchStats, webFolderPath]);

  return { scanning, webFolderPath, setWebFolderPath, handleScanFolder, scanAbortRef };
};
