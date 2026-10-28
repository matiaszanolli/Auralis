/**
 * Border Radius Styles - the two radii the library style modules import.
 *
 * `radiusMedium` is an alias over `tokens.borderRadius.md`, so skeleton loaders
 * stay in sync with the design system (#3599). Anything else should read
 * `tokens.borderRadius.*` directly rather than add another spelling here (#6289).
 */

import { tokens } from '@/design-system';

/** Medium border radius — currently tokens.borderRadius.md (12px). */
export const radiusMedium = tokens.borderRadius.md;

/** Circle radius (50%) — used for avatars / circular buttons. */
export const radiusCircle = '50%';
