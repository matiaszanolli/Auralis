/**
 * useEnhancementControl Hook
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Provides control over audio enhancement settings (preset, intensity, enabled state).
 * Listens to real-time updates via WebSocket and manages state synchronization.
 *
 * Usage:
 * ```typescript
 * const {
 *   enabled,
 *   preset,
 *   intensity,
 *   toggleEnabled,
 *   setPreset,
 *   setIntensity,
 *   isLoading,
 *   error
 * } = useEnhancementControl();
 *
 * await toggleEnabled();
 * await setPreset('adaptive');
 * await setIntensity(0.8);
 * ```
 *
 * Features:
 * - Control enhancement enabled/disabled state
 * - Change enhancement preset (only 'adaptive' is valid)
 * - Adjust intensity (0.0-1.0)
 * - Real-time state sync via WebSocket
 * - Optimistic UI updates with error rollback
 * - Proper error handling
 * - Memoized callbacks
 *
 * @module hooks/enhancement/useEnhancementControl
 */

import { useCallback, useState, useRef } from 'react';
import { useEnhancementCommands } from './useEnhancementCommands';
import { useEnhancementStatusSync } from './useEnhancementStatusSync';
import { INITIAL_STATE, type EnhancementState } from './enhancementState';
import { useWebSocketContext } from '@/contexts/WebSocketContext';
import type { ApiError } from '@/types/api';
import type { EnhancementPreset } from '@/types/domain';

export type { EnhancementState } from './enhancementState';

/**
 * Return type for useEnhancementControl hook
 */
export interface EnhancementControlActions {
  /** Current enhancement state */
  state: EnhancementState;

  /** Whether enhancement is currently enabled */
  enabled: boolean;

  /** Current preset */
  preset: EnhancementPreset;

  /** Current intensity */
  intensity: number;

  /** Toggle enhancement on/off */
  toggleEnabled: () => Promise<void>;

  /** Set enhancement enabled/disabled explicitly */
  setEnabled: (enabled: boolean) => Promise<void>;

  /** Change enhancement preset */
  setPreset: (preset: EnhancementPreset) => Promise<void>;

  /** Adjust enhancement intensity */
  setIntensity: (intensity: number) => Promise<void>;

  /** True while a command is executing */
  isLoading: boolean;

  /** Last error from a command */
  error: ApiError | null;

  /** Clear error state */
  clearError: () => void;
}



/**
 * Hook for controlling audio enhancement settings
 *
 * @returns Enhancement control actions and current state
 *
 * @example
 * ```typescript
 * const { enabled, preset, intensity, toggleEnabled, setPreset } = useEnhancementControl();
 *
 * const handlePresetChange = async (newPreset) => {
 *   try {
 *     await setPreset(newPreset);
 *   } catch (err) {
 *     console.error('Failed to change preset:', error?.message);
 *   }
 * };
 * ```
 */
export function useEnhancementControl(): EnhancementControlActions {
  // #3759 + #3763: WebSocket context exposes `reissueActiveStreamAs`,
  // which restarts the active stream from the current resume position.
  // We use it from the toggle / preset / intensity setters so live
  // changes actually affect the audio path (the backend binds these at
  // ChunkedAudioProcessor construction and the stream loop never
  // re-reads them).
  const wsContext = useWebSocketContext();
  const reissueRef = useRef(wsContext.reissueActiveStreamAs);
  reissueRef.current = wsContext.reissueActiveStreamAs;

  // State
  const [state, setState] = useState<EnhancementState>(INITIAL_STATE);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);

  // Keep refs in sync with the latest enabled / preset / intensity values so
  // the toggle and setter callbacks never read a stale closure (fixes #2990 —
  // WS race overwrites correct state; #3759 + #3763 — re-issued stream command
  // needs latest values). Direct assignment in the render body is sufficient
  // and avoids three single-field useEffect synchronizers (#3969).
  // Declared before useEnhancementStatusSync so the broadcast re-issue
  // callback below can read the live values (#5864).
  const enabledRef = useRef(state.enabled);
  enabledRef.current = state.enabled;
  const presetRef = useRef(state.preset);
  presetRef.current = state.preset;
  const intensityRef = useRef(state.intensity);
  intensityRef.current = state.intensity;

  // #5864: Settings-originated enabled changes reach the client only as the
  // enhancement_settings_changed broadcast; the running stream loop stops
  // itself when it re-reads enabled=false, so this re-issues as the
  // appropriate type — same shape as toggleEnabled's own re-issue.
  const handleExternalEnabledChange = useCallback((enabled: boolean) => {
    if (enabled === enabledRef.current) return; // already in the target mode
    if (enabled) {
      reissueRef.current('play_enhanced', {
        preset: presetRef.current,
        intensity: intensityRef.current,
      });
    } else {
      reissueRef.current('play_normal');
    }
  }, [reissueRef, enabledRef, presetRef, intensityRef]);

  useEnhancementStatusSync(setState, handleExternalEnabledChange);

  const { toggleEnabled, setEnabled, setPreset, setIntensity } = useEnhancementCommands({
    setState, setIsLoading, setError, enabledRef, presetRef, intensityRef, reissueRef,
  });

  /**
   * Clear error state
   */
  const clearError = useCallback(() => {
    setError(null);
  }, []);

  return {
    state,
    enabled: state.enabled,
    preset: state.preset,
    intensity: state.intensity,
    toggleEnabled,
    setEnabled,
    setPreset,
    setIntensity,
    isLoading,
    error,
    clearError,
  };
}
