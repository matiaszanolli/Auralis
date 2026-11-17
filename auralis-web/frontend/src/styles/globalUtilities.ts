import { css } from '@emotion/react';
import { tokens } from '@/design-system/tokens';

/**
 * Global utility classes: only those a component actually applies. Split out of
 * globalStyles.ts (#5841).
 */
export const utilityStyles = css`
  /* The one scroll-animation class anything uses (TrackGridView). */
  .animate-fade-in-up {
    animation: fadeInUp 0.6s ${tokens.transitions.easeOut} forwards;
  }
`;
