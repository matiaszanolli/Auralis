/**
 * usePlayerEnhancementSync - Isolated enhancement settings synchronization hook
 *
 * Responsibility: Sync enhancement settings from context to player service
 *
 * Separated from PlayerBarV2Connected to:
 * - Make enhancement syncing testable in isolation
 * - Keep audio processing settings separate from playback controls
 * - Make it easy to add/modify enhancement features without touching playback logic
 */

import { useEffect } from 'react';
import type { UseUnifiedWebMAudioPlayerResult } from './useUnifiedWebMAudioPlayer';
import type { EnhancementSettings } from '@/contexts/EnhancementContext';

interface EnhancementSyncOptions {
  player: UseUnifiedWebMAudioPlayerResult;
  settings: EnhancementSettings;
  onError?: (message: string) => void;
}

export function usePlayerEnhancementSync({
  player,
  settings,
  onError
}: EnhancementSyncOptions): void {
  // Sync enhancement settings with player when they change
  useEffect(() => {
    if (player.player) {
      console.log(
        `[usePlayerEnhancementSync] Settings changed: enabled=${settings.enabled}, preset=${settings.preset}, intensity=${settings.intensity}`
      );
      player.setEnhanced(settings.enabled, settings.preset).catch((err) => {
        console.error(`[usePlayerEnhancementSync] Failed to sync enhancement settings:`, err);
        onError?.(`Enhancement sync error: ${err.message}`);
      });
    }
    // Depend on all enhancement settings
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [settings.enabled, settings.preset, settings.intensity]);
}
