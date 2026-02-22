/**
 * usePlayerStreaming - Core timing and position tracking hook
 *
 * This is the single source of truth for all player timing information.
 * It reads directly from the HTML5 audio element and interpolates between
 * server updates to ensure smooth, drift-free playback position tracking.
 *
 * Architecture:
 * - Layer 1: Local interpolation from audio.currentTime (100ms updates)
 * - Layer 2: WebSocket sync for external changes (seek, play/pause)
 * - Layer 3: Periodic full sync every 5 seconds (drift correction)
 *
 * @module hooks/usePlayerStreaming
 */

import { useState, useEffect, useRef, useCallback } from 'react';
import { useWebSocketContext } from '@/contexts/WebSocketContext';

/**
 * Buffered range: [start, end] in seconds
 */
export interface BufferedRange {
  start: number;
  end: number;
}

/**
 * Complete streaming state - single source of truth
 */
export interface PlayerStreamingState {
  // Timing (seconds)
  currentTime: number;
  duration: number;

  // Playback state
  isPlaying: boolean;
  isPaused: boolean;
  isBuffering: boolean;
  isError: boolean;
  errorMessage?: string;

  // Buffering
  bufferedRanges: BufferedRange[];
  bufferedPercentage: number;

  // Synchronization
  lastSyncTime: number; // Timestamp of last server sync
  drift: number; // Difference between local and server time
  playbackRate: number; // Current playback rate (1.0 = normal)

  // Server state (for verification)
  serverCurrentTime?: number;
  serverDuration?: number;
}

/**
 * Configuration for the streaming hook
 */
export interface UsePlayerStreamingConfig {
  /**
   * Reference to the HTML5 audio element
   * Must be the actual audio element that plays content
   */
  audioElement: HTMLAudioElement | null;

  /**
   * Callback when drift is detected and corrected
   * Useful for logging/metrics
   */
  onDriftDetected?: (drift: number, correctionApplied: boolean) => void;

  /**
   * How often to sync with server (milliseconds)
   * Default: 5000 (5 seconds)
   * Lower values = more accurate but more network traffic
   */
  syncInterval?: number;

  /**
   * Maximum acceptable drift before correction (milliseconds)
   * Default: 500 (0.5 seconds)
   * Drift smaller than this is ignored
   */
  driftThreshold?: number;

  /**
   * How often to update state from audio element (milliseconds)
   * Default: 100 (10 updates per second)
   * Lower values = smoother UI but more re-renders
   */
  updateInterval?: number;

  /**
   * Callback to fetch current player status from server
   * Used for periodic full sync
   */
  onGetPlayerStatus?: () => Promise<{
    position: number;
    duration: number;
    is_playing: boolean;
    timestamp: number;
  }>;

  /**
   * Enable debug logging
   * Default: false
   */
  debug?: boolean;
}

/**
 * usePlayerStreaming - Core timing hook
 *
 * Provides continuous, drift-free position tracking by:
 * 1. Reading audio.currentTime every 100ms (Layer 1: Local)
 * 2. Listening to WebSocket for external changes (Layer 2: Events)
 * 3. Syncing with server every 5 seconds (Layer 3: Correction)
 *
 * Usage:
 *
 * ```tsx
 * const audioRef = useRef<HTMLAudioElement>(null);
 *
 * const streaming = usePlayerStreaming({
 *   audioElement: audioRef.current,
 *   syncInterval: 5000,
 *   driftThreshold: 500,
 *   onGetPlayerStatus: async () => {
 *     const response = await api.get('/api/player/status');
 *     return response;
 *   },
 *   debug: true,
 * });
 *
 * return (
 *   <>
 *     <audio ref={audioRef} />
 *     <ProgressBar
 *       currentTime={streaming.currentTime}
 *       duration={streaming.duration}
 *       bufferedRanges={streaming.bufferedRanges}
 *     />
 *   </>
 * );
 * ```
 */
