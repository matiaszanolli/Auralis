/**
 * useEnhancedPlaybackShortcuts Hook
 *
 * Provides keyboard shortcuts for enhanced audio playback features:
 * - Shift+E: Toggle enhanced playback mode
 * - Shift+A/S/W/B/P: Quick preset selection (Adaptive/Gentle/Warm/Bright/Punchy)
 * - Shift+↑/↓: Adjust intensity by ±0.1
 *
 * Integrates with Redux and usePlayEnhanced hook for state management.
 *
 * @example
 * ```tsx
 * const shortcuts = useEnhancedPlaybackShortcuts({
 *   trackId: 123,
 *   enabled: true,
 *   onPresetChange: (preset) => console.log(`Switched to ${preset}`),
 *   onIntensityChange: (intensity) => console.log(`Intensity: ${intensity}`),
 * });
 * ```
 */

import { useEffect, useCallback } from 'react';
import { useSelector } from 'react-redux';
import type { PresetName } from '@/store/slices/playerSlice';
import { playerSelectors } from '@/store/selectors';
import type { RootState } from '@/store';

/**
 * Enhanced playback shortcuts config
 */
export interface EnhancedPlaybackShortcutsConfig {
  /** Track ID for playback */
  trackId?: number;

  /** Enable/disable shortcuts */
  enabled?: boolean;

  /** Callback when preset is changed */
  onPresetChange?: (preset: PresetName) => void;

  /** Callback when intensity is changed */
  onIntensityChange?: (intensity: number) => void;

  /** Callback when enhanced mode is toggled */
  onEnhancedToggle?: (enabled: boolean) => void;

  /** Debug logging */
  debug?: boolean;
}

/**
 * Return type for enhanced playback shortcuts
 */
export interface UseEnhancedPlaybackShortcutsReturn {
  /** Whether shortcuts are enabled */
  isEnabled: boolean;

  /** Current selected preset */
  currentPreset: PresetName;

  /** Current intensity */
  currentIntensity: number;

  /** Whether enhanced mode is active */
  isEnhancedMode: boolean;
}

/**
 * Map key combinations to preset names
 */
const PRESET_SHORTCUTS: Record<string, PresetName> = {
  'a': 'adaptive',
  's': 'gentle',
  'w': 'warm',
  'b': 'bright',
  'p': 'punchy',
};

/**
 * useEnhancedPlaybackShortcuts Hook
 *
 * Manages keyboard shortcuts for enhanced playback control including
 * preset selection and intensity adjustment.
 */
export const useEnhancedPlaybackShortcuts = (
  config: EnhancedPlaybackShortcutsConfig = {}
): UseEnhancedPlaybackShortcutsReturn => {
  const {
    trackId,
    enabled = true,
    onPresetChange,
    onIntensityChange,
    onEnhancedToggle,
    debug = false,
  } = config;

  // Get streaming state from Redux (typed selectors fix #2463)
  const streaming = useSelector((state: RootState) => state.player.streaming.enhanced);
  const currentPreset = (useSelector(playerSelectors.selectPreset) ?? 'adaptive') as PresetName;
  const currentIntensity = streaming.intensity || 1.0;
  const isEnhancedMode = streaming.state === 'streaming';

  /**
   * Handle keyboard event
   */
  const handleKeyDown = useCallback(
    (event: KeyboardEvent) => {
      if (!enabled || !trackId) return;

      // Only handle shift key combinations
      if (!event.shiftKey) return;

      const key = event.key.toLowerCase();

      if (debug) {
        console.log(`[useEnhancedPlaybackShortcuts] Key: ${key}, Shift: ${event.shiftKey}`);
      }

      // Shift+E: Toggle enhanced playback mode
      if (key === 'e') {
        event.preventDefault();
        if (debug) console.log('[useEnhancedPlaybackShortcuts] Toggle enhanced mode');
        onEnhancedToggle?.(!isEnhancedMode);
        return;
      }

      // Shift+A/S/W/B/P: Preset selection
      if (PRESET_SHORTCUTS[key]) {
        event.preventDefault();
        const preset = PRESET_SHORTCUTS[key];
        if (debug) console.log(`[useEnhancedPlaybackShortcuts] Switch to preset: ${preset}`);
        onPresetChange?.(preset);
        return;
      }

      // Shift+↑: Increase intensity by 0.1
      if (event.key === 'ArrowUp') {
        event.preventDefault();
        const newIntensity = Math.min(1.0, currentIntensity + 0.1);
        if (debug) console.log(`[useEnhancedPlaybackShortcuts] Increase intensity: ${newIntensity}`);
        onIntensityChange?.(newIntensity);
        return;
      }

      // Shift+↓: Decrease intensity by 0.1
      if (event.key === 'ArrowDown') {
        event.preventDefault();
        const newIntensity = Math.max(0.0, currentIntensity - 0.1);
        if (debug) console.log(`[useEnhancedPlaybackShortcuts] Decrease intensity: ${newIntensity}`);
        onIntensityChange?.(newIntensity);
        return;
      }
    },
    [enabled, trackId, isEnhancedMode, currentIntensity, onPresetChange, onIntensityChange, onEnhancedToggle, debug]
  );

  /**
   * Register keyboard event listener
   */
  useEffect(() => {
    if (!enabled) return;

    window.addEventListener('keydown', handleKeyDown);
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [enabled, handleKeyDown]);

  return {
    isEnabled: enabled,
    currentPreset,
    currentIntensity,
    isEnhancedMode,
  };
};

export default useEnhancedPlaybackShortcuts;
