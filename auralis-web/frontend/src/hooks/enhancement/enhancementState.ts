/**
 * Enhancement state shape and its initial value.
 *
 * Split out of useEnhancementControl.ts (#5840) so the status-sync hook and
 * the control hook share them without importing each other.
 *
 * @module hooks/enhancement/enhancementState
 */

import type { EnhancementPreset } from '@/types/domain';

/**
 * Current enhancement settings state
 */
export interface EnhancementState {
  /** Whether enhancement is enabled */
  enabled: boolean;

  /** Current preset (only 'adaptive' is valid) */
  preset: EnhancementPreset;

  /** Enhancement intensity 0.0-1.0 */
  intensity: number;

  /** Last update timestamp */
  lastUpdated: number;
}

/**
 * Initial enhancement state
 */
export const INITIAL_STATE: EnhancementState = {
  enabled: false,
  preset: 'adaptive',
  intensity: 1.0,
  lastUpdated: Date.now(),
};
