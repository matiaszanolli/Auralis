/**
 * useScanProgress Hook
 *
 * Subscribes to scan lifecycle WebSocket messages so components can display
 * live scanning status and last scan results.
 *
 * #5622: the state used to live in per-hook `useState`, so ScanStatusCard —
 * which unmounts with the settings dialog's tab content — lost the last-scan
 * result on every remount, and a remount mid-scan showed 0/0 until the next
 * progress frame. Both consumers (ScanStatusCard and SettingsDialog's tab
 * badge) also each installed their own WS subscription doing identical work.
 * The state now lives in a module-level store (the useArtworkRevision
 * pattern) fed by ONE refcounted WS subscription; consumers read it via
 * `useSyncExternalStore`. SettingsDialog is mounted for the app lifetime, so
 * the subscription effectively always lives. The reconnect resync (#4821) and
 * the removedReceived tracking (#2868) belong to the shared state, not to
 * individual consumers.
 */

import { useEffect, useSyncExternalStore } from 'react';
import { useWebSocketContext } from '@/contexts/WebSocketContext';
import type {
  ScanProgressMessage,
  ScanCompleteMessage,
  ScanPhase,
  AnyWebSocketMessage,
  WebSocketMessage,
  WebSocketMessageType,
} from '@/types/websocket';
import type { ScanFailure } from '@/types/ws/library';
import { isLibraryTracksRemovedMessage } from '@/types/ws/guards';
import { get } from '@/utils/apiRequest';

export interface ScanProgress {
  isScanning: boolean;
  current: number;
  total: number;
  /** 0-100 once the scanner has a pre-counted total (#4616); null while the
   *  count pass is still running or no scan has started (show indeterminate
   *  indicator). A `0` here means 0% processed, not "unknown". */
  percentage: number | null;
  currentFile: string | null;
  phase: ScanPhase;
}

