import { useState, useCallback } from 'react';
import { useToast } from '../shared/Toast';
import { Track } from '@/hooks/library/useLibraryWithStats';
import { useWebSocketContext } from '@/contexts/WebSocketContext';

/**
 * usePlaybackState - Library playback state management
 *
 * IMPORTANT: This hook sends WebSocket messages directly instead of using
 * usePlayEnhanced, because usePlayEnhanced has cleanup effects that would
 * interfere with streaming when library components unmount/remount.
 *
 * The Player component's usePlayEnhanced instance handles the actual streaming.
 */
export const usePlaybackState = (onTrackPlay?: (track: Track) => void) => {
  const [currentTrackId, setCurrentTrackId] = useState<number | undefined>(undefined);
  const [isPlaying, setIsPlaying] = useState(false);
  const { success } = useToast();

  // Use WebSocket context directly (shared singleton connection)
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

      console.log('[usePlaybackState] Sent play_enhanced message for track:', track.id);

      // Update local UI state (Redux will sync via WebSocket)
      setCurrentTrackId(track.id);
      setIsPlaying(true);
      success(`Now playing: ${track.title}`);
      onTrackPlay?.(track);
    } catch (err) {
      console.error('Failed to play track:', err);
    }
  }, [success, onTrackPlay, wsContext]);

  const handlePause = useCallback(() => {
    // Send pause message via WebSocket
    wsContext.send({
      type: 'pause_playback',
    });
    setIsPlaying(false);
  }, [wsContext]);

  return {
    currentTrackId,
    isPlaying,
    handlePlayTrack,
    handlePause,
  };
};
