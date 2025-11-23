/**
 * usePlayerFeatures - Initialize all player feature hooks
 *
 * Combines track loading, enhancement sync, and event handlers
 * into a single hook for easier management.
 */

import { useMemo } from 'react';
import { usePlayerTrackLoader } from '@/hooks/usePlayerTrackLoader';
import { usePlayerEnhancementSync } from '@/hooks/usePlayerEnhancementSync';
import { usePlayerEventHandlers } from '@/hooks/usePlayerEventHandlers';

interface Track {
  id?: number;
  title?: string;
  [key: string]: any;
}

interface Queue {
  index: number;
  items: Track[];
}

interface EnhancementSettings {
  enabled: boolean;
  preset?: string;
}

interface Callbacks {
  play: () => void;
  pause: () => void;
  next: () => void;
  previous: () => void;
  setVolume: (volume: number) => void;
  setEnhanced: (enabled: boolean, preset?: string) => void;
  setEnhancementEnabled: (enabled: boolean) => void;
}

interface UsePlayerFeaturesProps {
  player: any; // UnifiedWebMAudioPlayer instance
  currentTrack: Track | null | undefined;
  queue: Track[];
  queueIndex: number;
  enhancementSettings: EnhancementSettings;
  callbacks: Callbacks;
  onError: (message: string) => void;
}

export const usePlayerFeatures = ({
  player,
  currentTrack,
  queue,
  queueIndex,
  enhancementSettings,
  callbacks,
  onError,
}: UsePlayerFeaturesProps) => {
  // Track loading and error handling
  usePlayerTrackLoader({
    player,
    trackId: currentTrack?.id,
    trackTitle: currentTrack?.title,
    onError,
  });

  // Enhancement settings synchronization
  usePlayerEnhancementSync({
    player,
    settings: enhancementSettings,
    onError,
  });

  // Event handlers for all playback controls
  const handlers = usePlayerEventHandlers({
    player,
    playback: { queue, queueIndex },
    callbacks,
    enhancementEnabled: enhancementSettings.enabled,
    enhancementPreset: enhancementSettings.preset,
    onInfo: () => {}, // TODO: connect to toast
    onError,
  });

  return handlers;
};

export default usePlayerFeatures;
