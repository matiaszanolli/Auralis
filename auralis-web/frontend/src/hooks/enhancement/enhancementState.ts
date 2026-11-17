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
  // The backend's runtime and stored default is enabled (auto_enhance, main.py's enhancement_settings),
  // so until the first status GET answers - or if it never does - the first play starts the enhanced
  // stream the server would have started, not a plain one (#5655).
  enabled: true,
  preset: 'adaptive',
  intensity: 1.0,
  // 0 = never written. A real timestamp here would be "module load time", which a status GET issued
  // later could not be ordered against by a clock that stepped back (#5655).
  lastUpdated: 0,
};
