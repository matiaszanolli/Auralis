/**
 * useAPIHealthPoll
 * ~~~~~~~~~~~~~~~~
 *
 * Polls `/api/health` every `intervalMs`, dispatching API-connected + latency to
 * the Redux connection slice so all consumers see the same values (#3380).
 * Pauses while the tab is hidden and resumes with an immediate check on return
 * (#3257). Uses a ref-stored interval so cleanup always clears the latest one
 * even if a visibilitychange fires mid-teardown (#3585).
 *
 * Extracted from ConnectionStatusIndicator (#4186).
 */

import { useEffect, useRef } from 'react';
import { useDispatch } from 'react-redux';
import { setAPIConnected, setLatency } from '@/store/slices/connectionSlice';
import { get, APIRequestError } from '@/utils/apiRequest';

export function useAPIHealthPoll(intervalMs = 5000): void {
  const dispatch = useDispatch();
  // Guard against dispatch after unmount.
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    const intervalRef: { current: ReturnType<typeof setInterval> | null } = { current: null };

    const pollHealth = async () => {
      const start = performance.now();
      try {
        // #5019: shared transport, so a stalled backend fails this poll after
        // DEFAULT_TIMEOUT_MS instead of leaving it pending forever — a bare
        // fetch() here could accumulate one hung request per interval tick.
        await get('/api/health');
        if (!mountedRef.current) return;
        const latency = Math.round(performance.now() - start);
        dispatch(setAPIConnected(true));
        dispatch(setLatency(latency));
      } catch (err) {
        if (!mountedRef.current) return;
        // Pre-#5019 semantics preserved: the success arm was gated on
        // `response.ok` with no `else`, so a non-2xx health response left the
        // connection state untouched — a backend that answers at all is
        // reachable. Only a transport-level failure (network error, or the new
        // timeout; both carry statusCode 0) marks the API disconnected.
        if (err instanceof APIRequestError && err.statusCode !== 0) return;
        dispatch(setAPIConnected(false));
        dispatch(setLatency(0));
      }
    };

    const startPolling = () => {
      if (!intervalRef.current) {
        intervalRef.current = setInterval(pollHealth, intervalMs);
      }
    };

    const stopPolling = () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };

    const handleVisibility = () => {
      if (document.hidden) {
        stopPolling();
      } else {
        pollHealth(); // Immediate check on return
        startPolling();
      }
    };

    startPolling();
    document.addEventListener('visibilitychange', handleVisibility);

    return () => {
      // Order matters: remove the visibility listener FIRST so it can no longer
      // call startPolling() between clearing the interval and finishing cleanup.
      mountedRef.current = false;
      document.removeEventListener('visibilitychange', handleVisibility);
      stopPolling();
    };
  }, [dispatch, intervalMs]);
}
