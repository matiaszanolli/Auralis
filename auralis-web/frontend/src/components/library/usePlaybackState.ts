import { useCallback } from 'react';
import { useSelector } from 'react-redux';
import type { LibraryTrack as Track } from '@/types/domain';
import { selectIsPlaying, selectCurrentTrack } from '@/store/slices/playerSlice';
import { usePlayTrack } from '@/hooks/player/usePlayTrack';
import { usePlaybackControls } from '@/contexts/PlaybackSessionContext';

/**
 * usePlaybackState - Library playback state management
 *
 * Reads isPlaying and currentTrackId from Redux (single source of truth)
 * and provides action methods.
 *
 * The play flow lives in `usePlayTrack` (#3940) — the canonical "play this
 * track" hook — so it is shared with the detail views instead of being drilled
 * down as an `onTrackPlay` callback. handlePlayTrack is a thin alias over it.
 *
 * Pausing goes through `usePlaybackControls().handlePlayPause` — the same
 * toggle the transport bar uses — instead of a raw WS `pause` frame. The
 * frame only cleared the backend stream's pause event, and nothing ever sent
 * a matching `resume`, so a library-row pause followed by a transport-bar
 * resume played only the buffered tail and then stalled mid-track (#5514).
 * handlePlayPause toggles the shared session's local engine; the backend
 * stream self-paces through buffer_full flow control.
 */
export const usePlaybackState = () => {
  // Read from Redux — single source of truth for playback state
  const isPlaying = useSelector(selectIsPlaying);
  const currentTrack = useSelector(selectCurrentTrack);
  const currentTrackId = currentTrack?.id;

  const { playTrack } = usePlayTrack();
  const { handlePlayPause } = usePlaybackControls();

  const handlePlayTrack = useCallback(
    (track: Track) => playTrack(track),
    [playTrack]
  );

  return {
    currentTrackId,
    isPlaying,
    handlePlayTrack,
    handlePlayPause,
  };
};
