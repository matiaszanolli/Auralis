/**
 * EmptyState Styles - Reusable empty state component styling
 *
 * Consolidates empty state/no results UI patterns with consistent
 * styling across the library views (grids, lists, tables, searches).
 *
 * Includes:
 * - EmptyStateContainer: Paper-based container for full-page empty states
 * - SearchEmptyState: Centered search results empty state
 * - NoResultsBox: Generic container for any "no items" message
 *
 * All use consistent padding, text alignment, and semi-transparent backgrounds.
 */

import { Box, Paper, styled } from '@mui/material';

/**
 * EmptyStateContainer - Paper-based empty state for list/grid views
 * Used when a collection (albums, artists, etc.) is empty
 * Features: semi-transparent background, rounded corners, centered text
 */
export const EmptyStateContainer = styled(Paper)(({ theme }) => ({
  padding: theme.spacing(4),
  textAlign: 'center',
  background: 'rgba(255,255,255,0.03)',
  borderRadius: theme.spacing(2)
}));

/**
 * SearchEmptyState - Empty state for search results (no items found)
 * Used by GlobalSearch when search yields no results
 * Features: centered layout, padding, text alignment
 */
export const SearchEmptyState = styled(Box)(({ theme }) => ({
  padding: theme.spacing(4),
  textAlign: 'center'
}));

/**
 * NoResultsBox - Generic container for "no items" messages
 * Simple Box-based empty state for any context
 * Features: padding, centered text
 */
export const NoResultsBox = styled(Box)(({ theme }) => ({
  padding: theme.spacing(3),
  textAlign: 'center'
}));
