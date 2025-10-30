/**
 * BottomPlayerBarMSE - MSE-Based Audio Playback
 *
 * Progressive streaming implementation using Media Source Extensions
 * for instant preset switching and intelligent buffer management.
 *
 * Features:
 * - Progressive chunk loading (< 100ms playback start)
 * - Instant preset switching (< 100ms with L1 cache)
 * - Multi-tier buffer integration (L1/L2/L3)
 * - Continuous prefetching (stay 2-3 chunks ahead)
 */

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useMSEController } from '../hooks/useMSEController';
import { useEnhancement } from '../contexts/EnhancementContext';
import { usePlayerAPI } from '../hooks/usePlayerAPI';
import {
  calculateTotalChunks,
  getChunkIndexForTime,
  getChunksToPrefetch,
} from '../services/mseStreamingService';

const CHUNK_DURATION = 30; // seconds
const PREFETCH_COUNT = 2; // Load 2 chunks ahead

interface MSEPlayerProps {
  onReady?: () => void;
  onError?: (error: string) => void;
}

export const MSEPlayer: React.FC<MSEPlayerProps> = ({ onReady, onError }) => {
  const audioRef = useRef<HTMLAudioElement>(null);
  const [isLoadingFirstChunk, setIsLoadingFirstChunk] = useState(false);
  const [totalChunks, setTotalChunks] = useState(0);
  const prefetchingRef = useRef(false);

  // Hooks
  const mse = useMSEController();
  const { currentTrack, isPlaying, duration } = usePlayerAPI();
  const { settings: enhancementSettings } = useEnhancement();

  /**
   * Initialize MSE on mount
   */
  useEffect(() => {
    if (!mse.isSupported) {
      onError?.('MSE not supported in this browser');
      return;
    }

    const objectUrl = mse.initializeMSE();
    if (objectUrl && audioRef.current) {
      audioRef.current.src = objectUrl;
      console.log('✅ MSE initialized, object URL set');
    }
  }, [mse.isSupported]);

  /**
   * Notify when MSE is ready
   */
  useEffect(() => {
    if (mse.isReady) {
      console.log('✅ MSE ready for playback');
      onReady?.();
    }
  }, [mse.isReady, onReady]);

  /**
   * Handle errors
   */
  useEffect(() => {
    if (mse.error) {
      console.error('❌ MSE error:', mse.error);
      onError?.(mse.error);
    }
  }, [mse.error, onError]);

  /**
   * Calculate total chunks when track changes
   */
  useEffect(() => {
    if (currentTrack && duration) {
      const chunks = calculateTotalChunks(duration);
      setTotalChunks(chunks);
      console.log(`📊 Track has ${chunks} chunks (${duration}s / ${CHUNK_DURATION}s)`);
    }
  }, [currentTrack, duration]);

  /**
   * Load first chunk and start playback when track changes
   */
  useEffect(() => {
    if (!currentTrack || !mse.isReady || !enhancementSettings.enabled) {
      return;
    }

    const loadAndPlay = async () => {
      try {
        setIsLoadingFirstChunk(true);

        // Clear previous buffer
        await mse.clearBuffer();

        console.log(`🎵 Loading first chunk for track ${currentTrack.id}`);

        // Load first chunk
        const success = await mse.loadChunk({
          trackId: currentTrack.id,
          chunkIndex: 0,
          preset: enhancementSettings.preset,
          intensity: enhancementSettings.intensity,
        });

        if (!success) {
          throw new Error('Failed to load first chunk');
        }

        setIsLoadingFirstChunk(false);

        // Start playback if backend says it's playing
        if (isPlaying && audioRef.current) {
          audioRef.current.play().catch(err => {
            console.warn('Failed to auto-play:', err);
          });
        }

        // Prefetch next chunks in background
        prefetchNextChunks(0);

      } catch (err) {
        console.error('❌ Failed to load first chunk:', err);
        setIsLoadingFirstChunk(false);
        onError?.(`Failed to load audio: ${err}`);
      }
    };

    loadAndPlay();
  }, [currentTrack, mse.isReady, enhancementSettings.enabled]);

  /**
   * Prefetch chunks ahead of current position
   */
  const prefetchNextChunks = useCallback(async (currentChunk: number) => {
    if (prefetchingRef.current || !currentTrack || !mse.isReady || !enhancementSettings.enabled) {
      return;
    }

    prefetchingRef.current = true;

    try {
      const chunksToPrefetch = getChunksToPrefetch(currentChunk, totalChunks, PREFETCH_COUNT);

      if (chunksToPrefetch.length === 0) {
        prefetchingRef.current = false;
        return;
      }

      console.log(`🔄 Prefetching chunks: ${chunksToPrefetch.join(', ')}`);

      // Load chunks in parallel
      await Promise.all(
        chunksToPrefetch.map(async (chunkIndex) => {
          // Skip if already loaded
          if (mse.loadedChunks.has(chunkIndex)) {
            return;
          }

          return mse.loadChunk({
            trackId: currentTrack.id,
            chunkIndex,
            preset: enhancementSettings.preset,
            intensity: enhancementSettings.intensity,
          });
        })
      );

      console.log(`✅ Prefetched ${chunksToPrefetch.length} chunks`);

    } catch (err) {
      console.warn('⚠️ Prefetch failed:', err);
    } finally {
      prefetchingRef.current = false;
    }
  }, [currentTrack, mse.isReady, mse.loadedChunks, enhancementSettings, totalChunks]);

  /**
   * Handle time updates - update current chunk and prefetch
   */
  const handleTimeUpdate = useCallback(() => {
    if (!audioRef.current) return;

    const currentTime = audioRef.current.currentTime;
    const currentChunk = getChunkIndexForTime(currentTime);

    // Update current chunk in MSE controller
    mse.updateCurrentChunk(currentTime);

    // Prefetch next chunks if we're close to the end of current chunk
    const chunkProgress = (currentTime % CHUNK_DURATION) / CHUNK_DURATION;
    if (chunkProgress > 0.7) {
      // When 70% through current chunk, start prefetching
      prefetchNextChunks(currentChunk);
    }
  }, [mse.updateCurrentChunk, prefetchNextChunks]);

  /**
   * Handle preset changes - instant preset switching
   */
  useEffect(() => {
    const switchPreset = async () => {
      if (!currentTrack || !mse.isReady || !audioRef.current || !enhancementSettings.enabled) {
        return;
      }

      const currentTime = audioRef.current.currentTime;
      const currentChunk = getChunkIndexForTime(currentTime);

      console.log(`🔄 Switching to preset: ${enhancementSettings.preset}`);

      try {
        // Clear buffer
        await mse.clearBuffer();

        // Load new preset chunk at current position
        const success = await mse.loadChunk({
          trackId: currentTrack.id,
          chunkIndex: currentChunk,
          preset: enhancementSettings.preset,
          intensity: enhancementSettings.intensity,
        });

        if (!success) {
          throw new Error('Failed to load chunk with new preset');
        }

        // Resume playback at same position
        audioRef.current.currentTime = currentTime;
        if (isPlaying) {
          audioRef.current.play().catch(err => {
            console.warn('Failed to resume playback:', err);
          });
        }

        // Prefetch next chunks with new preset
        prefetchNextChunks(currentChunk);

        console.log(`✅ Preset switched to: ${enhancementSettings.preset}`);

      } catch (err) {
        console.error('❌ Preset switch failed:', err);
        onError?.(`Failed to switch preset: ${err}`);
      }
    };

    // Debounce preset changes (wait 100ms)
    const timer = setTimeout(switchPreset, 100);
    return () => clearTimeout(timer);

  }, [enhancementSettings.preset, enhancementSettings.intensity]);

  /**
   * Sync playback state with backend
   */
  useEffect(() => {
    if (!audioRef.current) return;

    if (isPlaying && audioRef.current.paused) {
      audioRef.current.play().catch(err => {
        console.warn('Failed to sync play state:', err);
      });
    } else if (!isPlaying && !audioRef.current.paused) {
      audioRef.current.pause();
    }
  }, [isPlaying]);

  return (
    <>
      <audio
        ref={audioRef}
        style={{ display: 'none' }}
        onTimeUpdate={handleTimeUpdate}
        onLoadStart={() => console.log('⏳ MSE loading started')}
        onCanPlay={() => console.log('✅ MSE can play')}
        onPlaying={() => console.log('▶️ MSE playing')}
        onPause={() => console.log('⏸️ MSE paused')}
        onError={(e) => {
          const error = audioRef.current?.error;
          console.error('❌ MSE playback error:', error);
          onError?.(error?.message || 'Unknown playback error');
        }}
      />

      {/* Debug info */}
      {mse.isReady && (
        <div style={{ display: 'none' }}>
          MSE Ready | Current Chunk: {mse.currentChunk} | Loaded: {mse.loadedChunks.size} | Loading: {isLoadingFirstChunk}
        </div>
      )}
    </>
  );
};

export default MSEPlayer;
