import { useCallback } from 'react';
import { useSelector } from 'react-redux';
import type { LibraryTrack as Track } from '@/types/domain';
import { useWebSocketContext } from '@/contexts/WebSocketContext';
import { selectIsPlaying, selectCurrentTrack } from '@/store/slices/playerSlice';
import { usePlayTrack } from '@/hooks/player/usePlayTrack';

/**
 * usePlaybackState - Library playback state management
 *
 * Reads isPlaying and currentTrackId from Redux (single source of truth)
 * and provides action methods.
 *
 * The play flow lives in `usePlayTrack` (#3940) — the canonical "play this
 * track" hook — so it is shared with the detail views instead of being drilled
 * down as an `onTrackPlay` callback. handlePlayTrack is a thin alias over it.
 */
export const usePlaybackState = () => {
  // Read from Redux — single source of truth for playback state
  const isPlaying = useSelector(selectIsPlaying);
  const currentTrack = useSelector(selectCurrentTrack);
  const currentTrackId = currentTrack?.id;

  const { playTrack } = usePlayTrack();
  const wsContext = useWebSocketContext();

  const handlePlayTrack = useCallback(
    (track: Track) => playTrack(track),
    [playTrack]
  );

  const handlePause = useCallback(() => {
    wsContext.send({
      type: 'pause',
    });
    // Redux state will sync via WebSocket player_state broadcast
  }, [wsContext]);

  return {
    currentTrackId,
    isPlaying,
    handlePlayTrack,
    handlePause,
  };
};
