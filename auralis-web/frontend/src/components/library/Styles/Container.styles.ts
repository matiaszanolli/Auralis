/**
 * Container Styles - Reusable layout and container components
 *
 * Provides common container patterns used throughout the application for
 * flex layouts, centering, padding, and responsive behavior.
 *
 * Common Patterns:
 * - CenteredBox: Flex centered container (horizontal and vertical)
 * - CenteredColumn: Flex column centered container
 * - FlexRow: Horizontal flex container with gap
 * - PaddedBox: Padded container with configurable spacing
 * - SectionBox: Padded section with margin
 */

import { Box, styled } from '@mui/material';
import { tokens } from '@/design-system';

/**
 * CenteredBox - Flexbox container with centered content
 * Used for: modals, loaders, empty states, centered UI elements
 * Features: horizontal and vertical centering via flexbox
 */
export const CenteredBox = styled(Box)({
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  width: '100%',
  height: '100%',
});

/**
 * CenteredColumn - Flexbox column container with centered content
 * Used for: vertical layouts, form containers, stacked content
 * Features: vertical stacking with centered alignment
 */
export const CenteredColumn = styled(Box)({
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  justifyContent: 'center',
  width: '100%',
});

/**
 * FlexRow - Horizontal flex container with gap
 * Used for: inline elements, horizontal layouts, controls
 * Features: row layout with consistent spacing via gap
 */
export const FlexRow = styled(Box)({
  display: 'flex',
  alignItems: 'center',
  gap: tokens.spacing.xs,
});

/**
 * FlexColumn - Vertical flex container with gap
 * Used for: vertical layouts with spacing between items
 * Features: column layout with consistent spacing via gap
 */
export const FlexColumn = styled(Box)({
  display: 'flex',
  flexDirection: 'column',
  gap: tokens.spacing.xs,
});

/**
 * PaddedBox - Container with consistent padding
 * Default padding: 16px (md spacing)
 * Can be overridden with sx prop
 */
export const PaddedBox = styled(Box)({
  padding: tokens.spacing.sm,
});

/**
 * SectionBox - Padded section with margin separation
 * Used for: form sections, dialog content sections
 * Features: padding and margin-bottom for visual separation
 */
export const SectionBox = styled(Box)({
  padding: tokens.spacing.sm,
  marginBottom: tokens.spacing.sm,
});

/**
 * OverflowContainer - Container with scroll on overflow
 * Used for: scrollable lists, overflow content
 * Features: auto scroll, width/height constraints
 */
export const OverflowContainer = styled(Box)({
  overflow: 'auto',
  width: '100%',
});

/**
 * RelativeContainer - Positioned relative container
 * Used for: parent of absolutely positioned children
 * Features: position relative, size management
 */
export const RelativeContainer = styled(Box)({
  position: 'relative',
  width: '100%',
});
