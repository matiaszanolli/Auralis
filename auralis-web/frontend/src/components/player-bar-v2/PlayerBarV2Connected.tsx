/**
 * PlayerBarV2Connected - Connected version of PlayerBarV2
 *
 * Connects PlayerBarV2 to the application state using hooks:
 * - usePlayerAPI for playback control
 * - useUnifiedWebMAudioPlayer for current time/duration
 * - useEnhancement for enhancement state
 *
 * This makes PlayerBarV2 a drop-in replacement for BottomPlayerBarUnified
 */

import React, { useCallback, useEffect } from 'react';
import { PlayerBarV2 } from './PlayerBarV2';
import { usePlayerAPI } from '@/hooks/usePlayerAPI';
import { useUnifiedWebMAudioPlayer } from '@/hooks/useUnifiedWebMAudioPlayer';
import { useEnhancement } from '@/contexts/EnhancementContext';

const PlayerBarV2Connected: React.FC = () => {
  // Get player state from hooks
  const {
    currentTrack,
    isPlaying,
    volume,
    play,
    pause,
    next,
    previous,
    setVolume,
    togglePlayPause
  } = usePlayerAPI();

  const {
    settings: enhancementSettings,
    setEnabled: setEnhancementEnabled
  } = useEnhancement();

  // Initialize unified player with enhancement config
  const player = useUnifiedWebMAudioPlayer({
    apiBaseUrl: 'http://localhost:8765',
    enhanced: enhancementSettings.enabled,
    preset: enhancementSettings.preset,
    intensity: enhancementSettings.intensity,
    debug: true,
    autoPlay: true
  });

  // Load track when currentTrack changes
  useEffect(() => {
    if (currentTrack && currentTrack.id) {
      console.log(`[PlayerBarV2] Loading track ${currentTrack.id}: ${currentTrack.title}`);
      player.loadTrack(currentTrack.id)
        .then(() => {
          console.log(`[PlayerBarV2] Track loaded successfully`);
        })
        .catch((err) => {
          console.error(`[PlayerBarV2] Failed to load track:`, err);
        });
    }
  }, [currentTrack, player]);

  // Callbacks - use player instance methods
  const handlePlay = useCallback(() => {
    player.play();
  }, [player]);

  const handlePause = useCallback(() => {
    player.pause();
  }, [player]);

  const handleSeek = useCallback((time: number) => {
    player.seek(time);
  }, [player]);

  const handleVolumeChange = useCallback((newVolume: number) => {
    player.setVolume(newVolume);
  }, [player]);

  const handleEnhancementToggle = useCallback(() => {
    setEnhancementEnabled(!enhancementSettings.enabled);
  }, [enhancementSettings.enabled, setEnhancementEnabled]);

  const handlePrevious = useCallback(() => {
    previous();
  }, [previous]);

  const handleNext = useCallback(() => {
    next();
  }, [next]);

  // Prepare player state for PlayerBarV2
  const playerState = {
    currentTrack: currentTrack || null,
    isPlaying,
    currentTime: player.currentTime || 0,
    duration: player.duration || 0,
    volume: volume || 0.8,
    isEnhanced: enhancementSettings.enabled
  };

  return (
    <PlayerBarV2
      player={playerState}
      onPlay={handlePlay}
      onPause={handlePause}
      onSeek={handleSeek}
      onVolumeChange={handleVolumeChange}
      onEnhancementToggle={handleEnhancementToggle}
      onPrevious={handlePrevious}
      onNext={handleNext}
    />
  );
};

export default PlayerBarV2Connected;
