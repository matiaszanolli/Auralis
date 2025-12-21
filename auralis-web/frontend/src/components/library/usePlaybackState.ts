import { useState, useCallback } from 'react';
import { useToast } from '../shared/Toast';
import { Track } from '@/hooks/library/useLibraryWithStats';
import { usePlayEnhanced } from '@/hooks/enhancement/usePlayEnhanced';

export const usePlaybackState = (onTrackPlay?: (track: Track) => void) => {
  const [currentTrackId, setCurrentTrackId] = useState<number | undefined>(undefined);
  const [isPlaying, setIsPlaying] = useState(false);
  const { success } = useToast();

  // Use WebSocket streaming for playback
  const { playEnhanced } = usePlayEnhanced();

  const handlePlayTrack = useCallback(async (track: Track) => {
    try {
      // 1. Set queue via REST API (still needed for queue management)
      await fetch('/api/player/queue', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          tracks: [track.id],
          start_index: 0
        })
      });

      // 2. Start playback via WebSocket streaming (new system)
      playEnhanced(track.id, 'adaptive', 1.0);

      // Update local UI state (Redux will sync via WebSocket)
      setCurrentTrackId(track.id);
      setIsPlaying(true);
      success(`Now playing: ${track.title}`);
      onTrackPlay?.(track);
    } catch (err) {
      console.error('Failed to play track:', err);
    }
  }, [success, onTrackPlay, playEnhanced]);

  const handlePause = useCallback(() => {
    setIsPlaying(false);
  }, []);

  return {
    currentTrackId,
    isPlaying,
    handlePlayTrack,
    handlePause,
  };
};
