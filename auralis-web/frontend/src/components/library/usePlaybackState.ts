import { useState, useCallback } from 'react';
import { useToast } from '../shared/Toast';
import { Track } from '@/hooks/library/useLibraryWithStats';

export const usePlaybackState = (onTrackPlay?: (track: Track) => void) => {
  const [currentTrackId, setCurrentTrackId] = useState<number | undefined>(undefined);
  const [isPlaying, setIsPlaying] = useState(false);
  const { success } = useToast();

  const handlePlayTrack = useCallback(async (track: Track) => {
    try {
      // Call backend API to set queue and play track
      await fetch('/api/player/queue', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          tracks: [track.id],
          start_index: 0
        })
      });

      // Update local UI state (Redux will sync via WebSocket)
      setCurrentTrackId(track.id);
      setIsPlaying(true);
      success(`Now playing: ${track.title}`);
      onTrackPlay?.(track);
    } catch (err) {
      console.error('Failed to play track:', err);
    }
  }, [success, onTrackPlay]);

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
