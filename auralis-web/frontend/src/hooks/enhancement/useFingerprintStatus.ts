/**
 * useFingerprintStatus Hook
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Owns the fingerprint-analysis status state machine surfaced during enhanced
 * playback: it subscribes to `fingerprint_progress` WebSocket messages, mirrors
 * their status/message into state for the UI, and auto-clears a `complete`
 * message after 2 s (with the timer cancelled on unmount / disconnect to avoid
 * setState on a dead component — #2353, #2536).
 *
 * Extracted from usePlayEnhanced as part of decomposing that 900+-line hook
 * (#4077).
 *
 * @module hooks/enhancement/useFingerprintStatus
 */

const DEBUG = import.meta.env.DEV;

import { useCallback, useEffect, useRef, useState } from 'react';
import { useWebSocketContext } from '@/contexts/WebSocketContext';
import type { FingerprintProgressMessage } from '@/types/websocket';

type WebSocketContextValue = ReturnType<typeof useWebSocketContext>;

/** Fingerprint analysis status surfaced to the UI. */
export type FingerprintStatus =
  | 'idle'
  | 'analyzing'
  | 'complete'
  | 'failed'
  | 'error'
  | 'cached'
  | 'queued';

export interface UseFingerprintStatusReturn {
  /** Current fingerprint analysis status. */
  fingerprintStatus: FingerprintStatus;
  /** Human-readable analysis message for display, or null. */
  fingerprintMessage: string | null;
  /** Reset to the idle/empty state (call when a new stream begins). */
  resetFingerprint: () => void;
  /**
   * Cancel any pending auto-clear timeout. Exposed so the streaming core can
   * cancel it on WS disconnect (a stale callback must not fire against the next
   * stream context — #2536).
   */
  cancelFingerprintTimeout: () => void;
}

export function useFingerprintStatus(
  wsContext: WebSocketContextValue
): UseFingerprintStatusReturn {
  const [fingerprintStatus, setFingerprintStatus] = useState<FingerprintStatus>('idle');
  const [fingerprintMessage, setFingerprintMessage] = useState<string | null>(null);

  // Timer ref for the status auto-clear (fixes #2353).
  const fingerprintTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  // Latest handler kept in a ref so the mount-time subscription always calls the
  // current closure without needing to resubscribe.
  const handlerRef = useRef<((m: FingerprintProgressMessage) => void) | null>(null);

  const cancelFingerprintTimeout = useCallback(() => {
    if (fingerprintTimeoutRef.current !== null) {
      clearTimeout(fingerprintTimeoutRef.current);
      fingerprintTimeoutRef.current = null;
    }
  }, []);

  const resetFingerprint = useCallback(() => {
    setFingerprintStatus('idle');
    setFingerprintMessage(null);
  }, []);

  const handleFingerprintProgress = useCallback((message: FingerprintProgressMessage) => {
    const { status, message: progressMessage } = message.data || {};

    DEBUG && console.log('[useFingerprintStatus] Fingerprint progress:', { status, message: progressMessage });

    setFingerprintStatus(status || 'idle');
    setFingerprintMessage(progressMessage || null);

    // Auto-clear success message after 2 seconds; store handle so it can be
    // cancelled on unmount to avoid setState on a dead component (fixes #2353).
    if (status === 'complete') {
      cancelFingerprintTimeout();
      fingerprintTimeoutRef.current = setTimeout(() => {
        fingerprintTimeoutRef.current = null;
        setFingerprintStatus('idle');
        setFingerprintMessage(null);
      }, 2000);
    }
  }, [cancelFingerprintTimeout]);
  handlerRef.current = handleFingerprintProgress;

  // Subscribe on mount (or WebSocket reconnect).
  useEffect(() => {
    const unsubscribe = wsContext.subscribe(
      'fingerprint_progress',
      (m: unknown) => handlerRef.current?.(m as FingerprintProgressMessage)
    );
    DEBUG && console.log('[useFingerprintStatus] Subscribed to fingerprint_progress on mount');
    return () => {
      unsubscribe?.();
      DEBUG && console.log('[useFingerprintStatus] Unsubscribed from fingerprint_progress on unmount');
    };
  }, [wsContext]);

  // Cancel a pending auto-clear timer on unmount (#2353).
  useEffect(() => cancelFingerprintTimeout, [cancelFingerprintTimeout]);

  return { fingerprintStatus, fingerprintMessage, resetFingerprint, cancelFingerprintTimeout };
}
