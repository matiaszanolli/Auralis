/**
 * ArtistDetail Styles - Reusable artist detail component styling
 *
 * Consolidates styled components from ArtistDetailView for better organization
 * and reusability across artist-related components.
 */

import { Paper, Typography, Tabs, Box, TableContainer, styled } from '@mui/material';

/**
 * AlbumCard - Card container for album displays in artist view
 * Features hover elevation and color transition on album title
 */
export const AlbumCard = styled(Paper)(({ theme }) => ({
  background: 'rgba(255,255,255,0.03)',
  borderRadius: theme.spacing(2),
  overflow: 'hidden',
  cursor: 'pointer',
  transition: 'all 0.2s ease',
  border: '1px solid rgba(255,255,255,0.05)',
  '&:hover': {
    transform: 'translateY(-4px)',
    boxShadow: '0 8px 24px rgba(0,0,0,0.3)',
    '& .album-title': {
      color: '#667eea'
    }
  }
}));

/**
 * AlbumTitle - Title typography for album cards
 */
export const AlbumTitle = styled(Typography)(({ theme }) => ({
  fontSize: '1rem',
  fontWeight: 600,
  color: theme.palette.text.primary,
  marginBottom: 4,
  transition: 'color 0.2s ease'
}));

/**
 * AlbumInfo - Secondary information typography for album cards (year, track count)
 */
export const AlbumInfo = styled(Typography)(({ theme }) => ({
  fontSize: '0.875rem',
  color: theme.palette.text.secondary
}));

/**
 * StyledTabs - Tab navigation with aurora indicator for albums/tracks view
 */
export const StyledTabs = styled(Tabs)(({ theme }) => ({
  borderBottom: '1px solid rgba(255,255,255,0.1)',
  marginBottom: theme.spacing(3),
  '& .MuiTab-root': {
    textTransform: 'none',
    fontSize: '1rem',
    fontWeight: 500,
    minWidth: 120,
    '&.Mui-selected': {
      color: '#667eea'
    }
  },
  '& .MuiTabs-indicator': {
    backgroundColor: '#667eea'
  }
}));

/**
 * ArtistAvatarCircle - Circular artist avatar with aurora gradient background
 * Used for displaying artist initials
 */
export const ArtistAvatarCircle = styled(Box)(({ theme }) => ({
  width: 200,
  height: 200,
  borderRadius: '50%',
  background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  fontSize: '5rem',
  fontWeight: 'bold',
  color: 'white',
  boxShadow: '0 8px 32px rgba(102, 126, 234, 0.3)',
}));

/**
 * NoAlbumsContainer - Empty state container for when artist has no albums
 */
export const NoAlbumsContainer = styled(Paper)(({ theme }) => ({
  padding: theme.spacing(4),
  textAlign: 'center',
  background: 'rgba(255,255,255,0.03)',
  borderRadius: theme.spacing(2)
}));

/**
 * TracksTableContainer - Container for the tracks table with styling
 */
export const TracksTableContainer = styled(TableContainer)(({ theme }) => ({
  background: 'rgba(255,255,255,0.03)',
  borderRadius: theme.spacing(2),
  backdropFilter: 'blur(10px)'
}));
