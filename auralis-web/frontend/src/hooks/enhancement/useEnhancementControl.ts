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
 * await setPreset('warm');
 * await setIntensity(0.8);
 * ```
 *
 * Features:
 * - Control enhancement enabled/disabled state
 * - Change enhancement preset (adaptive, gentle, warm, bright, punchy)
 * - Adjust intensity (0.0-1.0)
 * - Real-time state sync via WebSocket
 * - Optimistic UI updates with error rollback
 * - Proper error handling
 * - Memoized callbacks
 *
 * @module hooks/enhancement/useEnhancementControl
 */

import { useCallback, useState, useEffect, useRef } from 'react';
import { useRestAPI } from '@/hooks/api/useRestAPI';
import { useWebSocketSubscription } from '@/hooks/websocket/useWebSocketSubscription';
import type { ApiError } from '@/types/api';
import type { EnhancementPreset } from '@/types/domain';
import type { EnhancementSettingsChangedMessage } from '@/types/websocket';

/**
 * Current enhancement settings state
 */
export interface EnhancementState {
  /** Whether enhancement is enabled */
  enabled: boolean;

  /** Current preset: 'adaptive', 'gentle', 'warm', 'bright', 'punchy' */
  preset: EnhancementPreset;

  /** Enhancement intensity 0.0-1.0 */
  intensity: number;

  /** Last update timestamp */
  lastUpdated: number;
}

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
 * Initial enhancement state
 */
const INITIAL_STATE: EnhancementState = {
  enabled: false,
  preset: 'adaptive',
  intensity: 1.0,
  lastUpdated: Date.now(),
};

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
  const { get, post } = useRestAPI();

  // State
  const [state, setState] = useState<EnhancementState>(INITIAL_STATE);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);

  /**
   * Subscribe to real-time enhancement setting changes via WebSocket
   */
  useWebSocketSubscription(
    ['enhancement_settings_changed'],
    (message) => {
      const enhancementMsg = message as EnhancementSettingsChangedMessage;

      setState((prevState) => ({
        ...prevState,
        enabled: enhancementMsg.data.enabled ?? prevState.enabled,
        preset: enhancementMsg.data.preset ?? prevState.preset,
        intensity: enhancementMsg.data.intensity ?? prevState.intensity,
        lastUpdated: Date.now(),
      }));
    }
  );

  /**
   * Fetch initial enhancement state on mount
   */
  useEffect(() => {
    const fetchInitialState = async () => {
      try {
        const response = await get<EnhancementState>('/api/player/enhancement/status');

        if (response) {
          setState({
            enabled: response.enabled,
            preset: response.preset,
            intensity: response.intensity,
            lastUpdated: Date.now(),
          });
        }
      } catch (err) {
        // Silently fail - user can still interact with defaults
        console.warn('Failed to fetch initial enhancement state:', err);
      }
    };

    fetchInitialState();
  }, [get]);

  /**
   * Toggle enhancement on/off
   */
  // Ref-based in-flight guard prevents rapid double-click from sending duplicate
  // requests: both clicks would read the same stale state.enabled and call the
  // API twice with the same value (fixes #2404).
  const isTogglingRef = useRef(false);

  const toggleEnabled = useCallback(async (): Promise<void> => {
    if (isTogglingRef.current) return;
    isTogglingRef.current = true;
    setIsLoading(true);
    setError(null);

    const newEnabled = !state.enabled;

    try {
      await post('/api/player/enhancement/toggle', { enabled: newEnabled });

      // Optimistic update - server will broadcast confirmation via WebSocket
      setState((prevState) => ({
        ...prevState,
        enabled: newEnabled,
        lastUpdated: Date.now(),
      }));
    } catch (err) {
      const apiError = err instanceof Error
        ? { message: err.message, code: 'TOGGLE_ERROR', status: 500 }
        : (err as ApiError);

      setError(apiError);
      throw apiError;
    } finally {
      isTogglingRef.current = false;
      setIsLoading(false);
    }
  }, [post, state.enabled]);

  /**
   * Change enhancement preset
   *
   * @param preset New preset: 'adaptive', 'gentle', 'warm', 'bright', 'punchy'
   * @throws Error if preset change fails
   */
  const setPreset = useCallback(async (preset: EnhancementPreset): Promise<void> => {
    setIsLoading(true);
    setError(null);

    // Validate preset
    const validPresets: EnhancementPreset[] = ['adaptive', 'gentle', 'warm', 'bright', 'punchy'];
    if (!validPresets.includes(preset)) {
      const apiError = {
        message: `Invalid preset: ${preset}`,
        code: 'INVALID_PRESET',
        status: 400,
      };
      setError(apiError);
      throw apiError;
    }

    try {
      await post('/api/player/enhancement/preset', { preset });

      // Optimistic update - server will broadcast confirmation via WebSocket
      setState((prevState) => ({
        ...prevState,
        preset,
        lastUpdated: Date.now(),
      }));
    } catch (err) {
      const apiError = err instanceof Error
        ? { message: err.message, code: 'PRESET_ERROR', status: 500 }
        : (err as ApiError);

      setError(apiError);
      throw apiError;
    } finally {
      setIsLoading(false);
    }
  }, [post]);

  /**
   * Adjust enhancement intensity
   *
   * @param intensity Intensity level 0.0-1.0
   * @throws Error if intensity change fails
   */
  const setIntensity = useCallback(async (intensity: number): Promise<void> => {
    setIsLoading(true);
    setError(null);

    // Clamp intensity to valid range
    const validIntensity = Math.max(0.0, Math.min(1.0, intensity));

    try {
      await post('/api/player/enhancement/intensity', { intensity: validIntensity });

      // Optimistic update - server will broadcast confirmation via WebSocket
      setState((prevState) => ({
        ...prevState,
        intensity: validIntensity,
        lastUpdated: Date.now(),
      }));
    } catch (err) {
      const apiError = err instanceof Error
        ? { message: err.message, code: 'INTENSITY_ERROR', status: 500 }
        : (err as ApiError);

      setError(apiError);
      throw apiError;
    } finally {
      setIsLoading(false);
    }
  }, [post]);

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
    setPreset,
    setIntensity,
    isLoading,
    error,
    clearError,
  };
}

/**
 * Convenience hook for preset control only
 *
 * @example
 * ```typescript
 * const { preset, setPreset, isLoading } = usePresetControl();
 * ```
 */
export function usePresetControl() {
  const { preset, setPreset, isLoading, error, clearError } = useEnhancementControl();

  return {
    preset,
    setPreset,
    isLoading,
    error,
    clearError,
  };
}

/**
 * Convenience hook for intensity control only
 *
 * @example
 * ```typescript
 * const { intensity, setIntensity } = useIntensityControl();
 * ```
 */
export function useIntensityControl() {
  const { intensity, setIntensity, isLoading, error, clearError } = useEnhancementControl();

  return {
    intensity,
    setIntensity,
    isLoading,
    error,
    clearError,
  };
}

/**
 * Convenience hook for enhancement enabled toggle only
 *
 * @example
 * ```typescript
 * const { enabled, toggleEnabled } = useEnhancementToggle();
 * ```
 */
export function useEnhancementToggle() {
  const { enabled, toggleEnabled, isLoading, error, clearError } = useEnhancementControl();

  return {
    enabled,
    toggleEnabled,
    isLoading,
    error,
    clearError,
  };
}
