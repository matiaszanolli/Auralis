/**
 * Connection Redux Hook
 * ~~~~~~~~~~~~~~~~~~~~~~
 *
 * Connection-slice state hook.
 *
 * @copyright (C) 2024 Auralis Team
 * @license AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
 */

import { useSelector, shallowEqual } from 'react-redux';
import type { RootState } from '@/store';

/**
 * Access entire connection state.
 *
 * The only Redux hook left from the shared wrappers (#6046): the rest had no production caller
 * and were deleted. This one is read by ConnectionStatusIndicator, an unmounted component
 * tracked in #5628.
 */
export const useConnectionState = () => {
  return useSelector((state: RootState) => state.connection, shallowEqual);
};
