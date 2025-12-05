import { useState, useEffect, useCallback, useRef } from 'react';
import { getApiUrl } from '../../../config/api';

export interface ProcessingParams {
  // 3D space coordinates (0-1)
  spectral_balance: number;
  dynamic_range: number;
  energy_level: number;

  // Target parameters
  target_lufs: number;
  peak_target_db: number;

  // EQ adjustments
  bass_boost: number;
  air_boost: number;

  // Dynamics
  compression_amount: number;
  expansion_amount: number;

  // Stereo
  stereo_width: number;
}

export interface UseEnhancementParametersProps {
  enabled: boolean;
}

/**
 * useEnhancementParameters - Fetches processing parameters on-demand
 *
 * Smart fetching strategy:
 * - Fetches only on mount and when enabled toggles
 * - Prevents request flooding with deduplication
 * - Uses correct API endpoint via getApiUrl
 * - Caches results to reduce backend load
 */
export const useEnhancementParameters = ({ enabled }: UseEnhancementParametersProps) => {
  const [params, setParams] = useState<ProcessingParams | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);

  // Track in-flight requests and cache timestamp to prevent duplicate fetches
  const inFlightRef = useRef<Promise<ProcessingParams | null> | null>(null);
  const lastFetchTimeRef = useRef<number>(0);
  const CACHE_DURATION_MS = 30000; // Cache for 30 seconds

  const fetchParams = useCallback(async () => {
    // Skip if request already in-flight
    if (inFlightRef.current) {
      return inFlightRef.current;
    }

    // Skip if cache is still valid
    const now = Date.now();
    if (now - lastFetchTimeRef.current < CACHE_DURATION_MS && params) {
      return params;
    }

    try {
      setIsAnalyzing(true);
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 5000); // 5 second timeout

      // Create the fetch promise and store it to prevent duplicates
      const fetchPromise = fetch(getApiUrl('/api/processing/parameters'), {
        signal: controller.signal
      }).then(async (response) => {
        clearTimeout(timeoutId);
        if (response.ok) {
          const data = await response.json();
          setParams(data);
          lastFetchTimeRef.current = Date.now();
          return data;
        }
        return null;
      }).catch(() => {
        // Silently ignore network errors and aborts (backend not ready yet)
        return null;
      }).finally(() => {
        inFlightRef.current = null;
        setIsAnalyzing(false);
      });

      inFlightRef.current = fetchPromise;
      return await fetchPromise;
    } catch {
      inFlightRef.current = null;
      setIsAnalyzing(false);
      return null;
    }
  }, [params]);

  // Fetch params only on mount and when enabled changes (no polling)
  useEffect(() => {
    if (enabled) {
      fetchParams();
    }
  }, [enabled]);

  return {
    params,
    isAnalyzing,
  };
};
