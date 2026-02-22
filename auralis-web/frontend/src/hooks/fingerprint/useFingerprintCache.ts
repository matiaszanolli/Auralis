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
// Import the canonical 25D AudioFingerprint from its single source of truth
// (fixes #2280: the old import from '../../types/domain' used a different,
// incompatible schema with fields like trackId/loudness/crest/rms/centroid).
import type { AudioFingerprint } from '@/utils/fingerprintToGradient';

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

        // Create mock fingerprint using the canonical 25D schema
        // (fixes #2280: old mock used the removed domain.ts schema).
        const mockFingerprint: AudioFingerprint = {
          sub_bass: 0.3, bass: 0.4, low_mid: 0.35, mid: 0.5,
          upper_mid: 0.45, presence: 0.4, air: 0.25,
          lufs: -14.5, crest_db: 6.2, bass_mid_ratio: 0.8,
          spectral_centroid: 0.55, spectral_rolloff: 0.6, spectral_flatness: 0.3,
          harmonic_ratio: 0.7, pitch_stability: 0.75, chroma_energy: 0.5,
          stereo_width: 0.4, phase_correlation: 0.9,
        };

        // Store in cache
        const cache = getFingerprintCache();
        await cache.set(trackId, mockFingerprint);

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
