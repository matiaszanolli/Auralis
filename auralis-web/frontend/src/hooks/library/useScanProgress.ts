/**
 * useScanProgress Hook
 *
 * Subscribes to scan lifecycle WebSocket messages so components can display
 * live scanning status and last scan results.
 */

import { useEffect, useRef, useState } from 'react';
import { useWebSocketContext } from '@/contexts/WebSocketContext';
import { useWebSocketMessages } from '@/hooks/websocket/useWebSocketMessages';
import type {
  ScanProgressMessage,
  ScanCompleteMessage,
} from '@/types/websocket';
import { isLibraryTracksRemovedMessage } from '@/types/ws/guards';
import { getApiUrl } from '@/config/api';

export interface ScanProgress {
  isScanning: boolean;
  current: number;
  total: number;
  /** 0-100 once the scanner has a pre-counted total (#4616); null while the
   *  count pass is still running or no scan has started (show indeterminate
   *  indicator). A `0` here means 0% processed, not "unknown". */
  percentage: number | null;
  currentFile: string | null;
  /** `'fingerprinting'` removed in #4648 — no reachable emitter. */
  phase: 'discovering' | 'processing';
}

export interface ScanResult {
  filesAdded: number;
  filesRemoved: number;
  /** Files the backend could not read/decode (#4412). */
  filesFailed: number;
  /** Files skipped (already present / unchanged) (#4412). */
  filesSkipped: number;
  duration: number;
}

export interface ScanStatus extends ScanProgress {
  lastResult: ScanResult | null;
}

const INITIAL_STATE: ScanStatus = {
  isScanning: false,
  current: 0,
  total: 0,
  // #4616: null, not 0 — before the first frame the percentage is genuinely
  // unknown, and seeding 0 made the UI flip 0 → null on the first frame of
  // every scan (and read as "0% done" while nothing was known).
  percentage: null,
  currentFile: null,
  phase: 'processing',
  lastResult: null,
};

/**
 * Subscribe to library scan lifecycle messages from the WebSocket.
 * Returns live scan status and the result of the most recent completed scan.
 */
export function useScanProgress(): ScanStatus {
  const [state, setState] = useState<ScanStatus>(INITIAL_STATE);

  // Track whether library_tracks_removed was received during this scan.
  // Without this, scan_complete would carry over stale filesRemoved from
  // the previous scan (fixes #2868).
  const removedReceivedRef = useRef(false);

  // #4821: scan lifecycle is otherwise broadcast-only, so a WebSocket drop
  // that spans the scan's terminal frame (scan_complete/library_scan_error)
  // leaves isScanning stuck true forever — the only fix is a page reload.
  // On every (re)connect, resync against a live server-side check instead of
  // trusting whatever frame happened to arrive last. Mirrors the reconnect
  // resync pattern in usePlayerStateSync (lastSeenSeqRef reset on
  // connectionStatus === 'connected').
  const { connectionStatus } = useWebSocketContext();
  useEffect(() => {
    if (connectionStatus !== 'connected') return;

    const controller = new AbortController();
    fetch(getApiUrl('/api/library/scan/status'), { signal: controller.signal })
      .then((response) => (response.ok ? response.json() : null))
      .then((data: { is_scanning?: boolean } | null) => {
        if (!data) return;
        setState((prev) => {
          if (data.is_scanning) {
            // A scan is active that this client may not know about yet
            // (reconnected mid-scan, or this is the first load while
            // another client's scan is still running).
            return prev.isScanning ? prev : { ...prev, isScanning: true };
          }
          // No scan is active. If we were still showing "Scanning…" the
          // terminal WS frame was missed while disconnected — clear it.
          // lastResult is deliberately left untouched: this endpoint only
          // knows the current is_scanning state, not final counts, so
          // overwriting it here would discard real data with nothing.
          return prev.isScanning ? { ...INITIAL_STATE, lastResult: prev.lastResult } : prev;
        });
      })
      .catch(() => {
        // Best-effort resync — a transient fetch failure just leaves local
        // state as-is until the next (re)connect retries.
      });

    return () => controller.abort();
  }, [connectionStatus]);

  useWebSocketMessages(
    ['library_scan_started', 'scan_progress', 'scan_complete', 'library_tracks_removed', 'library_scan_error'],
    (message) => {
      if (message.type === 'library_scan_started') {
        removedReceivedRef.current = false;
        setState((prev) => ({
          ...INITIAL_STATE,
          lastResult: prev.lastResult,
          isScanning: true,
        }));
      } else if (message.type === 'scan_progress') {
        const msg = message as ScanProgressMessage;
        setState((prev) => ({
          ...prev,
          isScanning: true,
          current: msg.data.current,
          total: msg.data.total,
          percentage: msg.data.percentage,
          currentFile: msg.data.current_file ?? null,
          phase: msg.data.phase ?? 'processing',
        }));
      } else if (message.type === 'scan_complete') {
        const msg = message as ScanCompleteMessage;
        const hadRemovals = removedReceivedRef.current;
        setState((prev) => ({
          ...INITIAL_STATE,
          lastResult: {
            filesAdded: msg.data.files_added ?? 0,
            filesRemoved: hadRemovals ? (prev.lastResult?.filesRemoved ?? 0) : 0,
            filesFailed: msg.data.files_failed ?? 0,
            filesSkipped: msg.data.files_skipped ?? 0,
            duration: msg.data.duration,
          },
        }));
      } else if (message.type === 'library_scan_error') {
        // Reset scanning state so the UI doesn't stay stuck (#2869)
        setState((prev) => ({
          ...INITIAL_STATE,
          lastResult: prev.lastResult,
        }));
      } else if (isLibraryTracksRemovedMessage(message)) {
        removedReceivedRef.current = true;
        setState((prev) => ({
          ...prev,
          lastResult: prev.lastResult
            ? { ...prev.lastResult, filesRemoved: message.data.count }
            : { filesAdded: 0, filesRemoved: message.data.count, filesFailed: 0, filesSkipped: 0, duration: 0 },
        }));
      }
    }
  );

  return state;
}
