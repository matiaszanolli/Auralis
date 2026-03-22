/**
 * useMasteringRecommendation Hook
 *
 * Manages WebSocket messages for mastering profile recommendations (Priority 4).
 * Subscribes to mastering_recommendation events and caches recommendations per track.
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { useWebSocketContext } from '@/contexts/WebSocketContext';
import type { AnyWebSocketMessage, WebSocketMessage } from '@/types/websocket';

export interface MasteringRecommendationData {
  track_id: number;
  primary_profile_id: string;
  primary_profile_name: string;
  confidence_score: number;
  predicted_loudness_change: number;
  predicted_crest_change: number;
  predicted_centroid_change: number;
  weighted_profiles?: Array<{
    profile_id: string;
    profile_name: string;
    weight: number;
  }>;
  reasoning?: string;
  is_hybrid?: boolean;
  created?: string;
  alternative_profiles?: Array<{
    id: string;
    name: string;
  }>;
}

/** WebSocket message shape for mastering_recommendation events */
interface MasteringRecommendationMessage {
  type: 'mastering_recommendation';
  data: MasteringRecommendationData;
}

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

  // Handle incoming mastering recommendation messages
  useEffect(() => {
    if (!trackId) return;

    // Check cache first
    if (cache.current[trackId]) {
      setRecommendation(cache.current[trackId]);
      return;
    }

    let timedOut = false;

    const handleMasteringRecommendation = (message: MasteringRecommendationMessage) => {
      const payload = message.data;
      if (payload?.track_id === trackId) {
        const rec = payload;
        cache.current[trackId] = rec;
        setRecommendation(rec);
        setIsLoading(false);
        setIsTimedOut(false);
        clearTimeout(timeout);
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
    const timeout = setTimeout(() => {
      timedOut = true;
      setIsLoading(false);
      setIsTimedOut(true);
    }, RECOMMENDATION_TIMEOUT_MS);

    return () => {
      unsubscribe?.();
      clearTimeout(timeout);
      if (!timedOut) setIsLoading(false);
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
