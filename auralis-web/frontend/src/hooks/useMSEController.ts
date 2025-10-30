/**
 * useMSEController - Media Source Extensions Controller Hook
 *
 * Manages MSE (Media Source Extensions) for progressive audio streaming
 * with instant preset switching and intelligent buffer management.
 *
 * Features:
 * - Progressive chunk loading (30s chunks with WebM/Opus encoding)
 * - Instant preset switching (< 100ms with L1 cache)
 * - Multi-tier buffer integration (L1/L2/L3 caching)
 * - Automatic buffer management and cleanup
 *
 * @see docs/sessions/oct30_beta7_mse_migration/BETA7_MSE_MIGRATION_PLAN.md
 */

import { useState, useEffect, useRef, useCallback } from 'react';

const CHUNK_DURATION = 30; // seconds
const MIME_TYPE = 'audio/webm; codecs="opus"';

interface MSEState {
  isSupported: boolean;
  isReady: boolean;
  error: string | null;
  currentChunk: number;
  loadedChunks: Set<number>;
  bufferedRanges: TimeRanges | null;
}

interface ChunkLoadOptions {
  trackId: number;
  chunkIndex: number;
  preset: string;
  intensity: number;
}

export function useMSEController() {
  const [state, setState] = useState<MSEState>({
    isSupported: false,
    isReady: false,
    error: null,
    currentChunk: 0,
    loadedChunks: new Set(),
    bufferedRanges: null,
  });

  const mediaSourceRef = useRef<MediaSource | null>(null);
  const sourceBufferRef = useRef<SourceBuffer | null>(null);
  const objectUrlRef = useRef<string | null>(null);
  const pendingChunksRef = useRef<ArrayBuffer[]>([]);
  const isAppendingRef = useRef(false);

  /**
   * Check if MSE is supported in the current browser
   */
  useEffect(() => {
    const isSupported = 'MediaSource' in window && MediaSource.isTypeSupported(MIME_TYPE);

    if (!isSupported) {
      setState(prev => ({
        ...prev,
        isSupported: false,
        error: 'MediaSource Extensions not supported in this browser. Please use Chrome, Firefox, or Edge.',
      }));
      console.warn('MSE not supported, falling back to HTML5 audio');
    } else {
      setState(prev => ({ ...prev, isSupported: true }));
    }
  }, []);

  /**
   * Initialize MediaSource and SourceBuffer
   */
  const initializeMSE = useCallback((): string | null => {
    if (!state.isSupported) {
      return null;
    }

    try {
      // Create MediaSource
      const mediaSource = new MediaSource();
      mediaSourceRef.current = mediaSource;

      // Create object URL for the audio element
      const objectUrl = URL.createObjectURL(mediaSource);
      objectUrlRef.current = objectUrl;

      // Handle sourceopen event
      mediaSource.addEventListener('sourceopen', () => {
        try {
          // Add SourceBuffer with WebM/Opus codec
          const sourceBuffer = mediaSource.addSourceBuffer(MIME_TYPE);
          sourceBufferRef.current = sourceBuffer;

          // Handle updateend event (buffer update complete)
          sourceBuffer.addEventListener('updateend', () => {
            isAppendingRef.current = false;

            // Process pending chunks if any
            if (pendingChunksRef.current.length > 0) {
              const nextChunk = pendingChunksRef.current.shift();
              if (nextChunk && sourceBuffer && !sourceBuffer.updating) {
                appendChunkToBuffer(nextChunk);
              }
            }

            // Update buffered ranges
            setState(prev => ({
              ...prev,
              bufferedRanges: sourceBuffer.buffered,
            }));
          });

          // Handle error event
          sourceBuffer.addEventListener('error', (e) => {
            console.error('SourceBuffer error:', e);
            setState(prev => ({
              ...prev,
              error: 'SourceBuffer error during playback',
            }));
          });

          // Mark as ready
          setState(prev => ({ ...prev, isReady: true, error: null }));
          console.log('✅ MSE initialized successfully');

        } catch (err) {
          console.error('Failed to add SourceBuffer:', err);
          setState(prev => ({
            ...prev,
            error: `Failed to initialize SourceBuffer: ${err}`,
          }));
        }
      });

      // Handle sourceended event
      mediaSource.addEventListener('sourceended', () => {
        console.log('MediaSource ended');
      });

      // Handle error event
      mediaSource.addEventListener('error', (e) => {
        console.error('MediaSource error:', e);
        setState(prev => ({
          ...prev,
          error: 'MediaSource error during initialization',
        }));
      });

      return objectUrl;

    } catch (err) {
      console.error('Failed to initialize MSE:', err);
      setState(prev => ({
        ...prev,
        error: `Failed to initialize MediaSource: ${err}`,
      }));
      return null;
    }
  }, [state.isSupported]);

  /**
   * Append chunk data to SourceBuffer
   */
  const appendChunkToBuffer = useCallback((arrayBuffer: ArrayBuffer) => {
    const sourceBuffer = sourceBufferRef.current;

    if (!sourceBuffer || sourceBuffer.updating) {
      // Buffer is updating, queue the chunk
      pendingChunksRef.current.push(arrayBuffer);
      return;
    }

    try {
      isAppendingRef.current = true;
      sourceBuffer.appendBuffer(arrayBuffer);
    } catch (err) {
      console.error('Failed to append chunk to buffer:', err);
      setState(prev => ({
        ...prev,
        error: `Failed to append chunk: ${err}`,
      }));
      isAppendingRef.current = false;
    }
  }, []);

  /**
   * Load a single chunk from the backend
   */
  const loadChunk = useCallback(async (options: ChunkLoadOptions): Promise<boolean> => {
    const { trackId, chunkIndex, preset, intensity } = options;

    try {
      console.log(`📦 Loading chunk ${chunkIndex} (preset: ${preset})`);

      const response = await fetch(
        `/api/mse_streaming/chunk/${trackId}/${chunkIndex}?preset=${preset}&intensity=${intensity}`,
        {
          headers: {
            'Accept': 'audio/webm',
          },
        }
      );

      if (!response.ok) {
        throw new Error(`Failed to load chunk ${chunkIndex}: ${response.status} ${response.statusText}`);
      }

      const cacheTier = response.headers.get('X-Cache-Tier');
      if (cacheTier) {
        console.log(`💾 Chunk ${chunkIndex} served from cache tier: ${cacheTier}`);
      }

      const arrayBuffer = await response.arrayBuffer();

      // Append to buffer
      appendChunkToBuffer(arrayBuffer);

      // Mark chunk as loaded
      setState(prev => ({
        ...prev,
        loadedChunks: new Set([...prev.loadedChunks, chunkIndex]),
      }));

      console.log(`✅ Chunk ${chunkIndex} loaded successfully (${(arrayBuffer.byteLength / 1024).toFixed(1)} KB)`);
      return true;

    } catch (err) {
      console.error(`❌ Failed to load chunk ${chunkIndex}:`, err);
      setState(prev => ({
        ...prev,
        error: `Failed to load chunk ${chunkIndex}: ${err}`,
      }));
      return false;
    }
  }, [appendChunkToBuffer]);

  /**
   * Clear the SourceBuffer (for preset switching or seeking)
   */
  const clearBuffer = useCallback(async (): Promise<boolean> => {
    const sourceBuffer = sourceBufferRef.current;

    if (!sourceBuffer) {
      return false;
    }

    // Wait for any pending updates to complete
    while (sourceBuffer.updating) {
      await new Promise(resolve => setTimeout(resolve, 10));
    }

    try {
      if (sourceBuffer.buffered.length > 0) {
        const start = sourceBuffer.buffered.start(0);
        const end = sourceBuffer.buffered.end(sourceBuffer.buffered.length - 1);

        sourceBuffer.remove(start, end);

        // Wait for removal to complete
        await new Promise<void>((resolve) => {
          const checkRemoval = () => {
            if (!sourceBuffer.updating) {
              resolve();
            } else {
              setTimeout(checkRemoval, 10);
            }
          };
          checkRemoval();
        });

        console.log('🧹 Buffer cleared successfully');
      }

      // Clear loaded chunks tracking
      setState(prev => ({
        ...prev,
        loadedChunks: new Set(),
      }));

      return true;

    } catch (err) {
      console.error('Failed to clear buffer:', err);
      return false;
    }
  }, []);

  /**
   * Update current chunk based on playback position
   */
  const updateCurrentChunk = useCallback((currentTime: number) => {
    const chunk = Math.floor(currentTime / CHUNK_DURATION);
    setState(prev => {
      if (prev.currentChunk !== chunk) {
        return { ...prev, currentChunk: chunk };
      }
      return prev;
    });
  }, []);

  /**
   * Cleanup on unmount
   */
  useEffect(() => {
    return () => {
      // Revoke object URL to prevent memory leaks
      if (objectUrlRef.current) {
        URL.revokeObjectURL(objectUrlRef.current);
        objectUrlRef.current = null;
      }

      // Clear MediaSource
      if (mediaSourceRef.current) {
        const mediaSource = mediaSourceRef.current;
        if (mediaSource.readyState === 'open') {
          try {
            mediaSource.endOfStream();
          } catch (err) {
            console.warn('Failed to end MediaSource:', err);
          }
        }
        mediaSourceRef.current = null;
      }

      // Clear SourceBuffer
      sourceBufferRef.current = null;

      // Clear pending chunks
      pendingChunksRef.current = [];
    };
  }, []);

  return {
    // State
    isSupported: state.isSupported,
    isReady: state.isReady,
    error: state.error,
    currentChunk: state.currentChunk,
    loadedChunks: state.loadedChunks,
    bufferedRanges: state.bufferedRanges,

    // Methods
    initializeMSE,
    loadChunk,
    clearBuffer,
    updateCurrentChunk,

    // Refs (for advanced usage)
    mediaSource: mediaSourceRef.current,
    sourceBuffer: sourceBufferRef.current,
  };
}
