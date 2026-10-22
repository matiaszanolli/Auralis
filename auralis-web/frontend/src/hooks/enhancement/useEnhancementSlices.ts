/**
 * Narrow views of useEnhancementControl for components that need one concern.
 *
 * Split out of useEnhancementControl.ts (#5840).
 *
 * @module hooks/enhancement/useEnhancementSlices
 */

import { useEnhancementControl } from './useEnhancementControl';

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
