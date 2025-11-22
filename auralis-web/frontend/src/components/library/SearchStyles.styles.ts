/**
 * Search Styles - Reusable search component styling
 *
 * Consolidates search field, results container, and result item styling
 * used in GlobalSearch component.
 *
 * Avatar components (ArtistSearchAvatar, DefaultSearchAvatar) are imported from Avatar.styles.ts
 * Empty state components are imported from EmptyState.styles.ts
 * Shadow effects are imported from Shadow.styles.ts
 */

import { TextField, Paper, ListItemButton, Chip, styled, Box } from '@mui/material';
import { containerShadows } from './Shadow.styles';
export { ArtistSearchAvatar, DefaultSearchAvatar } from './Avatar.styles';
export { SearchEmptyState as EmptyResultsBox } from './EmptyState.styles';
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
    backgroundColor: 'rgba(255,255,255,0.05)',
    borderRadius: 24,
    '&:hover': {
      backgroundColor: 'rgba(255,255,255,0.08)'
    },
    '&.Mui-focused': {
      backgroundColor: 'rgba(255,255,255,0.08)',
      '& fieldset': {
        borderColor: '#667eea',
        borderWidth: 2
      }
    },
    '& fieldset': {
      borderColor: 'rgba(255,255,255,0.1)'
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
  background: 'rgba(26, 31, 58, 0.98)',
  backdropFilter: 'blur(20px)',
  border: '1px solid rgba(255,255,255,0.1)',
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
    backgroundColor: 'rgba(102, 126, 234, 0.1)',
    '& .result-title': {
      color: '#667eea'
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
    backgroundColor: 'rgba(102, 126, 234, 0.2)',
    color: '#667eea'
  },
  '&.album': {
    backgroundColor: 'rgba(118, 75, 162, 0.2)',
    color: '#764ba2'
  },
  '&.artist': {
    backgroundColor: 'rgba(236, 72, 153, 0.2)',
    color: '#ec4899'
  }
}));

