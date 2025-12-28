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

import React, { useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  IconButton,
  Box,
  Typography,
  CircularProgress,
  List,
  ListItem,
  ListItemButton,
  ListItemText,
} from '@mui/material';
import { Close, PlayArrow, Explore } from '@mui/icons-material';
import { tokens } from '@/design-system';
import { useSimilarTracks, type SimilarTrack } from '@/hooks/fingerprint';

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
export const SimilarTracksModal: React.FC<SimilarTracksModalProps> = ({
  open,
  trackId,
  trackTitle = 'this track',
  onClose,
  onTrackPlay,
  limit = 20,
}) => {
  const { similarTracks, loading, error, findSimilar, clear } = useSimilarTracks();

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
      PaperProps={{
        sx: {
          // Glass effect for modal (Design Language v1.2.0 §4.2)
          background: tokens.glass.strong.background,
          backdropFilter: tokens.glass.strong.backdropFilter,   // 40px blur
          border: tokens.glass.strong.border,                   // 22% white opacity
          boxShadow: tokens.glass.strong.boxShadow,
          borderRadius: tokens.borderRadius.lg,                 // 16px - organic
          maxHeight: '80vh',
        },
      }}
    >
      {/* Header */}
      <DialogTitle sx={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: tokens.spacing.md,                                 // 12px
        padding: tokens.spacing.lg,                             // 16px
        borderBottom: `1px solid ${tokens.colors.border.light}`,
      }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: tokens.spacing.md }}>
          <Explore sx={{ color: tokens.colors.accent.primary, fontSize: '28px' }} />
          <Box>
            <Typography variant="h6" sx={{
              fontFamily: tokens.typography.fontFamily.header,  // Manrope for headers
              fontWeight: tokens.typography.fontWeight.semibold,
              fontSize: tokens.typography.fontSize.xl,          // 24px
              color: tokens.colors.text.primary,
            }}>
              Similar Tracks
            </Typography>
            <Typography variant="body2" sx={{
              fontSize: tokens.typography.fontSize.sm,          // 13px
              color: tokens.colors.text.secondary,
              marginTop: tokens.spacing.xs,                     // 4px
            }}>
              Tracks similar to "{trackTitle}"
            </Typography>
          </Box>
        </Box>
        <IconButton
          onClick={onClose}
          sx={{
            color: tokens.colors.text.secondary,
            '&:hover': {
              backgroundColor: tokens.colors.bg.tertiary,
            },
          }}
        >
          <Close />
        </IconButton>
      </DialogTitle>

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
              color: tokens.colors.text.secondary,
            }}>
              Analyzing fingerprint space...
            </Typography>
          </Box>
        )}

        {/* Error State */}
        {error && !loading && (
          <Box sx={{
            padding: tokens.spacing.xxl,                        // 40px
            textAlign: 'center',
          }}>
            <Typography sx={{
              fontSize: tokens.typography.fontSize.base,        // 16px
              color: tokens.colors.semantic.error,
              marginBottom: tokens.spacing.md,                  // 12px
            }}>
              ⚠️ {error}
            </Typography>
            <Typography sx={{
              fontSize: tokens.typography.fontSize.sm,          // 13px
              color: tokens.colors.text.secondary,
            }}>
              Try again or select a different track.
            </Typography>
          </Box>
        )}

        {/* Results */}
        {similarTracks && similarTracks.length > 0 && !loading && (
          <List sx={{ padding: 0 }}>
            {similarTracks.map((track, index) => (
              <ListItem
                key={track.trackId}
                disablePadding
                sx={{
                  borderBottom: index < similarTracks.length - 1
                    ? `1px solid ${tokens.colors.border.light}`
                    : 'none',
                }}
              >
                <ListItemButton
                  onClick={() => handleTrackClick(track)}
                  sx={{
                    padding: tokens.spacing.md,                 // 12px
                    gap: tokens.spacing.md,                     // 12px
                    transition: tokens.transitions.fast,        // 150ms hover
                    '&:hover': {
                      backgroundColor: tokens.colors.bg.secondary,
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
                      color: tokens.colors.text.secondary,
                      transition: tokens.transitions.fast,
                    }}>
                      {index + 1}
                    </Typography>
                    <PlayArrow
                      className="play-icon"
                      sx={{
                        position: 'absolute',
                        opacity: 0,
                        transform: 'scale(0.8)',
                        transition: tokens.transitions.fast,    // 150ms
                        color: tokens.colors.accent.primary,
                        fontSize: '20px',
                      }}
                    />
                  </Box>

                  {/* Track Info */}
                  <ListItemText
                    primary={track.title || `Track ${track.trackId}`}
                    secondary={track.artist || 'Unknown Artist'}
                    primaryTypographyProps={{
                      sx: {
                        fontSize: tokens.typography.fontSize.base, // 16px
                        fontWeight: tokens.typography.fontWeight.medium,
                        color: tokens.colors.text.primary,
                      },
                    }}
                    secondaryTypographyProps={{
                      sx: {
                        fontSize: tokens.typography.fontSize.sm, // 13px
                        color: tokens.colors.text.secondary,
                        marginTop: tokens.spacing.xs,           // 4px
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
            ))}
          </List>
        )}

        {/* No Results */}
        {similarTracks && similarTracks.length === 0 && !loading && !error && (
          <Box sx={{
            padding: tokens.spacing.xxl,                        // 40px
            textAlign: 'center',
          }}>
            <Typography sx={{
              fontSize: tokens.typography.fontSize.base,        // 16px
              color: tokens.colors.text.secondary,
              marginBottom: tokens.spacing.md,                  // 12px
            }}>
              No similar tracks found.
            </Typography>
            <Typography sx={{
              fontSize: tokens.typography.fontSize.sm,          // 13px
              color: tokens.colors.text.tertiary,
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
