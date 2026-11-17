import { useCallback } from 'react';
import { useSelector } from 'react-redux';
import type { LibraryTrack as Track } from '@/types/domain';
import { selectCurrentTrack } from '@/store/slices/playerSlice';
import { usePlayTrack } from '@/hooks/player/usePlayTrack';
import { usePlaybackControls } from '@/contexts/PlaybackSessionContext';

/**
 * usePlaybackState - Library playback state management
 *
 * Reads currentTrackId from Redux and `isPlaying` from the local playback session, and provides
 * action methods.
 *
 * `isPlaying` is the session's own `isPlaybackActive && !isPaused` — the same derivation the transport
 * bar uses. Redux `player.isPlaying` is written only by backend events and snapshots, which the
 * session that actually plays the audio never produces, so rows and album buttons that read it
 * showed "paused" for the track the user was hearing (#6015).
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
  const currentTrack = useSelector(selectCurrentTrack);
  const currentTrackId = currentTrack?.id;

  const { playTrack } = usePlayTrack();
  const { handlePlayPause, isPlaybackActive, isPaused } = usePlaybackControls();
  const isPlaying = isPlaybackActive && !isPaused;

  const handlePlayTrack = useCallback(
    (track: Pick<Track, 'id'>) => playTrack(track),
    [playTrack]
  );

  return {
    currentTrackId,
    isPlaying,
    handlePlayTrack,
    handlePlayPause,
  };
};
