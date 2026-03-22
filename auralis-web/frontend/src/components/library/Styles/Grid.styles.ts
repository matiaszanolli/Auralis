/**
 * Grid Styles - Reusable grid and list component styling
 *
 * Consolidates shared styling patterns for grid/list views, loading states,
 * and pagination indicators used across TrackListView and CozyAlbumGrid.
 */

import { Box, Paper, Typography, styled } from '@mui/material';
import { spin } from './Animation.styles';
import { tokens } from '@/design-system';

/**
 * ListLoadingContainer - Paper container for list view loading state
 * Used when displaying track row skeletons
 */
export const ListLoadingContainer = styled(Paper)({
  background: tokens.colors.bg.level2,
  borderRadius: tokens.spacing.md,
  overflow: 'hidden',
  padding: tokens.spacing.sm,
});

/**
 * GridContainer - Base container for grid views with consistent padding
 * Used by both TrackListView and CozyAlbumGrid
 */
export const GridContainer = styled(Box)({
  padding: tokens.spacing.md,
});

/**
 * InfiniteScrollTrigger - Invisible trigger element for infinite scroll
 * Watched by Intersection Observer to load more items
 */
export const InfiniteScrollTrigger = styled(Box)({
  height: '100px',
  width: '100%',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  marginTop: tokens.spacing.sm,
});

/**
 * LoadingIndicatorBox - Container for loading spinner and text
 * Displays during isLoadingMore state
 */
export const LoadingIndicatorBox = styled(Box)({
  height: '100px',
  width: '100%',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  padding: tokens.spacing.sm,
});


/**
 * LoadingSpinner - Animated spinner for loading state
 * Used during pagination loading
 */
export const LoadingSpinner = styled(Box)({
  width: 20,
  height: 20,
  border: '2px solid',
  borderColor: tokens.colors.accent.primary,
  borderRightColor: 'transparent',
  borderRadius: '50%',
  animation: `${spin} 1s linear infinite`
});

/**
 * LoadingText - Typography for loading indicator text
 * Displayed next to spinner
 */
export const LoadingText = styled(Typography)({
  marginLeft: tokens.spacing.sm,
  color: tokens.colors.text.secondary,
});

/**
 * EndOfListIndicator - Container for end-of-list message
 * Displayed when all items have been loaded
 */
export const EndOfListIndicator = styled(Box)({
  padding: tokens.spacing.md,
  textAlign: 'center',
});

/**
 * EndOfListText - Typography for end-of-list message
 * Shows total count of items loaded
 */
export const EndOfListText = styled(Typography)({
  color: tokens.colors.text.secondary,
});
