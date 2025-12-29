/**
 * AlbumCharacterPane Component
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Right sidebar panel showing album's sonic character.
 * Replaces track-level Auto-Mastering parameters in Albums view.
 *
 * Features:
 * - Aggregate fingerprint visualization (waveform-inspired)
 * - Mood tags with playback-aware breathing animations
 * - CALM ↔ AGGRESSIVE energy field (gradient, not slider)
 * - Rotating textual descriptions during playback
 * - Playback-aware visual states (alive when playing)
 *
 * Design Philosophy:
 * - Browsing context = Emotional, not analytical
 * - Album-level aggregate, not track-level parameters
 * - Living visualization, not static display
 * - Style Guide §6.1: Slow, weighted motion
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Box, Typography, Chip, LinearProgress, keyframes } from '@mui/material';
import { useSelector } from 'react-redux';
import { tokens } from '@/design-system';
import type { AudioFingerprint } from '@/utils/fingerprintToGradient';
import { computeAlbumCharacter } from '@/utils/albumCharacterDescriptors';
import { EnhancementToggle } from '@/components/shared/EnhancementToggle';
import { playerSelectors } from '@/store/selectors';

// ============================================================================
// Silence Decay Hook
// "The music stopped, but the impression lingers"
// ============================================================================

const DECAY_DURATION_MS = 2500; // 2.5 seconds of graceful fade

interface PlaybackDecayState {
  /** True when playing OR during decay period */
  isAnimating: boolean;
  /** 1.0 = full intensity, fades to 0 during decay */
  intensity: number;
  /** True only when actually playing (not during decay) */
  isPlaying: boolean;
}

/**
 * Custom hook that provides graceful animation decay when playback stops.
 * Instead of instantly freezing, animations fade over 2-3 seconds.
 * Glow effects fade last, creating a "lingering impression" effect.
 */
function usePlaybackWithDecay(isPlaying: boolean): PlaybackDecayState {
  const [isAnimating, setIsAnimating] = useState(isPlaying);
  const [intensity, setIntensity] = useState(isPlaying ? 1 : 0);
  const wasPlayingRef = useRef(isPlaying);
  const decayStartTimeRef = useRef<number | null>(null);
  const animationFrameRef = useRef<number | null>(null);

  useEffect(() => {
    // Transition: stopped → playing
    if (isPlaying && !wasPlayingRef.current) {
      // Cancel any decay in progress
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
        animationFrameRef.current = null;
      }
      decayStartTimeRef.current = null;
      setIsAnimating(true);
      setIntensity(1);
    }

    // Transition: playing → stopped (start decay)
    if (!isPlaying && wasPlayingRef.current) {
      decayStartTimeRef.current = performance.now();

      const animateDecay = (currentTime: number) => {
        if (!decayStartTimeRef.current) return;

        const elapsed = currentTime - decayStartTimeRef.current;
        const progress = Math.min(elapsed / DECAY_DURATION_MS, 1);

        // Easing: slow start, faster end (impression lingers longer)
        // Using quintic ease-out reversed for slow fade
        const easedProgress = 1 - Math.pow(1 - progress, 3);
        const newIntensity = 1 - easedProgress;

        setIntensity(newIntensity);

        if (progress < 1) {
          animationFrameRef.current = requestAnimationFrame(animateDecay);
        } else {
          // Decay complete
          setIsAnimating(false);
          setIntensity(0);
          decayStartTimeRef.current = null;
        }
      };

      animationFrameRef.current = requestAnimationFrame(animateDecay);
    }

    wasPlayingRef.current = isPlaying;

    return () => {
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
    };
  }, [isPlaying]);

  return { isAnimating, intensity, isPlaying };
}

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

// ============================================================================
// Keyframe Animations (Style Guide §6.1: Slow, weighted motion)
// ============================================================================

const breathePulse = keyframes`
  0%, 100% {
    opacity: 1;
    transform: scale(1);
  }
  50% {
    opacity: 0.85;
    transform: scale(1.02);
  }
`;

const subtleGlow = keyframes`
  0%, 100% {
    box-shadow: 0 0 0 0 transparent;
  }
  50% {
    box-shadow: 0 0 12px 2px rgba(115, 102, 240, 0.15);
  }
`;

const energyDrift = keyframes`
  0%, 100% {
    transform: translate(-50%, -50%) scale(1);
  }
  33% {
    transform: translate(-48%, -52%) scale(1.05);
  }
  66% {
    transform: translate(-52%, -48%) scale(0.98);
  }
`;

// ============================================================================
// Energy Field Component (Gradient field, not slider)
// ============================================================================

interface EnergyFieldProps {
  energy: number;
  isAnimating: boolean;
  intensity: number;
}

