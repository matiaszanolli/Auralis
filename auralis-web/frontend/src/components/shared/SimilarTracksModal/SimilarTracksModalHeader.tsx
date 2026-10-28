/**
 * SimilarTracksModalHeader
 * ~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * The DialogTitle block (icon, title, subtitle, close button) for
 * SimilarTracksModal. Extracted from SimilarTracksModal.tsx (#4916) to bring
 * it under the project's 300-line component guideline.
 */

import { DialogTitle, IconButton, Box, Typography } from '@mui/material';
import Close from '@mui/icons-material/Close';
import Explore from '@mui/icons-material/Explore';
import { tokens } from '@/design-system';
import { themeVars } from '@/theme/semanticTheme';

export interface SimilarTracksModalHeaderProps {
  /** Track title (for display in the subtitle) */
  trackTitle: string;
  onClose: () => void;
}

export const SimilarTracksModalHeader = ({ trackTitle, onClose }: SimilarTracksModalHeaderProps) => (
  <DialogTitle sx={{
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: tokens.spacing.md,                                 // 12px
    padding: tokens.spacing.lg,                             // 16px
    borderBottom: `1px solid ${tokens.colors.border.light}`,
  }}>
    <Box sx={{ display: 'flex', alignItems: 'center', gap: tokens.spacing.md }}>
      <Explore sx={{ color: tokens.colors.accent.primary, fontSize: tokens.typography.fontSize['2xl'] }} />
      <Box>
        {/* DialogTitle is already the dialog's <h2>; a nested heading or paragraph is invalid (#5671). */}
        <Typography component="span" variant="h6" sx={{
          display: 'block',
          fontFamily: tokens.typography.fontFamily.header,  // Manrope for headers
          fontWeight: tokens.typography.fontWeight.semibold,
          fontSize: tokens.typography.fontSize.xl,          // 24px
          color: themeVars.textPrimary,
        }}>
          Similar Tracks
        </Typography>
        <Typography component="span" variant="body2" sx={{
          display: 'block',
          fontSize: tokens.typography.fontSize.sm,          // 13px
          color: themeVars.textSecondary,
          marginTop: tokens.spacing.xs,                     // 4px
        }}>
          Tracks similar to "{trackTitle}"
        </Typography>
      </Box>
    </Box>
    <IconButton
      onClick={onClose}
      aria-label="Close similar tracks"
      sx={{
        color: themeVars.textSecondary,
        '&:hover': {
          backgroundColor: themeVars.surfaceSecondary,
        },
      }}
    >
      <Close />
    </IconButton>
  </DialogTitle>
);

export default SimilarTracksModalHeader;
