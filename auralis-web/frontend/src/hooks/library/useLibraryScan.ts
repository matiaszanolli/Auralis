import { useState, useCallback, useEffect, useRef } from 'react';
import { useToast } from '@/components/shared/Toast';
import { isElectron, getElectronAPI } from '@/utils/electron';

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
      const response = await fetch('/api/library/scan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ directories: [folderPath] }),
        signal: controller.signal,
      });

      if (response.ok) {
        const result: { files_added?: number; files_failed?: number; files_skipped?: number } =
          await response.json();
        // Guard post-success work against unmount (#3987).
        if (!mountedRef.current) return;
        // Surface partial failures instead of a silent "Added 0 tracks" (#4412).
        const added = result.files_added || 0;
        const failed = result.files_failed || 0;
        const skipped = result.files_skipped || 0;
        const extras = [
          failed > 0 ? `${failed} failed` : null,
          skipped > 0 ? `${skipped} skipped` : null,
        ].filter(Boolean).join(', ');
        const summary = `Scan complete! Added ${added} tracks${extras ? ` (${extras})` : ''}`;
        if (failed > 0) toastRef.current.toastError(summary);
        else toastRef.current.success(summary);
        await fetchTracks();
        if (includeStats) await refetchStats();
      } else {
        const errorData: { detail?: string } = await response.json();
        toastRef.current.toastError(`Scan failed: ${errorData.detail || 'Unknown error'}`);
      }
    } catch (err) {
      // Swallow abort errors (unmount / superseded scan) — not user-facing.
      if (err instanceof DOMException && err.name === 'AbortError') return;
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
