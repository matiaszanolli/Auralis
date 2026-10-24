/**
 * Cache Redux Hooks
 * ~~~~~~~~~~~~~~~~~
 *
 * Cache-slice state hook. Split out of useReduxState.ts (#5239), which
 * re-exports everything here.
 *
 * @copyright (C) 2024 Auralis Team
 * @license AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
 */

import { useSelector, shallowEqual } from 'react-redux';
import type { RootState } from '@/store';

/**
 * Access entire cache state
 */
export const useCacheState = () => {
  return useSelector((state: RootState) => state.cache, shallowEqual);
};

// No useCache() umbrella hook (#5354): the isLoading/error/clearError
// surface it would expose never changes in production.
