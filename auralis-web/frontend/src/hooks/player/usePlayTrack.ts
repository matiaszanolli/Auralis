import { useCallback, useEffect, useRef } from 'react';
import { useToast } from '@/components/shared/Toast';
import { useWebSocketContext } from '@/contexts/WebSocketContext';
import { getApiUrl } from '@/config/api';
import type { Track } from '@/types/domain';

/**
 * Minimal track shape usePlayTrack needs: `id` for the queue + stream, `title`
 * for the toast. `Track` / `LibraryTrack` / `DetailTrack` all satisfy it, so
 * every call site type-checks without conversion.
 */
export type PlayableTrack = Pick<Track, 'id' | 'title'>;

/**
 * usePlayTrack — the single source of truth for "play this track now".
 *
 * Sets the player queue to the track (REST) and starts enhanced playback via a
 * `play_enhanced` WebSocket message, then toasts. Call it directly at the leaf
 * (a track row, "Play All", etc.) instead of drilling an `onTrackPlay` callback
 * down through the component tree (#3940).
 *
 * The WS message is sent directly rather than through `usePlayEnhanced` for the
 * reason documented in the former `usePlaybackState`: the Player component owns
 * the single streaming instance, and `usePlayEnhanced`'s cleanup effects would
 * interfere with the stream when library components mount/unmount.
 */
export const usePlayTrack = () => {
  const wsContext = useWebSocketContext();
  const { success, error: errorToast } = useToast();

  // #4161: abort the queue POST on unmount so a stray play_enhanced (and a
  // success toast in the wrong view) doesn't fire after the user navigates away
  // mid-click.
  const abortRef = useRef<AbortController | null>(null);
  const isMountedRef = useRef(true);
  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
      abortRef.current?.abort();
    };
  }, []);

  const playTrack = useCallback(
    async (track: PlayableTrack): Promise<void> => {
      const controller = new AbortController();
      abortRef.current = controller;
      try {
        // 1. Set queue via REST (#3641: getApiUrl centralizes URL construction).
        const queueResponse = await fetch(getApiUrl('/api/player/queue'), {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ tracks: [track.id], start_index: 0 }),
          signal: controller.signal,
        });

        // #3953: only stream if the queue POST succeeded.
        if (!queueResponse.ok) {
          throw new Error(
            `Failed to set queue: ${queueResponse.status} ${queueResponse.statusText}`
          );
        }

        // Skip the stream + toast if the component unmounted while the POST was
        // in flight.
        if (controller.signal.aborted || !isMountedRef.current) return;

        // 2. Start enhanced playback. The Player's usePlayEnhanced instance
        //    handles the actual stream; Redux state syncs via the player_state
        //    WebSocket broadcast.
        wsContext.send({
          type: 'play_enhanced',
          data: {
            track_id: track.id,
            preset: 'adaptive',
            intensity: 1.0,
          },
        });

        success(`Now playing: ${track.title}`);
      } catch (err) {
        // Aborted by unmount — not user-facing.
        if ((err as Error).name === 'AbortError') return;
        console.error('Failed to play track:', err);
        errorToast(err instanceof Error ? err.message : 'Failed to play track');
      }
    },
    [wsContext, success, errorToast]
  );

  return { playTrack };
};