const EnergyField: React.FC<EnergyFieldProps> = ({ energy, isAnimating, intensity }) => {
  // Map energy (0-1) to visual position
  const percentage = energy * 100;

  // Calculate hue shift based on energy (cool blue → warm orange/red)
  // Calm: 210 (blue), Aggressive: 15 (orange-red)
  const hue = 210 - energy * 195;

  // Glow lingers longer (use sqrt for slower fade)
  const glowIntensity = Math.sqrt(intensity);

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
            opacity: 0.7 + intensity * 0.3,
            transition: `opacity ${tokens.transitions.slow}`,
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
            opacity: 0.7 + intensity * 0.3,
            transition: `opacity ${tokens.transitions.slow}`,
          }}
        >
          AGGRESSIVE
        </Typography>
      </Box>

      {/* Energy gradient field */}
      <Box
        sx={{
          position: 'relative',
          height: '8px',
          borderRadius: tokens.borderRadius.full,
          // Gradient from cool (calm) to warm (aggressive)
          // Intensity modulates the alpha
          background: `linear-gradient(to right,
            hsla(210, 80%, 60%, ${0.25 + intensity * 0.15}) 0%,
            hsla(45, 90%, 55%, ${0.25 + intensity * 0.15}) 50%,
            hsla(15, 95%, 55%, ${0.25 + intensity * 0.15}) 100%)`,
          transition: `all ${tokens.transitions.slow}`,
          // Subtle inner glow - lingers longer via glowIntensity
          boxShadow: glowIntensity > 0.1
            ? `inset 0 0 8px hsla(${hue}, 70%, 50%, ${0.2 * glowIntensity})`
            : 'none',
        }}
      >
        {/* Floating energy node (not a slider thumb) */}
        <Box
          sx={{
            position: 'absolute',
            left: `${percentage}%`,
            top: '50%',
            transform: 'translate(-50%, -50%)',
            width: '16px',
            height: '16px',
            borderRadius: tokens.borderRadius.full,
            // Dynamic hue based on energy
            background: `hsla(${hue}, 75%, 55%, 1)`,
            border: `2px solid ${tokens.colors.bg.primary}`,
            // Glow radius and intensity fade during decay (but linger)
            boxShadow: `0 0 ${6 + glowIntensity * 6}px hsla(${hue}, 70%, 50%, ${0.3 + glowIntensity * 0.2})`,
            transition: `left ${tokens.transitions.slow}, box-shadow ${tokens.transitions.base}`,
            // Subtle drift animation when animating
            animation: isAnimating
              ? `${energyDrift} 4s cubic-bezier(0.25, 0.46, 0.45, 0.94) infinite`
              : 'none',
          }}
        />
      </Box>
    </Box>
  );
};

// ============================================================================
// Waveform Visualization (Breathing when playing)
// ============================================================================

interface WaveformVisualizationProps {
  fingerprint: AudioFingerprint;
  isAnimating: boolean;
  intensity: number;
}

const WaveformVisualization: React.FC<WaveformVisualizationProps> = ({
  fingerprint,
  isAnimating,
  intensity,
}) => {
  const frequencyBands = [
    fingerprint.sub_bass,
    fingerprint.bass,
    fingerprint.low_mid,
    fingerprint.mid,
    fingerprint.upper_mid,
    fingerprint.presence,
    fingerprint.air,
  ];

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
            // Opacity fades with intensity during decay
            opacity: 0.5 + value * 0.3 + intensity * 0.2,
            transition: `all ${tokens.transitions.slow}`,
            // Subtle breathing animation when animating (continues during decay)
            animation: isAnimating
              ? `${breathePulse} ${2.5 + index * 0.3}s cubic-bezier(0.25, 0.46, 0.45, 0.94) infinite`
              : 'none',
            animationDelay: `${index * 0.15}s`,
          }}
        />
      ))}
    </Box>
  );
};

// ============================================================================
// Rotating Description Component
// ============================================================================

interface RotatingDescriptionProps {
  descriptions: string[];
  staticDescription: string;
  isPlaying: boolean;
}

const RotatingDescription: React.FC<RotatingDescriptionProps> = ({
  descriptions,
  staticDescription,
  isPlaying,
}) => {
  const [currentIndex, setCurrentIndex] = useState(0);
  const [isVisible, setIsVisible] = useState(true);

  // Rotate descriptions every 8-12 seconds when playing
  useEffect(() => {
    if (!isPlaying || descriptions.length === 0) {
      setCurrentIndex(0);
      return;
    }

    const interval = setInterval(() => {
      setIsVisible(false);
      setTimeout(() => {
        setCurrentIndex((prev) => (prev + 1) % descriptions.length);
        setIsVisible(true);
      }, 400); // Crossfade duration
    }, 10000); // 10 seconds between rotations

    return () => clearInterval(interval);
  }, [isPlaying, descriptions.length]);

  const displayText = isPlaying && descriptions.length > 0
    ? descriptions[currentIndex]
    : staticDescription;

  return (
    <Typography
      variant="body2"
      sx={{
        color: tokens.colors.text.secondary,
        fontSize: tokens.typography.fontSize.sm,
        lineHeight: 1.6,
        opacity: isVisible ? 1 : 0,
        transition: `opacity 0.4s cubic-bezier(0.25, 0.46, 0.45, 0.94)`,
        minHeight: '48px', // Prevent layout shift
      }}
    >
      {displayText}
    </Typography>
  );
};

