/**
 * ArtistInfoModal Component
 * ~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Display-only modal for artist information.
 * Shows artist name, album count, and track count.
 *
 * @example
 * <ArtistInfoModal
 *   open={modalOpen}
 *   artist={selectedArtist}
 *   onClose={() => setModalOpen(false)}
 * />
 */

import React from 'react';
import { DialogContent, DialogActions, Box } from '@mui/material';
import { Close as CloseIcon } from '@mui/icons-material';
import { tokens } from '@/design-system';
import { StyledDialog, StyledDialogTitle, CancelButtonForDialog } from '../../Styles/Dialog.styles';

interface ArtistInfo {
  id: number;
  name: string;
  album_count?: number;
  track_count?: number;
}

interface ArtistInfoModalProps {
  open: boolean;
  artist: ArtistInfo | null;
  onClose: () => void;
}

/**
 * ArtistInfoModal - Display-only modal for artist information
 *
 * Features:
 * - Shows artist name, album count, and track count
 * - Clean, centered layout
 * - Design system token styling
 * - Close button in actions bar
 */
export const ArtistInfoModal: React.FC<ArtistInfoModalProps> = ({
  open,
  artist,
  onClose,
}) => {
  if (!artist) return null;

  return (
    <StyledDialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <StyledDialogTitle>Artist Information</StyledDialogTitle>

      <DialogContent sx={styles.content}>
        <Box sx={styles.artistContainer}>
          {/* Artist Name */}
          <h2 style={styles.artistName}>{artist.name}</h2>

          {/* Album and Track Count */}
          <Box sx={styles.statsContainer}>
            <Box sx={styles.statItem}>
              <span style={styles.statLabel}>Albums</span>
              <span style={styles.statValue}>{artist.album_count ?? 0}</span>
            </Box>

            <Box sx={styles.statDivider} />

            <Box sx={styles.statItem}>
              <span style={styles.statLabel}>Tracks</span>
              <span style={styles.statValue}>{artist.track_count ?? 0}</span>
            </Box>
          </Box>
        </Box>
      </DialogContent>

      <DialogActions sx={styles.actions}>
        <CancelButtonForDialog
          onClick={onClose}
          startIcon={<CloseIcon />}
        >
          Close
        </CancelButtonForDialog>
      </DialogActions>
    </StyledDialog>
  );
};

const styles = {
  content: {
    display: 'flex',
    justifyContent: 'center',
    alignItems: 'center',
    minHeight: '200px',
  },

  artistContainer: {
    textAlign: 'center' as const,
    width: '100%',
  },

  artistName: {
    margin: 0,
    marginBottom: tokens.spacing.lg,
    fontSize: tokens.typography.fontSize.xl,
    fontWeight: tokens.typography.fontWeight.bold,
    color: tokens.colors.text.primary,
  },

  statsContainer: {
    display: 'flex',
    justifyContent: 'center',
    alignItems: 'center',
    gap: tokens.spacing.lg,
  },

  statItem: {
    display: 'flex',
    flexDirection: 'column' as const,
    alignItems: 'center',
    gap: tokens.spacing.xs,
  },

  statLabel: {
    fontSize: tokens.typography.fontSize.sm,
    color: tokens.colors.text.secondary,
    fontWeight: tokens.typography.fontWeight.semibold,
    textTransform: 'uppercase' as const,
    letterSpacing: '0.5px',
  },

  statValue: {
    fontSize: tokens.typography.fontSize.lg,
    fontWeight: tokens.typography.fontWeight.bold,
    color: tokens.colors.accent.primary,
  },

  statDivider: {
    width: '1px',
    height: '40px',
    backgroundColor: tokens.colors.border.light,
  },

  actions: {
    justifyContent: 'center',
    padding: tokens.spacing.md,
  },
};

export default ArtistInfoModal;
