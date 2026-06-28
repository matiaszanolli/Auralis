/**
 * useMasteringRecommendation Hook
 *
 * Manages WebSocket messages for mastering profile recommendations (Priority 4).
 * Subscribes to mastering_recommendation events and caches recommendations per track.
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { useWebSocketContext } from '@/contexts/WebSocketContext';
import type {
  AnyWebSocketMessage,
  WebSocketMessage,
  MasteringRecommendationData,
  MasteringRecommendationMessage,
} from '@/types/websocket';

// Single source of truth lives in types/ws/enhancement (#4166). Re-export so
// existing importers of this type from the hook keep resolving.
export type { MasteringRecommendationData };

interface MasteringRecommendationCache {
  [trackId: number]: MasteringRecommendationData;
}

const RECOMMENDATION_TIMEOUT_MS = 10_000;

export const useMasteringRecommendation = (trackId?: number) => {
  const { subscribe } = useWebSocketContext();
  const [recommendation, setRecommendation] = useState<MasteringRecommendationData | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isTimedOut, setIsTimedOut] = useState(false);
  const cache = useRef<MasteringRecommendationCache>({});
  // #4163: hold the timeout handle in a ref so the WS handler can clear it
  // without a forward reference to a `const timeout` declared after subscribe()
  // (a TDZ ReferenceError under synchronous WS delivery, e.g. sync-mock tests).
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Handle incoming mastering recommendation messages
  useEffect(() => {
    if (!trackId) return;

    // Check cache first
    if (cache.current[trackId]) {
      setRecommendation(cache.current[trackId]);
      // #3625: also clear loading/timed-out state so the spinner does not
      // hang when the previous trackId's request was still loading.
      setIsLoading(false);
      setIsTimedOut(false);
      return;
    }

    // #4165: clear the previous track's recommendation on a cache miss so a
    // stale profile is not shown for up to 10s while the new one loads.
    setRecommendation(null);

    const handleMasteringRecommendation = (message: MasteringRecommendationMessage) => {
      const payload = message.data;
      if (payload?.track_id === trackId) {
        const rec = payload;
        cache.current[trackId] = rec;
        setRecommendation(rec);
        setIsLoading(false);
        setIsTimedOut(false);
        if (timeoutRef.current) clearTimeout(timeoutRef.current);
      }
    };

    // Subscribe to mastering recommendation messages
    const unsubscribe = subscribe(
      'mastering_recommendation',
      handleMasteringRecommendation as (msg: AnyWebSocketMessage | WebSocketMessage) => void
    );

    // Start loading indicator
    setIsLoading(true);
    setIsTimedOut(false);

    // Timeout fallback: reset loading after 10s if no WS response (#2994)
    timeoutRef.current = setTimeout(() => {
      setIsLoading(false);
      setIsTimedOut(true);
    }, RECOMMENDATION_TIMEOUT_MS);

    return () => {
      unsubscribe?.();
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
      // Do NOT setIsLoading(false) here — the next effect run sets it true
      // again immediately, producing a one-render false→true flicker on rapid
      // trackId changes. Let the next effect own the loading lifecycle (#3971).
    };
  }, [trackId, subscribe]);

  // Method to clear cached recommendation
  const clearRecommendation = useCallback(() => {
    setRecommendation(null);
    if (trackId) {
      delete cache.current[trackId];
    }
  }, [trackId]);

  return {
    recommendation,
    isLoading,
    isTimedOut,
    clearRecommendation,
    isHybrid: recommendation?.is_hybrid ?? false
  };
};

export default useMasteringRecommendation;
