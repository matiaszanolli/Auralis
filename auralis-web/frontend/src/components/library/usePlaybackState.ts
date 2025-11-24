import { useState, useCallback } from 'react';
import { usePlayerAPI } from '../../hooks/usePlayerAPI';
import { useToast } from '../shared/Toast';
import { Track } from '../../hooks/useLibraryWithStats';

export const usePlaybackState = (onTrackPlay?: (track: Track) => void) => {
  const [currentTrackId, setCurrentTrackId] = useState<number | undefined>(undefined);
  const [isPlaying, setIsPlaying] = useState(false);
  const { playTrack } = usePlayerAPI();
  const { success } = useToast();

  const handlePlayTrack = useCallback(async (track: Track) => {
    await playTrack(track);
    setCurrentTrackId(track.id);
    setIsPlaying(true);
    success(`Now playing: ${track.title}`);
    onTrackPlay?.(track);
  }, [playTrack, success, onTrackPlay]);

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
