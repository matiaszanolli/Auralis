/**
 * SimilarTracksModal - Phase 5: Mood-Aware Interaction
 *
 * Modal displaying similar tracks based on fingerprint similarity.
 * Uses the useSimilarTracks hook to fetch acoustically similar tracks.
 *
 * Features:
 * - Displays similarity scores as percentage bars
 * - Click track to play
 * - Loading and error states
 * - Glass effect design (Design Language v1.2.0)
 *
 * Usage:
 * ```tsx
 * const [modalOpen, setModalOpen] = useState(false);
 * const [selectedTrackId, setSelectedTrackId] = useState<number | null>(null);
 *
 * <SimilarTracksModal
 *   open={modalOpen}
 *   trackId={selectedTrackId}
 *   onClose={() => setModalOpen(false)}
 *   onTrackPlay={handlePlay}
 * />
 * ```
 */

import { useEffect } from 'react';
import { Dialog, DialogContent, Box, Typography, CircularProgress, List } from '@mui/material';
import { tokens } from '@/design-system';
import {
  useSimilarTracks,
  classifySimilarityError,
  type SimilarTrack,
} from '@/hooks/fingerprint';
import { SimilarTracksModalHeader } from './SimilarTracksModalHeader';
import { SimilarTrackRow } from './SimilarTrackRow';
import { themeVars } from '@/theme/semanticTheme';

export interface SimilarTracksModalProps {
  /** Is modal open? */
  open: boolean;
  /** Track ID to find similar tracks for */
  trackId: number | null;
  /** Track title (for display in header) */
  trackTitle?: string;
  /** Callback when modal closes */
  onClose: () => void;
  /** Callback when user clicks a track to play */
  onTrackPlay?: (trackId: number) => void;
  /** Number of similar tracks to fetch (default: 20) */
  limit?: number;
}

/**
 * SimilarTracksModal Component
 *
 * Modal for displaying and interacting with similar tracks
 */
export const SimilarTracksModal = ({
  open,
  trackId,
  trackTitle = 'this track',
  onClose,
  onTrackPlay,
  limit = 20,
}: SimilarTracksModalProps) => {
  const { similarTracks, loading, error, errorStatus, findSimilar, clear } =
    useSimilarTracks();

  // The backend distinguishes "queued for fingerprinting", "still initialising"
  // and "no such track"; two of those are progress rather than failure, so they
  // must not render as a red error (#4626).
  const errorState = error ? classifySimilarityError(error, errorStatus) : null;

  // Fetch similar tracks when modal opens with a valid trackId
  useEffect(() => {
    if (open && trackId) {
      findSimilar(trackId, { limit, includeDetails: true }).catch((err) => {
        console.error('[SimilarTracksModal] Failed to find similar tracks:', err);
      });
    }

    // Clear results when modal closes
    if (!open) {
      clear();
    }
  }, [open, trackId, limit, findSimilar, clear]);

  /**
   * Handle track click - play track and close modal
   */
  const handleTrackClick = (track: SimilarTrack) => {
    if (onTrackPlay) {
      onTrackPlay(track.trackId);
    }
    onClose();
  };

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="sm"
      fullWidth
      slotProps={{
        paper: {
          sx: {
            // Glass effect for modal (Design Language v1.2.0 §4.2)
            background: tokens.glass.strong.background,
            backdropFilter: tokens.glass.strong.backdropFilter,   // 40px blur
            border: tokens.glass.strong.border,                   // 22% white opacity
            boxShadow: tokens.glass.strong.boxShadow,
            borderRadius: tokens.borderRadius.lg,                 // 16px - organic
            maxHeight: '80vh',
          },
        },
      }}
    >
      <SimilarTracksModalHeader trackTitle={trackTitle} onClose={onClose} />

      {/* Content */}
      <DialogContent sx={{
        padding: 0,
        overflowY: 'auto',
      }}>
        {/* Loading State */}
        {loading && (
          <Box sx={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            padding: tokens.spacing.xxl,                        // 40px
            gap: tokens.spacing.md,                             // 12px
          }}>
            <CircularProgress sx={{ color: tokens.colors.accent.primary }} />
            <Typography sx={{
              fontSize: tokens.typography.fontSize.base,        // 16px
              color: themeVars.textSecondary,
            }}>
              Analyzing fingerprint space...
            </Typography>
          </Box>
        )}

        {/* Error / pending State */}
        {errorState && !loading && (
          <Box sx={{
            padding: tokens.spacing.xxl,                        // 40px
            textAlign: 'center',
          }}>
            <Typography sx={{
              fontSize: tokens.typography.fontSize.base,        // 16px
              color: errorState.transient
                ? tokens.colors.semantic.info
                : tokens.colors.semantic.error,
              marginBottom: tokens.spacing.md,                  // 12px
            }}>
              {errorState.transient ? '⏳' : '⚠️'} {errorState.title}
            </Typography>
            <Typography sx={{
              fontSize: tokens.typography.fontSize.sm,          // 13px
              color: themeVars.textSecondary,
            }}>
              {errorState.hint}
            </Typography>
          </Box>
        )}

        {/* Results */}
        {similarTracks && similarTracks.length > 0 && !loading && (
          <List sx={{ padding: 0 }}>
            {similarTracks.map((track, index) => (
              <SimilarTrackRow
                key={track.trackId}
                track={track}
                rank={index + 1}
                isLast={index === similarTracks.length - 1}
                onClick={handleTrackClick}
              />
            ))}
          </List>
        )}

        {/* No Results */}
        {similarTracks && similarTracks.length === 0 && !loading && !errorState && (
          <Box sx={{
            padding: tokens.spacing.xxl,                        // 40px
            textAlign: 'center',
          }}>
            <Typography sx={{
              fontSize: tokens.typography.fontSize.base,        // 16px
              color: themeVars.textSecondary,
              marginBottom: tokens.spacing.md,                  // 12px
            }}>
              No similar tracks found.
            </Typography>
            <Typography sx={{
              fontSize: tokens.typography.fontSize.sm,          // 13px
              color: themeVars.textMuted,
            }}>
              Try a different track or check back later.
            </Typography>
          </Box>
        )}
      </DialogContent>
    </Dialog>
  );
};

export default SimilarTracksModal;
