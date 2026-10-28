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
import { useEnhancementStatusSync, type EnhancementSettingsChange } from './useEnhancementStatusSync';
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

  // Settings-originated changes reach the client only as the
  // enhancement_settings_changed broadcast, so this re-issues the active
  // stream the way the local commands do: as the new type when `enabled`
  // flips (the running loop stops itself on enabled=false, #5864), and as
  // play_enhanced with the new values when preset/intensity change while
  // enhanced — they are bound when the stream starts, and seek resolves them
  // from the snapshot that play_enhanced records (#5874). Off, they only
  // matter at the next play_enhanced, which sends the then-current values.
  const handleExternalChange = useCallback((change: EnhancementSettingsChange) => {
    const enabled = change.enabled ?? enabledRef.current;
    const preset = change.preset ?? presetRef.current;
    const intensity = change.intensity ?? intensityRef.current;
    if (enabled !== enabledRef.current) {
      if (enabled) reissueRef.current('play_enhanced', { preset, intensity });
      else reissueRef.current('play_normal');
    } else if (enabled && (preset !== presetRef.current || intensity !== intensityRef.current)) {
      reissueRef.current('play_enhanced', { preset, intensity });
    }
  }, [reissueRef, enabledRef, presetRef, intensityRef]);

  useEnhancementStatusSync(setState, handleExternalChange);

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
