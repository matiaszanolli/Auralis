/**
 * AlbumCharacterPane Component
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Right sidebar panel showing album's sonic character.
 * Replaces track-level Auto-Mastering parameters in Albums view.
 *
 * Features:
 * - Aggregate fingerprint visualization (waveform-inspired)
 * - Mood tags (High-energy, Warm, Wide stereo, etc.)
 * - CALM ↔ AGGRESSIVE energy slider
 * - Textual description
 *
 * Design Philosophy:
 * - Browsing context = Emotional, not analytical
 * - Album-level aggregate, not track-level parameters
 * - Ambient visualization, not busy UI
 */

import React from 'react';
import { Box, Typography, Chip, LinearProgress } from '@mui/material';
import { tokens } from '@/design-system';
import type { AudioFingerprint } from '@/utils/fingerprintToGradient';
import { computeAlbumCharacter } from '@/utils/albumCharacterDescriptors';
import { EnhancementToggle } from '@/components/shared/EnhancementToggle';

export interface AlbumCharacterPaneProps {
  /** Album fingerprint (median of all tracks) */
  fingerprint: AudioFingerprint | null;
  /** Album title */
  albumTitle?: string;
  /** Loading state */
  isLoading?: boolean;
  /** Enhancement enabled state */
  isEnhancementEnabled?: boolean;
  /** Enhancement toggle callback */
  onEnhancementToggle?: (enabled: boolean) => void;
}

/**
 * Energy slider component (CALM ↔ AGGRESSIVE)
 */
const EnergySlider: React.FC<{ energy: number }> = ({ energy }) => {
  // Map energy (0-1) to visual position
  const percentage = energy * 100;

  return (
    <Box sx={{ mt: tokens.spacing.lg }}>
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'space-between',
          mb: tokens.spacing.xs,
        }}
      >
        <Typography
          variant="caption"
          sx={{
            color: tokens.colors.text.tertiary,
            fontSize: tokens.typography.fontSize.xs,
            fontWeight: tokens.typography.fontWeight.medium,
            textTransform: 'uppercase',
            letterSpacing: '0.05em',
          }}
        >
          CALM
        </Typography>
        <Typography
          variant="caption"
          sx={{
            color: tokens.colors.text.tertiary,
            fontSize: tokens.typography.fontSize.xs,
            fontWeight: tokens.typography.fontWeight.medium,
            textTransform: 'uppercase',
            letterSpacing: '0.05em',
          }}
        >
          AGGRESSIVE
        </Typography>
      </Box>

      {/* Custom energy slider */}
      <Box
        sx={{
          position: 'relative',
          height: '6px',
          borderRadius: tokens.borderRadius.full,
          background: `linear-gradient(to right,
            ${tokens.colors.semantic.info} 0%,
            ${tokens.colors.semantic.warning} 50%,
            ${tokens.colors.semantic.error} 100%)`,
          opacity: 0.3,
        }}
      >
        {/* Energy indicator */}
        <Box
          sx={{
            position: 'absolute',
            left: `${percentage}%`,
            top: '50%',
            transform: 'translate(-50%, -50%)',
            width: '14px',
            height: '14px',
            borderRadius: tokens.borderRadius.full,
            background: tokens.colors.accent.primary,
            border: `2px solid ${tokens.colors.bg.primary}`,
            boxShadow: `0 0 0 2px ${tokens.colors.accent.primary}40`,
            transition: `left ${tokens.transitions.base}`,
          }}
        />
      </Box>
    </Box>
  );
};

/**
 * Waveform-inspired visualization
 * Simple ambient representation of album's sonic profile
 */
const WaveformVisualization: React.FC<{ fingerprint: AudioFingerprint }> = ({
  fingerprint,
}) => {
  // Generate simplified waveform from frequency distribution
  const frequencyBands = [
    fingerprint.sub_bass,
    fingerprint.bass,
    fingerprint.low_mid,
    fingerprint.mid,
    fingerprint.upper_mid,
    fingerprint.presence,
    fingerprint.air,
  ];

  // Normalize to 0-1 range for visualization
  const maxValue = Math.max(...frequencyBands, 0.01);
  const normalizedBands = frequencyBands.map((v) => v / maxValue);

  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'flex-end',
        justifyContent: 'space-around',
        height: '80px',
        gap: tokens.spacing.xs,
        mt: tokens.spacing.xl,
        mb: tokens.spacing.lg,
        px: tokens.spacing.md,
      }}
    >
      {normalizedBands.map((value, index) => (
        <Box
          key={index}
          sx={{
            flex: 1,
            height: `${value * 100}%`,
            minHeight: '8px',
            borderRadius: `${tokens.borderRadius.sm}px`,
            background: `linear-gradient(to top, ${tokens.colors.accent.primary}, ${tokens.colors.accent.tertiary})`,
            opacity: 0.6 + value * 0.4, // Higher bands more opaque
            transition: `height ${tokens.transitions.slow}`,
          }}
        />
      ))}
    </Box>
  );
};

/**
 * AlbumCharacterPane - Album sonic character display
 *
 * Shows aggregate analysis instead of track-level parameters.
 * Creates continuity between browsing and listening.
 */