// ============================================================================
// Character Tags with Breathing Animation
// ============================================================================

interface CharacterTagsProps {
  tags: Array<{ label: string; category: string }>;
  isAnimating: boolean;
  intensity: number;
}

const CharacterTags: React.FC<CharacterTagsProps> = ({ tags, isAnimating, intensity }) => {
  // Glow lingers longer (use sqrt for slower fade)
  const glowIntensity = Math.sqrt(intensity);

  return (
    <Box
      sx={{
        display: 'flex',
        flexWrap: 'wrap',
        gap: tokens.spacing.sm,
        mb: tokens.spacing.lg,
      }}
    >
      {tags.map((tag, index) => (
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
            transition: `all ${tokens.transitions.slow}`,
            // Subtle glow animation when animating (continues during decay, fades with intensity)
            animation: isAnimating
              ? `${subtleGlow} ${3 + index * 0.5}s cubic-bezier(0.25, 0.46, 0.45, 0.94) infinite`
              : 'none',
            animationDelay: `${index * 0.2}s`,
            // Glow lingers via glowIntensity
            boxShadow: glowIntensity > 0.1
              ? `0 0 ${8 * glowIntensity}px rgba(115, 102, 240, ${0.1 * glowIntensity})`
              : 'none',
            '&:hover': {
              background: tokens.colors.bg.level3,
            },
          }}
        />
      ))}
    </Box>
  );
};

// ============================================================================
// Main Component
// ============================================================================

export const AlbumCharacterPane: React.FC<AlbumCharacterPaneProps> = ({
  fingerprint,
  albumTitle,
  isLoading = false,
  isEnhancementEnabled = true,
  onEnhancementToggle,
}) => {
  // Get playback state from Redux
  const isPlayingRaw = useSelector(playerSelectors.selectIsPlaying);

  // Apply silence decay - motion fades gracefully over 2.5s when playback stops
  // "The music stopped, but the impression lingers"
  const { isAnimating, intensity, isPlaying } = usePlaybackWithDecay(isPlayingRaw);

  // Glow lingers longer - use sqrt for slower fade on container glow
  const glowIntensity = Math.sqrt(intensity);

  // Enhancement toggle section (always shown at top)
  const EnhancementSection = useCallback(() => (
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
  ), [isEnhancementEnabled, onEnhancementToggle]);

  // Container styles with playback-aware glow edge
  // Uses glowIntensity (0-1) for graceful fade - glow lingers last
  const containerStyles = {
    width: tokens.components.rightPanel.width,
    height: '100%',
    minHeight: 0, // Allow flex shrinking
    // Semi-transparent to let starfield show through
    background: 'rgba(26, 35, 56, 0.55)',
    backdropFilter: 'blur(10px) saturate(1.05)',
    border: 'none',  // No hard borders - use bevel shadows
    // Glass bevel with playback-aware glow: left highlight fades with intensity
    boxShadow: glowIntensity > 0.05
      ? `-2px 0 12px rgba(0, 0, 0, 0.10), inset 1px 0 0 rgba(115, 102, 240, ${0.15 + glowIntensity * 0.20}), inset 3px 0 12px -4px rgba(115, 102, 240, ${0.08 + glowIntensity * 0.12})`
      : '-2px 0 12px rgba(0, 0, 0, 0.10), inset 1px 0 0 rgba(255, 255, 255, 0.06)',
    p: tokens.spacing.xl,
    overflowY: 'auto' as const,
    transition: `box-shadow ${tokens.transitions.slow}`,
  };

  // Empty state (no album selected or no fingerprint)
  if (!fingerprint && !isLoading) {
    return (
      <Box
        sx={{
          ...containerStyles,
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
      <Box sx={containerStyles}>
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
    <Box sx={containerStyles}>
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

      {/* Waveform visualization with breathing - uses isAnimating for continued animation during decay */}
      <WaveformVisualization
        fingerprint={fingerprint}
        isAnimating={isAnimating}
        intensity={intensity}
      />

      {/* Character tags with subtle glow - glow lingers during decay */}
      <CharacterTags
        tags={character.tags}
        isAnimating={isAnimating}
        intensity={intensity}
      />

      {/* Energy field (gradient, not slider) - glow and drift fade with intensity */}
      <EnergyField
        energy={character.energyLevel}
        isAnimating={isAnimating}
        intensity={intensity}
      />

      {/* Rotating description */}
      <Box sx={{ mt: tokens.spacing.xl }}>
        <RotatingDescription
          descriptions={character.rotatingDescriptions}
          staticDescription={character.description}
          isPlaying={isPlaying}
        />
      </Box>

      {/* Mood discovery prompt - opacity fades with intensity during decay */}
      <Box
        sx={{
          mt: tokens.spacing.xxl,
          pt: tokens.spacing.lg,
          borderTop: `1px solid ${tokens.colors.border.light}`,
          opacity: 0.7 + intensity * 0.2,
          transition: `opacity ${tokens.transitions.slow}`,
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
