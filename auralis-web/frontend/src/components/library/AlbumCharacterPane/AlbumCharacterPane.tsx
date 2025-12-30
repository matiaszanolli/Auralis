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

import React, { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { Box, Typography, Chip, LinearProgress, keyframes } from '@mui/material';
import { useSelector } from 'react-redux';
import { tokens } from '@/design-system';
import type { AudioFingerprint } from '@/utils/fingerprintToGradient';
import { computeAlbumCharacter } from '@/utils/albumCharacterDescriptors';
import { EnhancementToggle } from '@/components/shared/EnhancementToggle';
import { playerSelectors } from '@/store/selectors';
import { useTrackFingerprint } from '@/hooks/fingerprint';

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
  /** Album fingerprint (median of all tracks) - used when hovering over albums */
  fingerprint?: AudioFingerprint | null;
  /** Album title - shown when hovering over albums */
  albumTitle?: string;
  /** Loading state for hovered album */
  isLoading?: boolean;
  /** Enhancement enabled state */
  isEnhancementEnabled?: boolean;
  /** Enhancement toggle callback */
  onEnhancementToggle?: (enabled: boolean) => void;
  /**
   * When true, fetches and displays the currently playing track's fingerprint.
   * Takes priority over hovered album fingerprint.
   * @default true
   */
  showPlayingTrack?: boolean;
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
    box-shadow: 0 0 8px 2px rgba(115, 102, 240, 0.15);
  }
  50% {
    box-shadow: 0 0 16px 4px rgba(115, 102, 240, 0.35);
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

// Floating particles animation
const particleFloat = keyframes`
  0% {
    transform: translateY(100%) translateX(0) scale(0);
    opacity: 0;
  }
  10% {
    opacity: 1;
    transform: translateY(80%) translateX(5px) scale(1);
  }
  50% {
    opacity: 0.8;
    transform: translateY(40%) translateX(-5px) scale(0.8);
  }
  90% {
    opacity: 0.3;
    transform: translateY(10%) translateX(3px) scale(0.5);
  }
  100% {
    transform: translateY(0%) translateX(0) scale(0);
    opacity: 0;
  }
`;

// Glowing arc pulse animation
const arcPulse = keyframes`
  0%, 100% {
    opacity: 0.6;
    filter: blur(8px);
  }
  50% {
    opacity: 1;
    filter: blur(4px);
  }
`;

// Waveform bar glow animation
const barGlow = keyframes`
  0%, 100% {
    filter: drop-shadow(0 0 4px rgba(115, 102, 240, 0.4));
  }
  50% {
    filter: drop-shadow(0 0 12px rgba(115, 102, 240, 0.8));
  }
`;

// ============================================================================
// Floating Particles Component (Ethereal sparkles inside panel)
// ============================================================================

interface FloatingParticlesProps {
  isAnimating: boolean;
  intensity: number;
  count?: number;
}

const FloatingParticles: React.FC<FloatingParticlesProps> = ({
  isAnimating,
  intensity,
  count = 12,
}) => {
  // Generate particles with varied properties
  const particles = React.useMemo(() =>
    Array.from({ length: count }, (_, i) => ({
      id: i,
      left: 10 + (i * 7) % 80, // Spread across width
      size: 2 + (i % 3) * 1.5, // Varied sizes (2-5px)
      duration: 6 + (i % 4) * 2, // 6-12s float duration
      delay: (i * 0.8) % 5, // Staggered starts
      hue: 240 + (i % 5) * 15, // Violet to cyan spectrum
    })),
  [count]);

  if (!isAnimating && intensity < 0.1) return null;

  return (
    <Box
      sx={{
        position: 'absolute',
        inset: 0,
        overflow: 'hidden',
        pointerEvents: 'none',
        opacity: intensity,
        transition: `opacity ${tokens.transitions.slow}`,
      }}
    >
      {particles.map((p) => (
        <Box
          key={p.id}
          sx={{
            position: 'absolute',
            left: `${p.left}%`,
            bottom: 0,
            width: `${p.size}px`,
            height: `${p.size}px`,
            borderRadius: '50%',
            background: `hsla(${p.hue}, 80%, 70%, 0.9)`,
            boxShadow: `0 0 ${p.size * 2}px hsla(${p.hue}, 80%, 60%, 0.6)`,
            animation: isAnimating
              ? `${particleFloat} ${p.duration}s ease-in-out infinite`
              : 'none',
            animationDelay: `${p.delay}s`,
          }}
        />
      ))}
    </Box>
  );
};

// ============================================================================
// Glowing Arc Component (Cyan-Purple energy visualization)
// ============================================================================

interface GlowingArcProps {
  isAnimating: boolean;
  intensity: number;
  energyLevel: number;
}

const GlowingArc: React.FC<GlowingArcProps> = ({ isAnimating, intensity, energyLevel }) => {
  const glowIntensity = Math.sqrt(intensity);

  // Arc spans based on energy level (more energy = wider arc)
  const arcDegrees = 120 + energyLevel * 60; // 120-180 degrees
  const startAngle = (180 - arcDegrees) / 2;

  return (
    <Box
      sx={{
        position: 'relative',
        width: '100%',
        height: '100px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        my: tokens.spacing.lg,
      }}
    >
      {/* Outer glow arc */}
      <Box
        sx={{
          position: 'absolute',
          width: '200px',
          height: '100px',
          borderRadius: '100px 100px 0 0',
          background: `conic-gradient(
            from ${startAngle}deg at 50% 100%,
            transparent 0deg,
            rgba(115, 102, 240, ${0.1 + glowIntensity * 0.3}) ${arcDegrees * 0.3}deg,
            rgba(0, 200, 220, ${0.2 + glowIntensity * 0.4}) ${arcDegrees * 0.5}deg,
            rgba(115, 102, 240, ${0.1 + glowIntensity * 0.3}) ${arcDegrees * 0.7}deg,
            transparent ${arcDegrees}deg
          )`,
          filter: `blur(${12 - glowIntensity * 4}px)`,
          opacity: 0.4 + glowIntensity * 0.4,
          animation: isAnimating
            ? `${arcPulse} 4s ease-in-out infinite`
            : 'none',
          transition: `all ${tokens.transitions.slow}`,
        }}
      />

      {/* Inner bright arc */}
      <Box
        sx={{
          position: 'absolute',
          width: '160px',
          height: '80px',
          borderRadius: '80px 80px 0 0',
          background: `conic-gradient(
            from ${startAngle + 10}deg at 50% 100%,
            transparent 0deg,
            rgba(180, 130, 255, ${0.3 + glowIntensity * 0.4}) ${arcDegrees * 0.4}deg,
            rgba(80, 220, 240, ${0.4 + glowIntensity * 0.5}) ${arcDegrees * 0.5}deg,
            rgba(180, 130, 255, ${0.3 + glowIntensity * 0.4}) ${arcDegrees * 0.6}deg,
            transparent ${arcDegrees - 20}deg
          )`,
          filter: `blur(${6 - glowIntensity * 2}px)`,
          opacity: 0.6 + glowIntensity * 0.3,
          animation: isAnimating
            ? `${arcPulse} 3s ease-in-out infinite 0.5s`
            : 'none',
          transition: `all ${tokens.transitions.slow}`,
        }}
      />

      {/* Center energy indicator */}
      <Box
        sx={{
          position: 'absolute',
          bottom: '0',
          width: '8px',
          height: '8px',
          borderRadius: '50%',
          background: `linear-gradient(135deg, rgba(115, 102, 240, 1), rgba(0, 200, 220, 1))`,
          boxShadow: `0 0 ${12 + glowIntensity * 8}px rgba(115, 102, 240, ${0.5 + glowIntensity * 0.3})`,
          transition: `all ${tokens.transitions.slow}`,
        }}
      />

      {/* "SPACE" label */}
      <Typography
        sx={{
          position: 'absolute',
          bottom: '-20px',
          fontSize: tokens.typography.fontSize.xs,
          fontWeight: tokens.typography.fontWeight.medium,
          color: tokens.colors.text.tertiary,
          letterSpacing: '0.15em',
          textTransform: 'uppercase',
          opacity: 0.6 + intensity * 0.3,
          transition: `opacity ${tokens.transitions.slow}`,
        }}
      >
        SPACE
      </Typography>
    </Box>
  );
};

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
  const glowIntensity = Math.sqrt(intensity);

  return (
    <Box
      sx={{
        position: 'relative',
        display: 'flex',
        alignItems: 'flex-end',
        justifyContent: 'space-around',
        height: '100px',
        gap: '6px',
        mt: tokens.spacing.xl,
        mb: tokens.spacing.lg,
        px: tokens.spacing.md,
        // Subtle backdrop glow behind waveform
        '&::before': {
          content: '""',
          position: 'absolute',
          inset: '-10px',
          background: `radial-gradient(ellipse at 50% 100%, rgba(115, 102, 240, ${0.08 + glowIntensity * 0.12}) 0%, transparent 70%)`,
          filter: 'blur(8px)',
          opacity: isAnimating ? 1 : 0.5,
          transition: `opacity ${tokens.transitions.slow}`,
          pointerEvents: 'none',
        },
      }}
    >
      {normalizedBands.map((value, index) => {
        // Hue shifts from violet (left/bass) to cyan (right/air)
        const hue = 260 - index * 8; // 260 (violet) to 204 (cyan)
        const barHeight = Math.max(value * 100, 12);

        return (
          <Box
            key={index}
            sx={{
              position: 'relative',
              flex: 1,
              height: `${barHeight}%`,
              minHeight: '12px',
              borderRadius: '4px',
              // Vibrant gradient with hue shift
              background: `linear-gradient(to top,
                hsla(${hue}, 70%, 50%, 0.9) 0%,
                hsla(${hue - 20}, 80%, 65%, 0.95) 50%,
                hsla(${hue - 40}, 90%, 75%, 1) 100%)`,
              // Glow effect intensifies with playback
              boxShadow: `
                0 0 ${4 + glowIntensity * 8}px hsla(${hue}, 80%, 55%, ${0.3 + glowIntensity * 0.4}),
                inset 0 1px 0 rgba(255, 255, 255, 0.3)`,
              opacity: 0.7 + value * 0.2 + intensity * 0.1,
              transition: `all ${tokens.transitions.slow}`,
              // Breathing + glow animation when animating
              animation: isAnimating
                ? `${breathePulse} ${2.5 + index * 0.3}s cubic-bezier(0.25, 0.46, 0.45, 0.94) infinite,
                   ${barGlow} ${3 + index * 0.4}s ease-in-out infinite`
                : 'none',
              animationDelay: `${index * 0.15}s, ${index * 0.2}s`,
            }}
          />
        );
      })}
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
      {tags.map((tag, index) => {
        // Each tag gets a slightly different hue for variety
        const tagHue = 260 - (index * 12) % 60; // Violet to blue-cyan range

        return (
          <Chip
            key={index}
            label={tag.label}
            size="small"
            sx={{
              // Glass background
              background: `rgba(30, 40, 65, ${0.4 + glowIntensity * 0.15})`,
              backdropFilter: 'blur(4px)',
              color: tokens.colors.text.secondary,
              fontSize: tokens.typography.fontSize.xs,
              fontWeight: tokens.typography.fontWeight.medium,
              // Glass bevel instead of hard border
              border: 'none',
              transition: `all ${tokens.transitions.slow}`,
              // Multi-layer glow effect
              boxShadow: `
                inset 0 1px 0 rgba(255, 255, 255, ${0.08 + glowIntensity * 0.08}),
                inset 0 -1px 0 rgba(0, 0, 0, 0.15),
                ${glowIntensity > 0.1
                  ? `0 0 ${8 + glowIntensity * 10}px hsla(${tagHue}, 70%, 55%, ${0.15 + glowIntensity * 0.25})`
                  : '0 2px 4px rgba(0, 0, 0, 0.1)'}
              `,
              // Glow animation when animating
              animation: isAnimating
                ? `${subtleGlow} ${3 + index * 0.5}s cubic-bezier(0.25, 0.46, 0.45, 0.94) infinite`
                : 'none',
              animationDelay: `${index * 0.2}s`,
              '&:hover': {
                background: `rgba(40, 55, 85, ${0.5 + glowIntensity * 0.2})`,
                boxShadow: `
                  inset 0 1px 0 rgba(255, 255, 255, 0.12),
                  inset 0 -1px 0 rgba(0, 0, 0, 0.2),
                  0 0 16px hsla(${tagHue}, 70%, 55%, 0.35)
                `,
              },
            }}
          />
        );
      })}
    </Box>
  );
};

