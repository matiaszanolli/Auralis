/**
 * Table Styles - Reusable table component styles for detail views
 *
 * Consolidates styled table components used in track listings.
 */

import { Box, TableRow, styled } from '@mui/material';

/**
 * StyledTableRow - Interactive table row with hover effects and current track highlighting
 * Used in AlbumDetailView and ArtistDetailView for track listings
 */
export const StyledTableRow = styled(TableRow)(({ theme }) => ({
  cursor: 'pointer',
  transition: 'background-color 0.2s ease',
  '&:hover': {
    backgroundColor: 'rgba(255,255,255,0.05)',
    '& .play-icon': {
      opacity: 1
    }
  },
  '&.current-track': {
    backgroundColor: 'rgba(102, 126, 234, 0.15)',
    '& .track-number': {
      color: '#667eea'
    },
    '& .track-title': {
      color: '#667eea',
      fontWeight: 'bold'
    }
  }
}));

/**
 * PlayIcon - Icon container that appears on row hover
 * Animates in/out when hovering over track rows
 */
export const PlayIcon = styled(Box)({
  opacity: 0,
  transition: 'opacity 0.2s ease',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center'
});
