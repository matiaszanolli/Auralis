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
import { useMessageSubscriptions } from '@/hooks/websocket/useWebSocketMessages';
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
  /**
   * Reset to the idle/empty state (call when a new stream begins). Pass the
   * track the new stream plays: `fingerprint_progress` for any other track is
   * then ignored, so a message still in flight from the previous track cannot
   * overwrite this one's status (#5380).
   */
  resetFingerprint: (trackId?: number | null) => void;
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
  // Track whose stream this status belongs to; null until a stream starts
  // (#5380). Same gate as the streaming reducers' trackId check (#4434).
  const activeTrackIdRef = useRef<number | null>(null);

  const cancelFingerprintTimeout = useCallback(() => {
    if (fingerprintTimeoutRef.current !== null) {
      clearTimeout(fingerprintTimeoutRef.current);
      fingerprintTimeoutRef.current = null;
    }
  }, []);

  const resetFingerprint = useCallback((trackId: number | null = null) => {
    // The previous track's 2 s auto-clear must not fire over this stream's
    // status (#6102).
    cancelFingerprintTimeout();
    activeTrackIdRef.current = trackId;
    setFingerprintStatus('idle');
    setFingerprintMessage(null);
  }, [cancelFingerprintTimeout]);

  const handleFingerprintProgress = useCallback((message: FingerprintProgressMessage) => {
    const { track_id: trackId, status, message: progressMessage } = message.data || {};

    // A skip resets this hook at click time, but the previous track's message
    // can still arrive afterwards; drop it rather than show it for the new
    // track (#5380).
    const activeTrackId = activeTrackIdRef.current;
    if (activeTrackId != null && trackId != null && trackId !== activeTrackId) {
      DEBUG && console.log('[useFingerprintStatus] Ignoring progress for superseded track', { trackId, activeTrackId });
      return;
    }

    DEBUG && console.log('[useFingerprintStatus] Fingerprint progress:', { status, message: progressMessage });

    setFingerprintStatus(status || 'idle');
    setFingerprintMessage(progressMessage || null);

    // Any new status supersedes a pending auto-clear (#6102).
    cancelFingerprintTimeout();

    // Auto-clear success message after 2 seconds; store handle so it can be
    // cancelled on unmount to avoid setState on a dead component (fixes #2353).
    if (status === 'complete') {
      fingerprintTimeoutRef.current = setTimeout(() => {
        fingerprintTimeoutRef.current = null;
        setFingerprintStatus('idle');
        setFingerprintMessage(null);
      }, 2000);
    }
  }, [cancelFingerprintTimeout]);

  // `subscribe` is identity-stable across WS status transitions, so the shared
  // subscription hook (which depends on it alone) does not resubscribe on a
  // connect/disconnect/error flicker (#4668).
  useMessageSubscriptions(wsContext.subscribe, {
    fingerprint_progress: (m) => handleFingerprintProgress(m as unknown as FingerprintProgressMessage),
  });

  // Cancel a pending auto-clear timer on unmount (#2353).
  useEffect(() => cancelFingerprintTimeout, [cancelFingerprintTimeout]);

  return { fingerprintStatus, fingerprintMessage, resetFingerprint, cancelFingerprintTimeout };
}
