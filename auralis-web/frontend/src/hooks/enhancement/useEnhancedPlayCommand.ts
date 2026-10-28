/**
 * useEnhancedPlayCommand Hook
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Owns the `playEnhanced` command: it tears down any prior stream, records
 * the track params for later seeks, sets the buffering state for instant UI
 * feedback, sends the `play_enhanced` message, and arms the first-stream
 * watchdog. Track metadata loads in the background and never gates playback
 * (#5649). Subscriptions are set up elsewhere (on mount), so this only prepares
 * state and sends the request.
 *
 * Extracted from usePlayEnhanced (#4077).
 *
 * @module hooks/enhancement/useEnhancedPlayCommand
 */

const DEBUG = import.meta.env.DEV;

import type { StreamType } from '@/types/domain';
import { useCallback } from 'react';
import type { MutableRefObject } from 'react';
import type { AppDispatch } from '@/store';
import { useWebSocketContext } from '@/contexts/WebSocketContext';
import {
  startStreaming,
  setStreamingError,
  resetStreaming,
} from '@/store/slices/playerSlice';
import { setCurrentTrackAndSyncQueue } from '@/store/slices/playerQueueSync';
import { transformTrack } from '@/api/transformers';
import type { TrackApiResponse } from '@/api/transformers/types';
import { get } from '@/utils/apiRequest';
import { isAbortError } from '@/utils/errorGuards';
import type { EnhancementPreset } from '@/types/domain';
import type { StreamingCoreReturn } from './useAudioStreamingCore';
import type { CurrentTrackInfo } from './useEnhancedStreamStart';

type WebSocketContextValue = ReturnType<typeof useWebSocketContext>;

export interface UseEnhancedPlayCommandParams {
  wsContext: WebSocketContextValue;
  dispatch: AppDispatch;
  core: StreamingCoreReturn;
  currentTrackInfoRef: MutableRefObject<CurrentTrackInfo | null>;
  /**
   * Reset the fingerprint status/message when a new stream begins, scoped to
   * that stream's track so late messages for the previous track are ignored.
   */
  resetFingerprint: (trackId: number) => void;
}

export type PlaybackWireType = StreamType;

export type StartPlayback = (
  trackId: number,
  preset: EnhancementPreset,
  intensity: number,
  wireType?: PlaybackWireType
) => Promise<void>;

/**
 * Load the track row so `currentTrack` is set ahead of the backend's own
 * `track_changed` confirmation (#2258).
 *
 * Fire-and-forget by design (#5649): it used to be awaited BEFORE the WS play
 * command, so a slow REST path delayed playback indefinitely with no buffering
 * state. It now rides the shared transport (30 s timeout, backend `detail`
 * extraction) and a failure is explicit: it is logged and `currentTrack` is
 * left to the `player_state` / `track_changed` frames, which carry the same
 * track once the stream starts. A superseded invocation aborts this request.
 */
async function loadCurrentTrack(
  trackId: number,
  dispatch: AppDispatch,
  signal: AbortSignal
): Promise<void> {
  try {
    // #5606: the REST body is the snake_case TrackResponse — transformTrack is
    // the API-boundary mapper every other REST consumer uses.
    const track = transformTrack(
      await get<TrackApiResponse>(`/api/library/tracks/${trackId}`, { signal })
    );
    if (signal.aborted) return;
    // #3587: keep queue.currentIndex aligned with player.currentTrack for the
    // duration before backend WS confirmation arrives.
    dispatch(setCurrentTrackAndSyncQueue(track));
    DEBUG && console.log('[usePlayEnhanced] Set current track:', track.title);
  } catch (err) {
    if (signal.aborted || isAbortError(err)) return;
    console.warn(
      `[usePlayEnhanced] Track ${trackId} metadata unavailable; ` +
        'currentTrack will follow the backend track_changed frame:',
      err
    );
  }
}

