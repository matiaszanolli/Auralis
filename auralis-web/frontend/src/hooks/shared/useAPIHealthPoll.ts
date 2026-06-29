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
        const response = await fetch('/api/health', { method: 'GET' });
        if (!mountedRef.current) return;
        const latency = Math.round(performance.now() - start);
        if (response.ok) {
          dispatch(setAPIConnected(true));
          dispatch(setLatency(latency));
        }
      } catch {
        if (!mountedRef.current) return;
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
