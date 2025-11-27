/**
 * useMasteringRecommendation Hook
 *
 * Manages WebSocket messages for mastering profile recommendations (Priority 4).
 * Subscribes to mastering_recommendation events and caches recommendations per track.
 */

import { useState, useEffect, useCallback } from 'react';
import { useWebSocket } from '../contexts/WebSocketContext';

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

interface MasteringRecommendationCache {
  [trackId: number]: MasteringRecommendationData;
}

export const useMasteringRecommendation = (trackId?: number) => {
  const { subscribe, unsubscribe } = useWebSocket();
  const [recommendation, setRecommendation] = useState<MasteringRecommendationData | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [cache] = useState<MasteringRecommendationCache>({});

  // Handle incoming mastering recommendation messages
  useEffect(() => {
    if (!trackId) return;

    // Check cache first
    if (cache[trackId]) {
      setRecommendation(cache[trackId]);
      return;
    }

    const handleMasteringRecommendation = (data: any) => {
      if (data.data?.track_id === trackId) {
        const rec = data.data as MasteringRecommendationData;
        cache[trackId] = rec;
        setRecommendation(rec);
        setIsLoading(false);
      }
    };

    // Subscribe to mastering recommendation messages
    subscribe('mastering_recommendation', handleMasteringRecommendation);

    // Start loading indicator
    setIsLoading(true);

    return () => {
      unsubscribe('mastering_recommendation', handleMasteringRecommendation);
    };
  }, [trackId, subscribe, unsubscribe, cache]);

  // Method to clear cached recommendation
  const clearRecommendation = useCallback(() => {
    setRecommendation(null);
    if (trackId) {
      delete cache[trackId];
    }
  }, [trackId, cache]);

  return {
    recommendation,
    isLoading,
    clearRecommendation,
    isHybrid: recommendation?.is_hybrid ?? false
  };
};

export default useMasteringRecommendation;