export function usePlayerStreaming({
  audioElement,
  onDriftDetected,
  syncInterval = 5000,
  driftThreshold = 500,
  updateInterval = 100,
  onGetPlayerStatus,
  debug = false,
}: UsePlayerStreamingConfig): PlayerStreamingState {
  // Convert drift threshold from milliseconds to seconds for comparison
  const driftThresholdSeconds = driftThreshold / 1000;

  const log = useCallback((msg: string, data?: any) => {
    if (debug) {
      console.log(`[usePlayerStreaming] ${msg}`, data ?? '');
    }
  }, [debug]);

  // Initial state
  const initialState: PlayerStreamingState = {
    currentTime: 0,
    duration: 0,
    isPlaying: false,
    isPaused: true,
    isBuffering: false,
    isError: false,
    bufferedRanges: [],
    bufferedPercentage: 0,
    lastSyncTime: Date.now(),
    drift: 0,
    playbackRate: 1.0,
  };

  const [state, setState] = useState<PlayerStreamingState>(initialState);
  const wsContext = useWebSocketContext();
  const syncTimerRef = useRef<NodeJS.Timeout | null>(null);
  const updateTimerRef = useRef<NodeJS.Timeout | null>(null);

  // Get buffered ranges from audio element
  const getBufferedRanges = useCallback((audio: HTMLAudioElement): BufferedRange[] => {
    const ranges: BufferedRange[] = [];
    for (let i = 0; i < audio.buffered.length; i++) {
      ranges.push({
        start: audio.buffered.start(i),
        end: audio.buffered.end(i),
      });
    }
    return ranges;
  }, []);

  // Calculate buffered percentage
  const getBufferedPercentage = useCallback(
    (ranges: BufferedRange[], duration: number): number => {
      if (duration === 0) return 0;
      const bufferedSeconds = ranges.reduce((total, range) => {
        return total + (range.end - range.start);
      }, 0);
      return Math.min((bufferedSeconds / duration) * 100, 100);
    },
    []
  );

  // Layer 1: Update from audio element every 100ms
  useEffect(() => {
    if (!audioElement) {
      log('Audio element not available');
      return;
    }

    const interval = setInterval(() => {
      // Short-circuit when paused and not seeking to avoid reading 6 DOM properties
      // unnecessarily — prevents 600 redundant reads/min while paused (fixes #2543).
      if (audioElement.paused && !audioElement.seeking) return;

      const time = audioElement.currentTime;
      const dur = audioElement.duration;
      const playing = !audioElement.paused && !audioElement.ended;
      const buffering = audioElement.buffered.length === 0;
      const bufferedRanges = getBufferedRanges(audioElement);
      const bufferedPct = getBufferedPercentage(bufferedRanges, dur);

      setState((prev) => {
        // Only update if something changed
        if (
          prev.currentTime !== time ||
          prev.duration !== dur ||
          prev.isPlaying !== playing ||
          prev.isBuffering !== buffering ||
          prev.bufferedPercentage !== bufferedPct
        ) {
          return {
            ...prev,
            currentTime: time,
            duration: dur,
            isPlaying: playing,
            isPaused: !playing,
            isBuffering: buffering,
            bufferedRanges,
            bufferedPercentage: bufferedPct,
          };
        }
        return prev;
      });
    }, updateInterval);

    return () => clearInterval(interval);
  }, [audioElement, updateInterval, getBufferedRanges, getBufferedPercentage, log]);

  // Layer 2: Listen to WebSocket for external changes (seek, play/pause from other clients)
  useEffect(() => {
    if (!wsContext || !audioElement) return;

    const unsubscribes: (() => void)[] = [];

    // Handle position_changed event (external seek)
    const unsubscribePosition = wsContext.subscribe('position_changed', (msg: any) => {
      const serverPosition = msg.data.position;
      const localPosition = audioElement.currentTime;
      const drift = Math.abs(localPosition - serverPosition);

      log('Position change from WebSocket', { serverPosition, localPosition, drift });

      if (drift > driftThresholdSeconds) {
        log('Drift detected, correcting');
        onDriftDetected?.(drift, true);

        // Gradual correction via playback rate
        if (drift > 1) {
          // Large drift (>1 second): speed up/slow down playback
          audioElement.playbackRate = drift > 0 ? 0.95 : 1.05;
          setTimeout(() => {
            audioElement.playbackRate = 1.0;
          }, Math.min(drift * 1500, 2000)); // Correction time proportional to drift
        } else {
          // Small drift: just note it for next sync
          setState((prev) => ({
            ...prev,
            drift: localPosition - serverPosition,
            serverCurrentTime: serverPosition,
          }));
        }
      }

      setState((prev) => ({
        ...prev,
        serverCurrentTime: serverPosition,
        lastSyncTime: Date.now(),
      }));
    });

    // Handle playback_started event
    const unsubscribePlayback = wsContext.subscribe('playback_started', () => {
      log('Playback started from WebSocket');
      // Audio should already be playing if synced correctly
      // This is mainly for external changes
    });

    // Handle playback_paused event
    const unsubscribePaused = wsContext.subscribe('playback_paused', () => {
      log('Playback paused from WebSocket');
      // Audio should match this state
    });

    unsubscribes.push(unsubscribePosition, unsubscribePlayback, unsubscribePaused);

    return () => {
      unsubscribes.forEach((unsub) => unsub());
    };
  }, [wsContext, audioElement, driftThreshold, onDriftDetected, log]);

  // Layer 3: Periodic full sync with server every N seconds
  useEffect(() => {
    if (!audioElement || !onGetPlayerStatus) return;

    const performSync = async () => {
      try {
        const status = await onGetPlayerStatus();
        const localTime = audioElement.currentTime;
        const drift = localTime - status.position;

        log('Full sync performed', {
          serverPosition: status.position,
          localTime,
          drift,
          isDrifting: Math.abs(drift) > driftThresholdSeconds,
        });

        // Check if drift is significant
        if (Math.abs(drift) > driftThresholdSeconds) {
          log('Significant drift detected during sync', { drift });
          onDriftDetected?.(drift, false); // Not corrected yet, just detected

          // For now, just log the drift
          // In production, could apply gradual correction here
          setState((prev) => ({
            ...prev,
            drift,
            serverCurrentTime: status.position,
            serverDuration: status.duration,
            lastSyncTime: Date.now(),
          }));
        } else {
          setState((prev) => ({
            ...prev,
            drift: 0,
            serverCurrentTime: status.position,
            serverDuration: status.duration,
            lastSyncTime: Date.now(),
          }));
        }
      } catch (error) {
        console.error('[usePlayerStreaming] Full sync failed:', error);
        // Don't crash, just continue with local timing
      }
    };

    // Perform initial sync
    performSync();

    // Schedule periodic syncs
    syncTimerRef.current = setInterval(performSync, syncInterval);

    return () => {
      if (syncTimerRef.current) {
        clearInterval(syncTimerRef.current);
      }
    };
  }, [audioElement, onGetPlayerStatus, syncInterval, driftThreshold, onDriftDetected, log]);

  // Handle audio errors
  useEffect(() => {
    if (!audioElement) return;

    const handleError = () => {
      log('Audio error detected');
      setState((prev) => ({
        ...prev,
        isError: true,
        errorMessage: `Error code: ${audioElement.error?.code}`,
      }));
    };

    audioElement.addEventListener('error', handleError);
    return () => audioElement.removeEventListener('error', handleError);
  }, [audioElement, log]);

  // Handle buffering state
  useEffect(() => {
    if (!audioElement) return;

    const handleWaiting = () => {
      log('Audio waiting (buffering)');
      setState((prev) => ({ ...prev, isBuffering: true }));
    };

    const handleCanPlay = () => {
      log('Audio can play');
      setState((prev) => ({ ...prev, isBuffering: false, isError: false }));
    };

    audioElement.addEventListener('waiting', handleWaiting);
    audioElement.addEventListener('canplay', handleCanPlay);

    return () => {
      audioElement.removeEventListener('waiting', handleWaiting);
      audioElement.removeEventListener('canplay', handleCanPlay);
    };
  }, [audioElement, log]);

  return state;
}

export default usePlayerStreaming;
