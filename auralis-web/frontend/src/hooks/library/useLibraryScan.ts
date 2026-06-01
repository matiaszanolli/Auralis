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
        toastError('Failed to open folder picker');
        return;
      }
    } else {
      // Web browser: read from the controlled input (set via setWebFolderPath).
      folderPath = webFolderPath.trim() || undefined;
      if (!folderPath) {
        info('Enter a folder path in the scan field and try again');
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
        const result: { files_added?: number } = await response.json();
        // Guard post-success work against unmount (#3987).
        if (!mountedRef.current) return;
        success(`Scan complete! Added ${result.files_added || 0} tracks`);
        await fetchTracks();
        if (includeStats) await refetchStats();
      } else {
        const errorData: { detail?: string } = await response.json();
        toastError(`Scan failed: ${errorData.detail || 'Unknown error'}`);
      }
    } catch (err) {
      // Swallow abort errors (unmount / superseded scan) — not user-facing.
      if (err instanceof DOMException && err.name === 'AbortError') return;
      console.error('Scan error:', err);
      toastError('Error scanning folder — check the backend is reachable');
    } finally {
      if (mountedRef.current) {
        setScanning(false);
      }
    }
  }, [includeStats, fetchTracks, refetchStats, webFolderPath, success, toastError, info]);

  return { scanning, webFolderPath, setWebFolderPath, handleScanFolder, scanAbortRef };
};
