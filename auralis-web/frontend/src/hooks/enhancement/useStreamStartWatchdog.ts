/**
 * useStreamStartWatchdog
 * ~~~~~~~~~~~~~~~~~~~~~~
 *
 * Client-side watchdog for the first stream message after a play command
 * (#4433), lifted out of useAudioStreamingCore's body (#5041).
 *
 * The timeout must exceed the backend's own bound (CHUNK_PROCESS_TIMEOUT =
 * 30s, plus a 5s stream-semaphore wait) so that in the ordinary timeout case
 * the backend's `audio_stream_error` surfaces first. This only fires for a
 * fully-hung worker that never emits anything, which would otherwise leave
 * the UI in 'buffering' forever — the duplicate-play guard blocks a naive
 * retry out of that state.
 *
 * `onTimeout` is held in a ref, so `arm` and `clear` keep stable identities
 * no matter how often the caller's callback is rebuilt. That matters here
 * beyond the usual render-churn argument: in useAudioStreamingCore the
 * timeout handler runs `cleanupStreaming`, which itself calls `clear`. A
 * callback-identity dependency would close that loop and make neither
 * function memoizable.
 *
 * @module hooks/enhancement/useStreamStartWatchdog
 */

import { useCallback, useEffect, useRef } from 'react';

export const STREAM_START_WATCHDOG_MS = 45000;

export interface StreamStartWatchdog {
  /** Start (or restart) the timer. Called right after a play command is sent. */
  arm: () => void;
  /** Cancel a pending timer. Safe to call when nothing is armed. */
  clear: () => void;
}

export function useStreamStartWatchdog(
  onTimeout: () => void,
  timeoutMs: number = STREAM_START_WATCHDOG_MS
): StreamStartWatchdog {
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const onTimeoutRef = useRef(onTimeout);

  useEffect(() => {
    onTimeoutRef.current = onTimeout;
  }, [onTimeout]);

  const clear = useCallback(() => {
    if (timerRef.current !== null) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  const arm = useCallback(() => {
    clear();
    timerRef.current = setTimeout(() => {
      timerRef.current = null;
      onTimeoutRef.current();
    }, timeoutMs);
  }, [clear, timeoutMs]);

  // A timer outliving the component would fire onTimeout against a torn-down
  // stream. The hook owns the handle, so it owns the unmount cleanup too.
  useEffect(() => clear, [clear]);

  return { arm, clear };
}
