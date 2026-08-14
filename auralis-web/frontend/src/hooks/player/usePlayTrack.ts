import { useCallback, useEffect, useRef } from 'react';
import { useToast } from '@/components/shared/Toast';
import { usePlaybackControls } from '@/contexts/PlaybackSessionContext';
import { getApiUrl } from '@/config/api';
import type { Track } from '@/types/domain';
import { isAbortError } from '@/utils/errorGuards';
import { httpErrorFromResponse } from '@/utils/httpError';

/**
 * Minimal track shape usePlayTrack needs. `Track` / `LibraryTrack` /
 * `DetailTrack` all satisfy it, so every call site type-checks without
 * conversion.
 */
export type PlayableTrack = Pick<Track, 'id'>;

/**
 * usePlayTrack — the single source of truth for "play this track now".
 *
 * Sets the player queue over REST, then delegates playback to the single shared
 * browser session. That session chooses normal/enhanced from live settings and
 * owns stream confirmation/error state (#4812/#4813/#4829).
 */
export const usePlayTrack = () => {
  const { startTrack } = usePlaybackControls();
  const { error: errorToast } = useToast();

  // #4161: abort the queue POST on unmount so a stray playback start doesn't
  // fire after the user navigates away mid-click.
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
      // #4426: abort the previous invocation before replacing the ref. Without
      // this, two rapid clicks both ran to completion and whichever queue POST
      // *resolved* last started its track last — reverting playback to the
      // older selection. Same ordering as the lower-level play commands.
      abortRef.current?.abort();
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
        // #5121: surface the backend's HTTPException `detail` rather than a
        // bare status line — set_queue raises actionable text ("Track 123 not
        // found") that the hardcoded message discarded. Same fix #4831 applied
        // to useRestAPI.ts.
        if (!queueResponse.ok) {
          throw await httpErrorFromResponse(queueResponse);
        }

        // Skip the stream if the component unmounted while the POST was in flight.
        if (controller.signal.aborted || !isMountedRef.current) return;

        // 2. Start through PlaybackSession so every entry point shares one PCM
        // engine and the current enhancement settings. Do not announce success
        // before the backend confirms the stream (#4829).
        await startTrack(track.id);
      } catch (err) {
        // Aborted by unmount — not user-facing.
        if (isAbortError(err)) return;
        console.error('Failed to play track:', err);
        errorToast(err instanceof Error ? err.message : 'Failed to play track');
      }
    },
    [startTrack, errorToast]
  );

  return { playTrack };
};
