/**
 * Search Styles - Reusable search component styling
 *
 * Consolidates search field, results container, and result item styling
 * used in GlobalSearch component.
 *
 * Avatar components (ArtistSearchAvatar, DefaultSearchAvatar) are imported from Avatar.styles.ts
 * Shadow effects are imported from Shadow.styles.ts
 */

import { containerShadows } from './Shadow.styles';
import { auroraOpacity } from './Color.styles';
import { tokens } from '@/design-system';
import { Chip } from '@/design-system';
import { TextField, Paper, ListItemButton, styled, Box } from '@mui/material';
export { ArtistSearchAvatar, DefaultSearchAvatar } from './Avatar.styles';
export { CategoryHeader, ResultTitle, ResultSubtitle } from './Typography.styles';

/**
 * SearchContainer - Root container for search input
 * Centered layout with max width constraint
 */
export const SearchContainer = styled(Box)(({ theme }) => ({
  position: 'relative',
  width: '100%',
  maxWidth: 600,
  margin: '0 auto'
}));

/**
 * SearchField - Styled search input with aurora focus color
 */
export const SearchField = styled(TextField)(({ theme }) => ({
  '& .MuiOutlinedInput-root': {
    backgroundColor: auroraOpacity.ultraLight,
    borderRadius: 24,
    '&:hover': {
      backgroundColor: auroraOpacity.veryLight
    },
    '&.Mui-focused': {
      backgroundColor: auroraOpacity.veryLight,
      '& fieldset': {
        borderColor: tokens.colors.accent.primary,
        borderWidth: 2
      }
    },
    '& fieldset': {
      borderColor: auroraOpacity.lighter
    }
  },
  '& .MuiOutlinedInput-input': {
    padding: '12px 16px',
    fontSize: '1rem'
  }
}));

/**
 * ResultsContainer - Dropdown results panel with blur background
 */
export const ResultsContainer = styled(Paper)(({ theme }) => ({
  position: 'absolute',
  top: '100%',
  left: 0,
  right: 0,
  marginTop: theme.spacing(1),
  maxHeight: 500,
  overflowY: 'auto',
  background: tokens.colors.bg.secondary,
  backdropFilter: 'blur(20px)',
  border: `1px solid ${auroraOpacity.lighter}`,
  borderRadius: theme.spacing(2),
  boxShadow: containerShadows.resultsPanel,
  zIndex: 1000
}));

/**
 * StyledListItemButton - Result row with hover effects
 */
export const StyledListItemButton = styled(ListItemButton)(({ theme }) => ({
  borderRadius: theme.spacing(1),
  margin: theme.spacing(0.5, 1),
  '&:hover': {
    backgroundColor: auroraOpacity.ultraLight,
    '& .result-title': {
      color: tokens.colors.accent.primary
    }
  }
}));

/**
 * TypeChip - Type indicator with color coding
 * Supports track, album, artist types with distinct colors
 */
export const TypeChip = styled(Chip)(({ theme }) => ({
  height: 20,
  fontSize: '0.7rem',
  fontWeight: 600,
  '&.track': {
    backgroundColor: auroraOpacity.light,
    color: tokens.colors.accent.primary
  },
  '&.album': {
    backgroundColor: auroraOpacity.standard,
    color: tokens.colors.accent.secondary
  },
  '&.artist': {
    backgroundColor: auroraOpacity.standard,
    color: tokens.colors.accent.tertiary
  }
}));

