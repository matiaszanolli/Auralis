import { useCallback } from 'react';
import { useSelector } from 'react-redux';
import { useToast } from '@/components/shared/Toast';
import type { LibraryTrack as Track } from '@/types/domain';
import { useWebSocketContext } from '@/contexts/WebSocketContext';
import { selectIsPlaying, selectCurrentTrack } from '@/store/slices/playerSlice';

/**
 * usePlaybackState - Library playback state management
 *
 * Reads isPlaying and currentTrackId from Redux (single source of truth)
 * and provides action methods that send WebSocket messages.
 *
 * IMPORTANT: This hook sends WebSocket messages directly instead of using
 * usePlayEnhanced, because usePlayEnhanced has cleanup effects that would
 * interfere with streaming when library components unmount/remount.
 *
 * The Player component's usePlayEnhanced instance handles the actual streaming.
 */
export const usePlaybackState = (onTrackPlay?: (track: Track) => void) => {
  // Read from Redux — single source of truth for playback state
  const isPlaying = useSelector(selectIsPlaying);
  const currentTrack = useSelector(selectCurrentTrack);
  const currentTrackId = currentTrack?.id;

  const { success } = useToast();
  const wsContext = useWebSocketContext();

  const handlePlayTrack = useCallback(async (track: Track) => {
    try {
      // 1. Set queue via REST API (still needed for queue management)
      const apiBaseUrl = import.meta.env.VITE_API_URL || '';
      await fetch(`${apiBaseUrl}/api/player/queue`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          tracks: [track.id],
          start_index: 0
        })
      });

      // 2. Send play_enhanced message via WebSocket
      // The Player component's usePlayEnhanced instance will handle the stream
      wsContext.send({
        type: 'play_enhanced',
        data: {
          track_id: track.id,
          preset: 'adaptive',
          intensity: 1.0,
        },
      });

      // Redux state will sync via WebSocket player_state broadcast
      success(`Now playing: ${track.title}`);
      onTrackPlay?.(track);
    } catch (err) {
      console.error('Failed to play track:', err);
    }
  }, [success, onTrackPlay, wsContext]);

  const handlePause = useCallback(() => {
    wsContext.send({
      type: 'pause_playback',
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