export interface ScanResult {
  filesAdded: number;
  filesRemoved: number;
  /** Files the backend could not read/decode (#4412). */
  filesFailed: number;
  /** Files skipped (already present / unchanged) (#4412). */
  filesSkipped: number;
  /**
   * Which files failed and why, capped backend-side (#4841, carried through
   * here for #5466 so ScanStatusCard can name them like useLibraryScan's
   * toast already does). Can be shorter than `filesFailed`.
   */
  failures: ScanFailure[];
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

// ----- Module-level shared status store (#5622) -----

let sharedState: ScanStatus = INITIAL_STATE;
const statusListeners = new Set<() => void>();

/** Whether library_tracks_removed was received during the current scan —
 *  without it, scan_complete would carry stale filesRemoved (#2868). Lives
 *  with the shared state so two consumers cannot disagree. */
let removedReceivedInScan = false;

function getSnapshot(): ScanStatus {
  return sharedState;
}

function subscribeToStatus(listener: () => void): () => void {
  statusListeners.add(listener);
  return () => {
    statusListeners.delete(listener);
  };
}

function setSharedState(update: (prev: ScanStatus) => ScanStatus): void {
  const next = update(sharedState);
  if (next !== sharedState) {
    sharedState = next;
    for (const listener of statusListeners) listener();
  }
}

// AnyWebSocketMessage (MessageHandler's union), not the narrower
// WebSocketMessage — the shared subscription delivers any dispatched type.
function handleScanMessage(raw: AnyWebSocketMessage | WebSocketMessage): void {
  if (raw.type === 'library_scan_started') {
    removedReceivedInScan = false;
    setSharedState((prev) => ({
      ...INITIAL_STATE,
      lastResult: prev.lastResult,
      isScanning: true,
    }));
  } else if (raw.type === 'scan_progress') {
    const msg = raw as ScanProgressMessage;
    setSharedState((prev) => ({
      ...prev,
      isScanning: true,
      current: msg.data.current,
      total: msg.data.total,
      percentage: msg.data.percentage,
      currentFile: msg.data.current_file ?? null,
      phase: msg.data.phase ?? 'processing',
    }));
  } else if (raw.type === 'scan_complete') {
    const msg = raw as ScanCompleteMessage;
    const hadRemovals = removedReceivedInScan;
    setSharedState((prev) => ({
      ...INITIAL_STATE,
      lastResult: {
        filesAdded: msg.data.files_added ?? 0,
        filesRemoved: hadRemovals ? (prev.lastResult?.filesRemoved ?? 0) : 0,
        filesFailed: msg.data.files_failed ?? 0,
        filesSkipped: msg.data.files_skipped ?? 0,
        failures: msg.data.failures ?? [],
        duration: msg.data.duration,
      },
    }));
  } else if (raw.type === 'library_scan_error') {
    // Reset scanning state so the UI doesn't stay stuck (#2869)
    setSharedState((prev) => ({
      ...INITIAL_STATE,
      lastResult: prev.lastResult,
    }));
  } else if (isLibraryTracksRemovedMessage(raw)) {
    removedReceivedInScan = true;
    setSharedState((prev) => ({
      ...prev,
      lastResult: prev.lastResult
        ? { ...prev.lastResult, filesRemoved: raw.data.count }
        : { filesAdded: 0, filesRemoved: raw.data.count, filesFailed: 0, filesSkipped: 0, failures: [], duration: 0 },
    }));
  }
}

const SCAN_MESSAGE_TYPES: WebSocketMessageType[] = [
  'library_scan_started',
  'scan_progress',
  'scan_complete',
  'library_tracks_removed',
  'library_scan_error',
];

// ----- Single refcounted WS subscription (the useArtworkRevision pattern) -----

let globalRefCount = 0;
let detachGlobalSubscription: (() => void) | null = null;

/**
 * #4821: scan lifecycle is otherwise broadcast-only, so a WebSocket drop that
 * spans the scan's terminal frame (scan_complete/library_scan_error) leaves
 * isScanning stuck true forever — the only fix is a page reload. On every
 * (re)connect, resync against a live server-side check instead of trusting
 * whatever frame happened to arrive last.
 *
 * Module-level with abort-dedup: two mounted consumers both see the
 * 'connected' transition, and the second call aborts the first's in-flight
 * request — one resync per connection, not one per consumer.
 */
let resyncController: AbortController | null = null;

function resyncScanStatus(): void {
  resyncController?.abort();
  const controller = new AbortController();
  resyncController = controller;
  // #5019: shared transport, so the resync inherits DEFAULT_TIMEOUT_MS on top
  // of the disconnect/unmount signal. get() rejects on a non-2xx rather than
  // resolving to null, which the .catch() below already treats as "leave
  // local state alone".
  get<{ is_scanning?: boolean }>('/api/library/scan/status', { signal: controller.signal })
    .then((data) => {
      if (!data) return;
      setSharedState((prev) => {
        if (data.is_scanning) {
          // A scan is active that this client may not know about yet
          // (reconnected mid-scan, or this is the first load while another
          // client's scan is still running).
          return prev.isScanning ? prev : { ...prev, isScanning: true };
        }
        // No scan is active. If we were still showing "Scanning…" the terminal
        // WS frame was missed while disconnected — clear it. lastResult is
        // deliberately left untouched: this endpoint only knows the current
        // is_scanning state, not final counts, so overwriting it here would
        // discard real data with nothing.
        return prev.isScanning ? { ...INITIAL_STATE, lastResult: prev.lastResult } : prev;
      });
    })
    .catch(() => {
      // Best-effort resync — a transient request failure (including a
      // timeout) just leaves state as-is until the next (re)connect.
    });
}

/**
 * Subscribe to library scan lifecycle messages from the WebSocket.
 * Returns live scan status and the result of the most recent completed scan.
 *
 * The returned shape is unchanged from the per-instance version — consumers
 * (ScanStatusCard, SettingsDialog) read the shared store transparently.
 */
export function useScanProgress(): ScanStatus {
  const { subscribe, connectionStatus } = useWebSocketContext();

  // Refcount: the WS subscription is installed exactly once while >= 1
  // consumer is mounted. SettingsDialog stays mounted for the app lifetime,
  // so in practice the subscription always lives and ScanStatusCard's
  // remounts reuse it instead of restarting from INITIAL_STATE.
  useEffect(() => {
    globalRefCount += 1;
    if (globalRefCount === 1) {
      // handleScanMessage only narrows the message types it reads; the
      // context's handler union is wider by design.
      const handler = handleScanMessage as Parameters<typeof subscribe>[1];
      const unsubscribes = SCAN_MESSAGE_TYPES.map((type) => subscribe(type, handler));
      detachGlobalSubscription = () => {
        for (const unsubscribe of unsubscribes) unsubscribe();
      };
    }
    return () => {
      globalRefCount = Math.max(0, globalRefCount - 1);
      if (globalRefCount === 0) {
        detachGlobalSubscription?.();
        detachGlobalSubscription = null;
        // No consumer left to receive the resync result — cancel it.
        resyncController?.abort();
        resyncController = null;
      }
    };
  }, [subscribe]);

  useEffect(() => {
    if (connectionStatus === 'connected') resyncScanStatus();
  }, [connectionStatus]);

  return useSyncExternalStore(subscribeToStatus, getSnapshot, getSnapshot);
}

// Test/debug helpers
export const _internal = {
  get state() {
    return sharedState;
  },
  reset() {
    sharedState = INITIAL_STATE;
    removedReceivedInScan = false;
    statusListeners.clear();
    resyncController?.abort();
    resyncController = null;
  },
};
