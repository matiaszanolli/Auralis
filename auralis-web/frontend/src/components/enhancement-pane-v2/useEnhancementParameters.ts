import { useState, useEffect, useCallback } from 'react';

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
 * useEnhancementParameters - Fetches and polls processing parameters
 *
 * Automatically fetches parameters when enhancement is enabled.
 * Polls for updates every 2 seconds while enabled.
 */
export const useEnhancementParameters = ({ enabled }: UseEnhancementParametersProps) => {
  const [params, setParams] = useState<ProcessingParams | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);

  const fetchParams = useCallback(async () => {
    try {
      setIsAnalyzing(true);
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 5000); // 5 second timeout

      const response = await fetch('/api/processing/parameters', { signal: controller.signal });
      clearTimeout(timeoutId);

      if (response.ok) {
        const data = await response.json();
        setParams(data);
      }
    } catch (err) {
      // Silently ignore network errors and aborts (backend not ready yet)
    } finally {
      setIsAnalyzing(false);
    }
  }, []);

  // Fetch params on mount and when enabled changes
  useEffect(() => {
    let interval: NodeJS.Timeout | undefined;

    if (enabled) {
      fetchParams();
      // Poll for updates every 2 seconds when enabled
      interval = setInterval(fetchParams, 2000);
    }

    return () => {
      if (interval) clearInterval(interval);
    };
  }, [enabled, fetchParams]);

  return {
    params,
    isAnalyzing,
  };
};