// ============================================================================
// Main Component
// ============================================================================

export const AlbumCharacterPane: React.FC<AlbumCharacterPaneProps> = ({
  fingerprint: albumFingerprint,
  albumTitle,
  isLoading: albumLoading = false,
  isEnhancementEnabled = true,
  onEnhancementToggle,
  showPlayingTrack = true,
}) => {
  // Get playback state from Redux
  const isPlayingRaw = useSelector(playerSelectors.selectIsPlaying);
  const currentTrack = useSelector(playerSelectors.selectCurrentTrack);

  // Fetch playing track's fingerprint when available
  const {
    fingerprint: playingTrackFingerprint,
    trackTitle: playingTrackTitle,
    artist: playingArtist,
    // album: playingAlbum, // Available if needed for album context
    isLoading: playingTrackLoading,
    isPending: fingerprintPending,
  } = useTrackFingerprint(
    showPlayingTrack && currentTrack?.id ? currentTrack.id : null
  );

  // Priority: Playing track > Hovered album > Empty state
  // When playing, show the track's fingerprint; when hovering, show album's
  const displayFingerprint = useMemo(() => {
    if (showPlayingTrack && currentTrack?.id && playingTrackFingerprint) {
      return playingTrackFingerprint;
    }
    return albumFingerprint ?? null;
  }, [showPlayingTrack, currentTrack?.id, playingTrackFingerprint, albumFingerprint]);

  const displayTitle = useMemo(() => {
    if (showPlayingTrack && currentTrack?.id) {
      if (playingTrackTitle) {
        return `${playingTrackTitle}${playingArtist ? ` • ${playingArtist}` : ''}`;
      }
      return currentTrack.title || 'Now Playing';
    }
    return albumTitle;
  }, [showPlayingTrack, currentTrack, playingTrackTitle, playingArtist, albumTitle]);

  // Only show loading during the initial fetch, NOT when fingerprint is pending generation
  // If fingerprint isn't available yet, we'll show "generating" state instead of infinite loading
  const isLoading = showPlayingTrack && currentTrack?.id
    ? playingTrackLoading  // Only true during initial fetch, not when pending
    : albumLoading;

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

  // Container styles matching sidebar (muscle memory UI - lower contrast)
  // Uses glowIntensity (0-1) for playback-aware edge glow
  const containerStyles = {
    position: 'relative' as const,
    width: tokens.components.rightPanel.width,
    height: '100%',
    minHeight: 0, // Allow flex shrinking
    alignSelf: 'stretch', // Match sidebar's flex behavior
    flexShrink: 0,
    // Match sidebar's subtle transparency
    background: tokens.components.rightPanel.background,
    backdropFilter: tokens.components.rightPanel.backdropFilter,
    border: 'none',
    // Base shadow from tokens + playback-aware edge glow
    boxShadow: glowIntensity > 0.05
      ? `${tokens.components.rightPanel.shadow}, inset 3px 0 16px -4px rgba(115, 102, 240, ${0.08 + glowIntensity * 0.12})`
      : tokens.components.rightPanel.shadow,
    p: tokens.spacing.lg,
    overflowY: 'auto' as const,
    overflowX: 'hidden' as const,
    transition: `all ${tokens.transitions.slow}`,
    display: 'flex',
    flexDirection: 'column' as const,
  };

  // State 1: No track playing and no album hovered
  if (!currentTrack?.id && !albumFingerprint && !isLoading) {
    return (
      <Box sx={containerStyles}>
        {/* Subtle floating particles even in empty state */}
        <FloatingParticles isAnimating={false} intensity={0.3} count={8} />
        <EnhancementSection />
        <Box
          sx={{
            flex: 1,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            position: 'relative',
            zIndex: 1,
          }}
        >
          <Typography
            variant="body2"
            sx={{
              color: tokens.colors.text.tertiary,
              textAlign: 'center',
              fontSize: tokens.typography.fontSize.sm,
              textShadow: '0 2px 8px rgba(0, 0, 0, 0.3)',
            }}
          >
            Play a track to see its sonic character
          </Typography>
        </Box>
      </Box>
    );
  }

  // State 2: Track playing but fingerprint is being generated (pending)
  if (currentTrack?.id && !displayFingerprint && fingerprintPending) {
    return (
      <Box sx={containerStyles}>
        {/* Animated particles during generation */}
        <FloatingParticles isAnimating={true} intensity={0.5} count={10} />
        <EnhancementSection />
        <Box
          sx={{
            flex: 1,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            position: 'relative',
            zIndex: 1,
            gap: tokens.spacing.md,
          }}
        >
          <Typography
            variant="body2"
            sx={{
              color: tokens.colors.text.secondary,
              textAlign: 'center',
              fontSize: tokens.typography.fontSize.sm,
              textShadow: '0 2px 8px rgba(0, 0, 0, 0.3)',
            }}
          >
            {displayTitle || 'Now Playing'}
          </Typography>
          <Typography
            variant="caption"
            sx={{
              color: tokens.colors.text.tertiary,
              textAlign: 'center',
              fontSize: tokens.typography.fontSize.xs,
              opacity: 0.8,
            }}
          >
            Generating audio fingerprint...
          </Typography>
          <Typography
            variant="caption"
            sx={{
              color: tokens.colors.text.tertiary,
              textAlign: 'center',
              fontSize: tokens.typography.fontSize.xs,
              opacity: 0.6,
              mt: tokens.spacing.sm,
            }}
          >
            Character will appear after analysis completes
          </Typography>
        </Box>
      </Box>
    );
  }

  // State 3: Loading state (initial fetch)
  if (isLoading) {
    return (
      <Box sx={containerStyles}>
        {/* Particles animate during loading */}
        <FloatingParticles isAnimating={true} intensity={0.6} count={10} />
        <Box sx={{ position: 'relative', zIndex: 1 }}>
          <EnhancementSection />
          <LinearProgress
            sx={{
              mb: tokens.spacing.lg,
              background: 'rgba(115, 102, 240, 0.15)',
              '& .MuiLinearProgress-bar': {
                background: 'linear-gradient(90deg, rgba(115, 102, 240, 0.8), rgba(0, 200, 220, 0.8))',
              },
            }}
          />
          <Typography
            variant="body2"
            sx={{
              color: tokens.colors.text.tertiary,
              textAlign: 'center',
              textShadow: '0 0 12px rgba(115, 102, 240, 0.3)',
            }}
          >
            {currentTrack?.id ? 'Analyzing track character...' : 'Analyzing album character...'}
          </Typography>
        </Box>
      </Box>
    );
  }

  // State 4: No fingerprint available (edge case - API error or unexpected state)
  if (!displayFingerprint) {
    return (
      <Box sx={containerStyles}>
        <FloatingParticles isAnimating={false} intensity={0.3} count={8} />
        <EnhancementSection />
        <Box
          sx={{
            flex: 1,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            position: 'relative',
            zIndex: 1,
          }}
        >
          <Typography
            variant="body2"
            sx={{
              color: tokens.colors.text.tertiary,
              textAlign: 'center',
              fontSize: tokens.typography.fontSize.sm,
              textShadow: '0 2px 8px rgba(0, 0, 0, 0.3)',
            }}
          >
            {currentTrack?.id
              ? 'Fingerprint not available for this track'
              : 'Play a track to see its sonic character'}
          </Typography>
        </Box>
      </Box>
    );
  }

  // Compute character from fingerprint
  const character = computeAlbumCharacter(displayFingerprint);

  return (
    <Box sx={containerStyles}>
      {/* Floating particles - ethereal sparkles inside the panel */}
      <FloatingParticles
        isAnimating={isAnimating}
        intensity={intensity}
        count={15}
      />

      {/* Enhancement Toggle */}
      <EnhancementSection />

      {/* Header with subtle glow */}
      <Box sx={{ mb: tokens.spacing.xl, position: 'relative', zIndex: 1 }}>
        <Typography
          variant="h6"
          sx={{
            fontSize: tokens.typography.fontSize.lg,
            fontWeight: tokens.typography.fontWeight.semibold,
            color: tokens.colors.text.primary,
            mb: tokens.spacing.xs,
            textShadow: glowIntensity > 0.1
              ? `0 0 ${8 + glowIntensity * 8}px rgba(115, 102, 240, ${0.2 + glowIntensity * 0.3})`
              : 'none',
            transition: `text-shadow ${tokens.transitions.slow}`,
          }}
        >
          {currentTrack?.id ? 'Track Character' : 'Album Character'}
        </Typography>
        {displayTitle && (
          <Typography
            variant="caption"
            sx={{
              color: tokens.colors.text.tertiary,
              fontSize: tokens.typography.fontSize.xs,
            }}
          >
            {displayTitle}
          </Typography>
        )}
      </Box>

      {/* Waveform visualization with dramatic glow effects */}
      <Box sx={{ position: 'relative', zIndex: 1 }}>
        <WaveformVisualization
          fingerprint={displayFingerprint}
          isAnimating={isAnimating}
          intensity={intensity}
        />
      </Box>

      {/* Glowing Arc - cyan-purple energy visualization */}
      <Box sx={{ position: 'relative', zIndex: 1 }}>
        <GlowingArc
          isAnimating={isAnimating}
          intensity={intensity}
          energyLevel={character.energyLevel}
        />
      </Box>

      {/* Character tags with enhanced glow - glow lingers during decay */}
      <Box sx={{ position: 'relative', zIndex: 1 }}>
        <CharacterTags
          tags={character.tags}
          isAnimating={isAnimating}
          intensity={intensity}
        />
      </Box>

      {/* Energy field (gradient, not slider) - glow and drift fade with intensity */}
      <Box sx={{ position: 'relative', zIndex: 1 }}>
        <EnergyField
          energy={character.energyLevel}
          isAnimating={isAnimating}
          intensity={intensity}
        />
      </Box>

      {/* Rotating description */}
      <Box sx={{ mt: tokens.spacing.xl, position: 'relative', zIndex: 1 }}>
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
          position: 'relative',
          zIndex: 1,
          // Glass bevel separator instead of hard border
          boxShadow: 'inset 0 1px 0 rgba(255, 255, 255, 0.04)',
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
