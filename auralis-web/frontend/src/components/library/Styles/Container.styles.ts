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

/**
 * CenteredBox - Flexbox container with centered content
 * Used for: modals, loaders, empty states, centered UI elements
 * Features: horizontal and vertical centering via flexbox
 */
export const CenteredBox = styled(Box)(({ theme: _theme }) => ({
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  width: '100%',
  height: '100%',
}));

/**
 * CenteredColumn - Flexbox column container with centered content
 * Used for: vertical layouts, form containers, stacked content
 * Features: vertical stacking with centered alignment
 */
export const CenteredColumn = styled(Box)(({ theme: _theme }) => ({
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  justifyContent: 'center',
  width: '100%',
}));

/**
 * FlexRow - Horizontal flex container with gap
 * Used for: inline elements, horizontal layouts, controls
 * Features: row layout with consistent spacing via gap
 */
export const FlexRow = styled(Box)(({ theme }) => ({
  display: 'flex',
  alignItems: 'center',
  gap: theme.spacing(1),
}));

/**
 * FlexColumn - Vertical flex container with gap
 * Used for: vertical layouts with spacing between items
 * Features: column layout with consistent spacing via gap
 */
export const FlexColumn = styled(Box)(({ theme }) => ({
  display: 'flex',
  flexDirection: 'column',
  gap: theme.spacing(1),
}));

/**
 * PaddedBox - Container with consistent padding
 * Default padding: 16px (md spacing)
 * Can be overridden with sx prop
 */
export const PaddedBox = styled(Box)(({ theme }) => ({
  padding: theme.spacing(2),
}));

/**
 * SectionBox - Padded section with margin separation
 * Used for: form sections, dialog content sections
 * Features: padding and margin-bottom for visual separation
 */
export const SectionBox = styled(Box)(({ theme }) => ({
  padding: theme.spacing(2),
  marginBottom: theme.spacing(2),
}));

/**
 * OverflowContainer - Container with scroll on overflow
 * Used for: scrollable lists, overflow content
 * Features: auto scroll, width/height constraints
 */
export const OverflowContainer = styled(Box)(({ theme: _theme }) => ({
  overflow: 'auto',
  width: '100%',
}));

/**
 * RelativeContainer - Positioned relative container
 * Used for: parent of absolutely positioned children
 * Features: position relative, size management
 */
export const RelativeContainer = styled(Box)(({ theme: _theme }) => ({
  position: 'relative',
  width: '100%',
}));
