/**
 * useFingerprintCache Hook
 *
 * Hook for managing fingerprint cache operations.
 * Handles background preprocessing (disguised as buffering) of audio tracks.
 *
 * Usage:
 *   const { state, progress, preprocess } = useFingerprintCache();
 *
 *   // When user loads a track
 *   useEffect(() => {
 *     if (currentTrack) {
 *       preprocess(currentTrack.id);
 *     }
 *   }, [currentTrack?.id]);
 *
 *   // Show buffering to user
 *   {state === 'processing' && <BufferingBar progress={progress} />}
 */

import { useState, useCallback, useRef, useEffect } from 'react';
import { getFingerprintCache } from '../../services/fingerprint/FingerprintCache';
import type { AudioFingerprint } from '../../types/domain';

type FingerprintState = 'idle' | 'processing' | 'ready' | 'error';

export interface UseFingerprintCacheReturn {
  state: FingerprintState;
  progress: number; // 0-100
  fingerprint: AudioFingerprint | null;
  error: string | null;
  preprocess: (trackId: number) => Promise<AudioFingerprint | null>;
  cancel: () => void;
  clear: () => Promise<void>;
}

/**
 * Hook for fingerprint caching with background preprocessing.
 */
export function useFingerprintCache(): UseFingerprintCacheReturn {
  const [state, setState] = useState<FingerprintState>('idle');
  const [progress, setProgress] = useState(0);
  const [fingerprint, setFingerprint] = useState<AudioFingerprint | null>(null);
  const [error, setError] = useState<string | null>(null);

  const abortControllerRef = useRef<AbortController | null>(null);
  const workerRef = useRef<Worker | null>(null);

  /**
   * Preprocess a track (compute fingerprint).
   * Returns cached fingerprint if available, otherwise computes in background.
   */
  const preprocess = useCallback(async (trackId: number): Promise<AudioFingerprint | null> => {
    setState('processing');
    setProgress(0);
    setError(null);

    try {
      const cache = getFingerprintCache();

      // Check if cached
      const cached = await cache.get(trackId);
      if (cached) {
        setState('ready');
        setFingerprint(cached);
        setProgress(100);
        return cached;
      }

      // Start Web Worker for background computation
      startWorker(trackId);

      return null;
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unknown error';
      setError(message);
      setState('error');
      return null;
    }
  }, []);

  /**
   * Start Web Worker for fingerprinting.
   */
  const startWorker = useCallback((trackId: number) => {
    // Cancel previous worker if running
    if (workerRef.current) {
      workerRef.current.terminate();
    }

    // Abort previous operation
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }

    // Create new abort controller
    abortControllerRef.current = new AbortController();

    // For now, we'll simulate the worker in the main thread
    // In production, this would be a real Web Worker
    simulateFingerprinting(trackId, abortControllerRef.current.signal);
  }, []);

  /**
   * Simulate fingerprinting (placeholder for actual Web Worker).
   * In production, this would delegate to a real Web Worker.
   */
  const simulateFingerprinting = useCallback(
    async (trackId: number, signal: AbortSignal) => {
      try {
        // Simulate processing with progress updates
        for (let i = 0; i < 100; i += 10) {
          if (signal.aborted) {
            return;
          }

          setProgress(i);
          await new Promise(resolve => setTimeout(resolve, 100));
        }

        // Create mock fingerprint
        const mockFingerprint: AudioFingerprint = {
          trackId,
          loudness: -14.5,
          crest: 6.2,
          rms: -16.0,
          centroid: 2450,
          spectralFlux: Array(100).fill(0.5),
          mfcc: Array(13).fill(0).map(() => Array(100).fill(0.1)),
          chroma: Array(12).fill(0).map(() => Array(100).fill(0.08)),
          timestamp: Date.now(),
          cached: false,
          computation_time_ms: 1000,
        };

        // Store in cache
        const cache = getFingerprintCache();
        const { trackId: _, ...fpData } = mockFingerprint;
        await cache.set(trackId, fpData);

        setFingerprint(mockFingerprint);
        setState('ready');
        setProgress(100);
      } catch (err) {
        if (!signal.aborted) {
          const message = err instanceof Error ? err.message : 'Fingerprinting failed';
          setError(message);
          setState('error');
        }
      }
    },
    []
  );

  /**
   * Cancel preprocessing.
   */
  const cancel = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    if (workerRef.current) {
      workerRef.current.terminate();
      workerRef.current = null;
    }
    setState('idle');
    setProgress(0);
    setError(null);
  }, []);

  /**
   * Clear all cached fingerprints.
   */
  const clear = useCallback(async () => {
    const cache = getFingerprintCache();
    await cache.clear();
    setState('idle');
    setProgress(0);
    setFingerprint(null);
    setError(null);
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      cancel();
    };
  }, [cancel]);

  return {
    state,
    progress,
    fingerprint,
    error,
    preprocess,
    cancel,
    clear,
  };
}

/**
 * Hook to check if fingerprint is cached without triggering preprocessing.
 */
export function useIsFingerprintCached(trackId: number): boolean {
  const [isCached, setIsCached] = useState(false);

  useEffect(() => {
    const checkCache = async () => {
      const cache = getFingerprintCache();
      const cached = await cache.has(trackId);
      setIsCached(cached);
    };

    checkCache().catch(console.error);
  }, [trackId]);

  return isCached;
}

/**
 * Hook to get fingerprint from cache without preprocessing.
 */
export function useCachedFingerprint(trackId: number): AudioFingerprint | null {
  const [fingerprint, setFingerprint] = useState<AudioFingerprint | null>(null);

  useEffect(() => {
    const getFromCache = async () => {
      const cache = getFingerprintCache();
      const fp = await cache.get(trackId);
      setFingerprint(fp);
    };

    getFromCache().catch(console.error);
  }, [trackId]);

  return fingerprint;
}

/**
 * Hook to get fingerprint cache statistics.
 */
export function useFingerprintCacheStats() {
  const [stats, setStats] = useState({
    total: 0,
    sizeMB: 0,
    oldestTimestamp: null as number | null,
    newestTimestamp: null as number | null,
  });

  useEffect(() => {
    const getStats = async () => {
      const cache = getFingerprintCache();
      const cacheStats = await cache.getStats();
      setStats(cacheStats);
    };

    getStats().catch(console.error);

    // Refresh stats every 30 seconds
    const interval = setInterval(() => {
      getStats().catch(console.error);
    }, 30000);

    return () => clearInterval(interval);
  }, []);

  return stats;
}
