import { Box, styled } from '@mui/material';
import { tokens } from '@/design-system/tokens';

/**
 * ArtistListContainer - Main container with padding and width
 */
export const ArtistListContainer = styled(Box)({
  padding: tokens.spacing.lg,
  width: '100%',
});

/**
 * LoadMoreTrigger - Invisible sentinel element for infinite scroll
 */
export const LoadMoreTrigger = styled(Box)({
  height: '1px',
  width: '100%',
});

/**
 * EndOfListIndicator - Centered message indicating end of list
 */
export const EndOfListIndicator = styled(Box)({
  padding: tokens.spacing.lg,
  textAlign: 'center',
});