export const AlbumCharacterPane: React.FC<AlbumCharacterPaneProps> = ({
  fingerprint,
  albumTitle,
  isLoading = false,
  isEnhancementEnabled = true,
  onEnhancementToggle,
}) => {
  // Enhancement toggle section (always shown at top)
  const EnhancementSection = () => (
    <Box
      sx={{
        pb: tokens.spacing.lg,
        mb: tokens.spacing.lg,
        borderBottom: `1px solid ${tokens.colors.border.light}`,
      }}
    >
      <EnhancementToggle
        variant="switch"
        isEnabled={isEnhancementEnabled}
        onToggle={onEnhancementToggle ?? (() => {})}
        label="Auto-Mastering"
        description={isEnhancementEnabled ? 'Enhancing playback' : 'Original audio'}
        showDescription
      />
    </Box>
  );

  // Empty state (no album selected or no fingerprint)
  if (!fingerprint && !isLoading) {
    return (
      <Box
        sx={{
          width: tokens.components.rightPanel.width, // 360px from design tokens
          background: tokens.colors.bg.elevated,
          borderLeft: `1px solid ${tokens.colors.border.light}`,
          p: tokens.spacing.xl,
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        <EnhancementSection />
        <Box
          sx={{
            flex: 1,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <Typography
            variant="body2"
            sx={{
              color: tokens.colors.text.tertiary,
              textAlign: 'center',
              fontSize: tokens.typography.fontSize.sm,
            }}
          >
            Hover over an album to view its sonic character
          </Typography>
        </Box>
      </Box>
    );
  }

  // Loading state
  if (isLoading || !fingerprint) {
    return (
      <Box
        sx={{
          width: tokens.components.rightPanel.width,
          background: tokens.colors.bg.elevated,
          borderLeft: `1px solid ${tokens.colors.border.light}`,
          p: tokens.spacing.xl,
        }}
      >
        <EnhancementSection />
        <LinearProgress sx={{ mb: tokens.spacing.lg }} />
        <Typography
          variant="body2"
          sx={{ color: tokens.colors.text.tertiary, textAlign: 'center' }}
        >
          Analyzing album character...
        </Typography>
      </Box>
    );
  }

  // Compute character from fingerprint
  const character = computeAlbumCharacter(fingerprint);

  return (
    <Box
      sx={{
        width: tokens.components.rightPanel.width,
        background: tokens.colors.bg.elevated,
        borderLeft: `1px solid ${tokens.colors.border.light}`,
        p: tokens.spacing.xl,
        overflowY: 'auto',
      }}
    >
      {/* Enhancement Toggle */}
      <EnhancementSection />

      {/* Header */}
      <Box sx={{ mb: tokens.spacing.xl }}>
        <Typography
          variant="h6"
          sx={{
            fontSize: tokens.typography.fontSize.lg,
            fontWeight: tokens.typography.fontWeight.semibold,
            color: tokens.colors.text.primary,
            mb: tokens.spacing.xs,
          }}
        >
          Album Character
        </Typography>
        {albumTitle && (
          <Typography
            variant="caption"
            sx={{
              color: tokens.colors.text.tertiary,
              fontSize: tokens.typography.fontSize.xs,
            }}
          >
            {albumTitle}
          </Typography>
        )}
      </Box>

      {/* Waveform visualization */}
      <WaveformVisualization fingerprint={fingerprint} />

      {/* Character tags */}
      <Box
        sx={{
          display: 'flex',
          flexWrap: 'wrap',
          gap: tokens.spacing.sm,
          mb: tokens.spacing.lg,
        }}
      >
        {character.tags.map((tag, index) => (
          <Chip
            key={index}
            label={tag.label}
            size="small"
            sx={{
              background: tokens.colors.bg.level2,
              color: tokens.colors.text.secondary,
              fontSize: tokens.typography.fontSize.xs,
              fontWeight: tokens.typography.fontWeight.medium,
              border: `1px solid ${tokens.colors.border.light}`,
              '&:hover': {
                background: tokens.colors.bg.level3,
              },
            }}
          />
        ))}
      </Box>

      {/* Energy slider */}
      <EnergySlider energy={character.energyLevel} />

      {/* Description */}
      <Box sx={{ mt: tokens.spacing.xl }}>
        <Typography
          variant="body2"
          sx={{
            color: tokens.colors.text.secondary,
            fontSize: tokens.typography.fontSize.sm,
            lineHeight: 1.6,
          }}
        >
          {character.description}
        </Typography>
      </Box>

      {/* Mood discovery prompt */}
      <Box
        sx={{
          mt: tokens.spacing.xxl,
          pt: tokens.spacing.lg,
          borderTop: `1px solid ${tokens.colors.border.light}`,
        }}
      >
        <Typography
          variant="caption"
          sx={{
            color: tokens.colors.text.tertiary,
            fontSize: tokens.typography.fontSize.xs,
            display: 'flex',
            alignItems: 'center',
            gap: tokens.spacing.xs,
          }}
        >
          ✨ Explore mood-based discovery...
        </Typography>
      </Box>
    </Box>
  );
};

export default AlbumCharacterPane;
