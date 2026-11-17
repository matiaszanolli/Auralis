/**
 * Player Redux Selectors
 * ~~~~~~~~~~~~~~~~~~~~~~
 *
 * Split out of store/selectors/index.ts (#4316).
 *
 * @copyright (C) 2024 Auralis Team
 * @license AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
 */

import type { RootState } from '@/store/index';
import { selectCurrentTrack, selectIsMuted, selectIsPlaying, selectVolume } from '@/store/slices/playerSlice';

/**
 * Basic selectors (non-memoized, for simple properties)
 */
export const playerSelectors = {
  // The slice owns the field selectors; this object only groups the ones with a consumer (#6040).
  selectIsPlaying,
  selectCurrentTrack,
  selectVolume,
  selectIsMuted,
  /** Streaming state for the enhanced stream (idle | buffering | streaming | error | complete) */
  selectEnhancedStreamingState: (state: RootState) => state.player.streaming.enhanced.state,
};
