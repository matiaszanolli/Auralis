/**
 * useEnhancedPlayCommand Hook
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Owns the `playEnhanced` command: it tears down any prior stream, loads the
 * track metadata (so currentTrack is set before backend confirmation), records
 * the track params for later seeks, sets the buffering state for instant UI
 * feedback, sends the `play_enhanced` message, and arms the first-stream
 * watchdog. Subscriptions are set up elsewhere (on mount), so this only prepares
 * state and sends the request.
 *
 * Extracted from usePlayEnhanced (#4077).
 *
 * @module hooks/enhancement/useEnhancedPlayCommand
 */

const DEBUG = import.meta.env.DEV;

import { useCallback } from 'react';
import type { MutableRefObject } from 'react';
import type { AppDispatch } from '@/store';
import { useWebSocketContext } from '@/contexts/WebSocketContext';
import { getApiUrl } from '@/config/api';
import {
  startStreaming,
  setStreamingError,
  resetStreaming,
  setCurrentTrackAndSyncQueue,
} from '@/store/slices/playerSlice';
import type { EnhancementPreset } from '@/types/domain';
import type { StreamingCoreReturn } from './useAudioStreamingCore';
import type { CurrentTrackInfo } from './useEnhancedStreamStart';

type WebSocketContextValue = ReturnType<typeof useWebSocketContext>;

export interface UseEnhancedPlayCommandParams {
  wsContext: WebSocketContextValue;
  dispatch: AppDispatch;
  core: StreamingCoreReturn;
  currentTrackInfoRef: MutableRefObject<CurrentTrackInfo | null>;
  /** Reset the fingerprint status/message when a new stream begins. */
  resetFingerprint: () => void;
}

export type PlayEnhanced = (
  trackId: number,
  preset: EnhancementPreset,
  intensity: number
) => Promise<void>;

export function useEnhancedPlayCommand({
  wsContext,
  dispatch,
  core,
  currentTrackInfoRef,
  resetFingerprint,
}: UseEnhancedPlayCommandParams): PlayEnhanced {
  return useCallback(
    async (trackId: number, preset: EnhancementPreset, intensity: number) => {
      try {
        // Stop any existing playback
        core.playbackEngineRef.current?.stopPlayback();
        // Release the prior ~100 MB buffer before dropping the ref (#4147)
        core.pcmBufferRef.current?.dispose();
        core.pcmBufferRef.current = null;
        core.streamingMetadataRef.current = null;
        core.pendingChunksRef.current = [];
        core.lastReceivedChunkIndexRef.current = -1;

        // Reset streaming state
        dispatch(resetStreaming('enhanced'));

        // Reset fingerprint status
        resetFingerprint();

        // Check WebSocket connection before proceeding
        if (!wsContext.isConnected) {
          throw new Error('WebSocket not connected. Please wait for connection and try again.');
        }

        // Load track data from backend so we can set currentTrack (fixes #2258)
        // AbortController cancels fetch on unmount/re-invocation (#2780)
        core.abortRef.current?.abort();
        core.abortRef.current = new AbortController();
        try {
          const response = await fetch(getApiUrl(`/api/library/tracks/${trackId}`), {
            signal: core.abortRef.current.signal,
          });
          if (response.ok) {
            const track = await response.json();
            // #3587: keep queue.currentIndex aligned with player.currentTrack
            // for the duration before backend WS confirmation arrives.
            dispatch(setCurrentTrackAndSyncQueue(track));
            DEBUG && console.log('[usePlayEnhanced] Set current track:', track.title);
          }
        } catch (err) {
          if (err instanceof DOMException && err.name === 'AbortError') return;
          DEBUG && console.warn('[usePlayEnhanced] Failed to load track data:', err);
          // Continue anyway - playback will still work
        }

        // Store track info for seek operations
        currentTrackInfoRef.current = {
          trackId,
          preset,
          intensity,
        };

        // Set buffering state immediately for instant user feedback
        dispatch(startStreaming({
          streamType: 'enhanced',
          trackId,
          totalChunks: 0, // Will be updated when stream starts
          intensity,
        }));

        // Send play_enhanced message to backend
        // Subscriptions are already set up on mount
        wsContext.send({
          type: 'play_enhanced',
          data: {
            track_id: trackId,
            preset,
            intensity,
          },
        });

        // Arm the first-stream watchdog so a hung worker that never emits any
        // stream message surfaces an error instead of leaving the UI stuck in
        // 'buffering' (#4433). Cleared by the core on the first stream message.
        core.armStreamStartWatchdog();

        DEBUG && console.log('[usePlayEnhanced] Play enhanced requested (buffering...):', {
          trackId,
          preset,
          intensity,
        });
      } catch (error) {
        const errorMsg = `Failed to start enhanced playback: ${error instanceof Error ? error.message : String(error)}`;
        console.error('[usePlayEnhanced]', errorMsg);
        dispatch(setStreamingError({ streamType: 'enhanced', error: errorMsg }));
      }
    },
    [wsContext, dispatch, core, currentTrackInfoRef, resetFingerprint]
  );
}
