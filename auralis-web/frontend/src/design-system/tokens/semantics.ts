/**
 * Auralis Design System Tokens — see ./README or tokens barrel.
 * Split from the former monolithic tokens.ts (#4079). Categories are otherwise
 * self-contained, but `components.*` intentionally composes its glass surface
 * backgrounds from `colors.bg.*` via `withOpacity` so component tokens track
 * palette updates instead of drifting (#4203). Keep all other categories free
 * of cross-category references.
 */
import { colors } from './colors';
import { withOpacity } from './with-opacity';


  /**
   * Component-Specific Tokens
   * Predefined sizes and styles for major UI components
   */
  /**
   * Component-Specific Tokens (Design Language §4)
   * Surfaces, not cards. Hierarchy by space and subtle glass borders.
   * Sidebar is muscle memory UI (low contrast, no visual drama).
   */
export const components = {
    playerBar: {
      height: '96px',
      background: withOpacity(colors.bg.level0, 0.85), // Deep blue-black (translucent)
    },

    sidebar: {
      width: '256px',
    },

    rightPanel: {
      width: '360px',
    },

    albumCard: {
      hoverScale: 1.04,            // Increased from 1.05 for subtlety
    },

    searchBar: {
      height: '48px',
    },
} as const;
