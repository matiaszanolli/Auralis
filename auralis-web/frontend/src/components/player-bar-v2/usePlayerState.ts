/**
 * usePlayerState - Prepare player state for PlayerBarV2
 *
 * Combines unified player state with Redux state and enhancement settings
 * into a single memoized object for PlayerBarV2.
 *
 * IMPORTANT: Uses player.isPlaying (unified player state) NOT Redux isPlaying
 * to avoid desync between play/pause button and actual playback
 */

import { useMemo } from 'react';

interface Track {
  id: number;
  title: string;
  artist?: string;
  album?: string;
  duration?: number;
  [key: string]: any;
}

interface PlayerUnified {
  isPlaying: boolean;
  currentTime: number;
  duration: number;
}

interface EnhancementSettings {
  enabled: boolean;
  preset?: string;
  intensity?: number;
}

interface UsePlayerStateProps {
  currentTrack: Track | null | undefined;
  unifiedPlayer: PlayerUnified;
  volume: number;
  enhancementSettings: EnhancementSettings;
  queue: Track[];
  queueIndex: number;
}

export const usePlayerState = ({
  currentTrack,
  unifiedPlayer,
  volume,
  enhancementSettings,
  queue,
  queueIndex,
}: UsePlayerStateProps) => {
  // CRITICAL: Wrap in useMemo to prevent unnecessary re-renders of memoized PlayerBarV2
  const playerState = useMemo(
    () => ({
      currentTrack: currentTrack || null,
      isPlaying: unifiedPlayer.isPlaying, // Use unified player's state
      currentTime: unifiedPlayer.currentTime || 0,
      duration: unifiedPlayer.duration || 0,
      volume: volume || 0.8,
      isEnhanced: enhancementSettings.enabled,
      queue: queue || [],
      queueIndex,
    }),
    [
      currentTrack,
      unifiedPlayer.isPlaying,
      unifiedPlayer.currentTime,
      unifiedPlayer.duration,
      volume,
      enhancementSettings.enabled,
      queue,
      queueIndex,
    ]
  );

  return playerState;
};

export default usePlayerState;