export function useEnhancedPlayCommand({
  wsContext,
  dispatch,
  core,
  currentTrackInfoRef,
  resetFingerprint,
}: UseEnhancedPlayCommandParams): StartPlayback {
  return useCallback(
    async (
      trackId: number,
      preset: EnhancementPreset,
      intensity: number,
      wireType: PlaybackWireType = 'enhanced'
    ) => {
      try {
        // Stop any existing playback. Choosing a track means play, so release a
        // pause hold left by the previous track (#5459).
        core.pauseHoldRef.current = false;
        core.playbackEngineRef.current?.stopPlayback();
        // Release the prior ~100 MB buffer before dropping the ref (#4147)
        core.pcmBufferRef.current?.dispose();
        core.pcmBufferRef.current = null;
        core.streamingMetadataRef.current = null;
        core.pendingChunksRef.current = [];
        core.lastReceivedChunkIndexRef.current = -1;

        // Reset streaming state
        dispatch(resetStreaming('enhanced'));

        // Reset fingerprint status for the new track (#5380)
        resetFingerprint(trackId);

        // Check WebSocket connection before proceeding
        if (!wsContext.isConnected) {
          throw new Error('WebSocket not connected. Please wait for connection and try again.');
        }

        // AbortController cancels a still-running metadata load when this
        // invocation is superseded or the component unmounts (#2780).
        core.abortRef.current?.abort();
        const metadataController = new AbortController();
        core.abortRef.current = metadataController;

        // Store the track this stream is for, so seekTo can restart it.
        // Deliberately trackId-only (#5604): preset/intensity used to be
        // snapshotted here and re-sent on seek, re-mastering the seek stream
        // with play-time values after a live slider change. Seek now omits
        // them and the backend resolves from the connection's active stream
        // settings, which the live-change reissue path keeps current.
        currentTrackInfoRef.current = { trackId };

        // Set buffering state immediately for instant user feedback
        dispatch(startStreaming({
          streamType: 'enhanced',
          trackId,
          totalChunks: 0, // Will be updated when stream starts
        }));

        // One browser audio session consumes either backend stream. Route the
        // wire command from the stored enhancement flag at the session layer
        // while preserving live preset/intensity for enhanced playback
        // (#4812/#4813).
        if (wireType === 'enhanced') {
          wsContext.send({
            type: 'play_enhanced',
            data: {
              track_id: trackId,
              preset,
              intensity,
            },
          });
        } else {
          wsContext.send({
            type: 'play_normal',
            data: { track_id: trackId },
          });
        }

        // Arm the first-stream watchdog so a hung worker that never emits any
        // stream message surfaces an error instead of leaving the UI stuck in
        // 'buffering' (#4433). Cleared by the core on the first stream message.
        core.armStreamStartWatchdog();

        // Background: playback above has already been dispatched (#5649).
        void loadCurrentTrack(trackId, dispatch, metadataController.signal);

        DEBUG && console.log('[usePlayEnhanced] Playback requested (buffering...):', {
          trackId,
          preset,
          intensity,
          wireType,
        });
      } catch (error) {
        const errorMsg = `Failed to start playback: ${error instanceof Error ? error.message : String(error)}`;
        console.error('[usePlayEnhanced]', errorMsg);
        dispatch(setStreamingError({ streamType: 'enhanced', error: errorMsg }));
      }
    },
    // Depend on the individual core fields actually used, not the whole `core`
    // object — useAudioStreamingCore returns a bare literal, so `core` has a new
    // identity every render and `playEnhanced` never stabilized. That churn
    // cascaded into Player.tsx's handleNext/handlePrevious/handlePlayPause and
    // the auto-advance effect keyed on them (#4608).
    //
    // Every field listed here is stable by construction: the `*Ref` objects are
    // useRef containers and armStreamStartWatchdog is useCallback'd. Memoizing
    // useAudioStreamingCore's return object instead would NOT fix this — that
    // object also carries `currentTime`, which changes ~10x/second during
    // playback, so the memo would invalidate just as often.
    //
    // Matches the established convention in useEnhancedSeek.ts / useEnhancedStreamStart.ts.
    [
      wsContext,
      dispatch,
      currentTrackInfoRef,
      resetFingerprint,
      core.playbackEngineRef,
      core.pcmBufferRef,
      core.streamingMetadataRef,
      core.pendingChunksRef,
      core.lastReceivedChunkIndexRef,
      core.abortRef,
      core.pauseHoldRef,
      core.armStreamStartWatchdog,
    ]
  );
}
