/**
 * SimilarTrackRow
 * ~~~~~~~~~~~~~~~~
 *
 * A single result row (rank/play icon, track info, similarity bar) in
 * SimilarTracksModal's results list. Extracted from SimilarTracksModal.tsx
 * (#4916) to bring it under the project's 300-line component guideline.
 */

import { ListItem, ListItemButton, ListItemText, Box, Typography } from '@mui/material';
import PlayArrow from '@mui/icons-material/PlayArrow';
import { tokens } from '@/design-system';
import type { SimilarTrack } from '@/hooks/fingerprint';
import { themeVars } from '@/theme/semanticTheme';

export interface SimilarTrackRowProps {
  track: SimilarTrack;
  /** 1-based rank shown before the play icon. */
  rank: number;
  /** Whether this is the last row (suppresses the bottom border). */
  isLast: boolean;
  onClick: (track: SimilarTrack) => void;
}

export const SimilarTrackRow = ({ track, rank, isLast, onClick }: SimilarTrackRowProps) => (
  <ListItem
    disablePadding
    sx={{
      borderBottom: isLast ? 'none' : `1px solid ${tokens.colors.border.light}`,
    }}
  >
    <ListItemButton
      onClick={() => onClick(track)}
      sx={{
        padding: tokens.spacing.md,                 // 12px
        gap: tokens.spacing.md,                      // 12px
        transition: tokens.transitions.fast,         // 150ms hover
        '&:hover': {
          backgroundColor: themeVars.surfacePrimary,
          '& .play-icon': {
            opacity: 1,
            transform: 'scale(1)',
          },
        },
      }}
    >
      {/* Rank Number / Play Icon */}
      <Box sx={{
        minWidth: '32px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        position: 'relative',
      }}>
        <Typography sx={{
          fontSize: tokens.typography.fontSize.base, // 16px
          fontWeight: tokens.typography.fontWeight.medium,
          color: themeVars.textSecondary,
          transition: tokens.transitions.fast,
        }}>
          {rank}
        </Typography>
        <PlayArrow
          className="play-icon"
          sx={{
            position: 'absolute',
            opacity: 0,
            transform: 'scale(0.8)',
            transition: tokens.transitions.fast,    // 150ms
            color: tokens.colors.accent.primary,
            fontSize: tokens.typography.fontSize.lg,
          }}
        />
      </Box>

      {/* Track Info */}
      <ListItemText
        primary={track.title || `Track ${track.trackId}`}
        secondary={track.artist || 'Unknown Artist'}
        slotProps={{
          primary: {
            sx: {
              fontSize: tokens.typography.fontSize.base, // 16px
              fontWeight: tokens.typography.fontWeight.medium,
              color: themeVars.textPrimary,
            },
          },
          secondary: {
            sx: {
              fontSize: tokens.typography.fontSize.sm, // 13px
              color: themeVars.textSecondary,
              marginTop: tokens.spacing.xs,            // 4px
            },
          },
        }}
      />

      {/* Similarity Score */}
      <Box sx={{
        minWidth: '80px',
        textAlign: 'right',
      }}>
        <Typography sx={{
          fontSize: tokens.typography.fontSize.sm,  // 13px
          fontWeight: tokens.typography.fontWeight.medium,
          color: tokens.colors.accent.primary,
          marginBottom: tokens.spacing.xs,          // 4px
        }}>
          {(track.similarityScore * 100).toFixed(0)}% match
        </Typography>
        {/* Similarity Bar */}
        <Box sx={{
          width: '100%',
          height: '3px',
          backgroundColor: tokens.colors.border.medium,
          borderRadius: tokens.borderRadius.full,   // 9999px pill
          overflow: 'hidden',
        }}>
          <Box sx={{
            width: `${track.similarityScore * 100}%`,
            height: '100%',
            backgroundColor: tokens.colors.accent.primary,
            transition: `width ${tokens.transitions.slow}`, // 500-600ms
          }} />
        </Box>
      </Box>
    </ListItemButton>
  </ListItem>
);

export default SimilarTrackRow;
