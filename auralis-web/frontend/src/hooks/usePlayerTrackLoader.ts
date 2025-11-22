/**
 * usePlayerTrackLoader - Isolated track loading and error handling hook
 *
 * Responsibility: Load tracks when track selection changes and handle loading errors
 *
 * Separated from PlayerBarV2Connected to:
 * - Make track loading logic testable in isolation
 * - Keep error handling separate from other concerns
 * - Make it easy to modify loading behavior without affecting other features
 */

import { useEffect } from 'react';
import type { UseUnifiedWebMAudioPlayerResult } from './useUnifiedWebMAudioPlayer';

interface TrackLoaderOptions {
  player: UseUnifiedWebMAudioPlayerResult;
  trackId: number | undefined;
  trackTitle: string | undefined;
  onError: (message: string) => void;
}

export function usePlayerTrackLoader({
  player,
  trackId,
  trackTitle,
  onError
}: TrackLoaderOptions): void {
  // Load track when currentTrack changes
  useEffect(() => {
    if (trackId) {
      console.log(`[usePlayerTrackLoader] Loading track ${trackId}: ${trackTitle}`);
      player
        .loadTrack(trackId)
        .then(() => {
          console.log(`[usePlayerTrackLoader] Track loaded successfully`);
          return player.play();
        })
        .catch((err) => {
          console.error(`[usePlayerTrackLoader] Failed to load track:`, err);
          onError(`Playback error: ${err.message}`);
        });
    }
  }, [trackId]); // Only depend on track ID

  // Show error toast when player encounters errors
  useEffect(() => {
    if (player.error) {
      console.error(`[usePlayerTrackLoader] Player error:`, player.error);
      onError(`Playback error: ${player.error.message}`);
    }
  }, [player.error, onError]);
}
