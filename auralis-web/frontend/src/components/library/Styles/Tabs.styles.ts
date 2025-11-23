/**
 * Tabs Styles - Reusable tab component styling
 *
 * Consolidates tab navigation patterns with aurora indicator styling
 * used across dialogs and detail views.
 *
 * Includes:
 * - DialogTabs: Compact tabs for dialog interfaces (minHeight: 48)
 * - DetailViewTabs: Larger tabs for detail view interfaces (fontSize: 1rem, marginBottom: 3)
 *
 * Both use aurora gradient color (#667eea) for selected state and indicator.
 */

import { Tabs, styled } from '@mui/material';
import { colorAuroraPrimary } from './Color.styles';

/**
 * DialogTabs - Tab navigation for dialog interfaces
 * Compact styling (minHeight 48, fontSize 0.95rem) for dialog content
 * Used by: SettingsDialog, CreatePlaylistDialog, EditPlaylistDialog
 */
export const DialogTabs = styled(Tabs)(({ theme }) => ({
  borderBottom: '1px solid rgba(255,255,255,0.1)',
  minHeight: 48,
  '& .MuiTab-root': {
    textTransform: 'none',
    fontSize: '0.95rem',
    minHeight: 48,
    color: theme.palette.text.secondary,
    '&.Mui-selected': {
      color: colorAuroraPrimary
    }
  },
  '& .MuiTabs-indicator': {
    backgroundColor: colorAuroraPrimary
  }
}));

/**
 * DetailViewTabs - Tab navigation for detail view interfaces
 * Larger styling (fontSize 1rem, marginBottom 3, minWidth 120) for artist/album views
 * Used by: ArtistDetailView, AlbumDetailView
 */
export const DetailViewTabs = styled(Tabs)(({ theme }) => ({
  borderBottom: '1px solid rgba(255,255,255,0.1)',
  marginBottom: theme.spacing(3),
  '& .MuiTab-root': {
    textTransform: 'none',
    fontSize: '1rem',
    fontWeight: 500,
    minWidth: 120,
    '&.Mui-selected': {
      color: colorAuroraPrimary
    }
  },
  '& .MuiTabs-indicator': {
    backgroundColor: colorAuroraPrimary
  }
}));

/**
 * NOTE: StyledTabs is exported from ArtistDetail.styles.ts as a re-export of DetailViewTabs
 * Use DialogTabs or DetailViewTabs directly, or import StyledTabs from ArtistDetail.styles
 */
