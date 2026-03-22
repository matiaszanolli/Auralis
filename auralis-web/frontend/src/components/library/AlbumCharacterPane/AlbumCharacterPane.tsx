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
 * - CALM <-> AGGRESSIVE energy field (gradient, not slider)
 * - Rotating textual descriptions during playback
 * - Playback-aware visual states (alive when playing)
 *
 * Design Philosophy:
 * - Browsing context = Emotional, not analytical
 * - Album-level aggregate, not track-level parameters
 * - Living visualization, not static display
 * - Style Guide 6.1: Slow, weighted motion
 */

import { useCallback, useMemo } from 'react';
import { Box, Typography } from '@mui/material';
import { useSelector } from 'react-redux';
import { tokens } from '@/design-system';
import type { AudioFingerprint } from '@/utils/fingerprintToGradient';
import { computeAlbumCharacter } from '@/utils/albumCharacterDescriptors';
import { EnhancementToggle } from '@/components/shared/EnhancementToggle';
import { useEnhancementControl } from '@/hooks/enhancement/useEnhancementControl';
import { playerSelectors } from '@/store/selectors';
import { useTrackFingerprint } from '@/hooks/fingerprint';

import { usePlaybackWithDecay } from './usePlaybackWithDecay';
export { usePlaybackWithDecay } from './usePlaybackWithDecay';
export type { PlaybackDecayState } from './usePlaybackWithDecay';
import { FloatingParticles } from './FloatingParticles';
import { WaveformVisualization } from './WaveformVisualization';
import { GlowingArc } from './GlowingArc';
import { CharacterTags } from './CharacterTags';
import { EnergyField } from './EnergyField';
import { RotatingDescription } from './RotatingDescription';
import {
  EmptyStatePane,
  PendingStatePane,
  LoadingStatePane,
  NoFingerprintPane,
} from './PanePlaceholders';

export interface AlbumCharacterPaneProps {
  /** Album fingerprint (median of all tracks) - used when hovering over albums */
  fingerprint?: AudioFingerprint | null;
  /** Album title - shown when hovering over albums */
  albumTitle?: string;
  /** Loading state for hovered album */
  isLoading?: boolean;
  /**
   * When true, fetches and displays the currently playing track's fingerprint.
   * Takes priority over hovered album fingerprint.
   * @default true
   */
  showPlayingTrack?: boolean;
}

export const AlbumCharacterPane = ({
  fingerprint: albumFingerprint,
  albumTitle,
  isLoading: albumLoading = false,
  showPlayingTrack = true,
}: AlbumCharacterPaneProps) => {
  // Enhancement state from unified hook (eliminates prop drilling, fixes #2765)
  const { enabled: isEnhancementEnabled, setEnabled: onEnhancementToggle } = useEnhancementControl();

  // Get playback state from Redux
  const isPlayingRaw = useSelector(playerSelectors.selectIsPlaying);
  const currentTrack = useSelector(playerSelectors.selectCurrentTrack);

  // Fetch playing track's fingerprint when available
  const {
    fingerprint: playingTrackFingerprint,
    trackTitle: playingTrackTitle,
    artist: playingArtist,
    isLoading: playingTrackLoading,
    isPending: fingerprintPending,
  } = useTrackFingerprint(
    showPlayingTrack && currentTrack?.id ? currentTrack.id : null
  );

  // Priority: Playing track > Hovered album > Empty state
  const displayFingerprint = useMemo(() => {
    if (showPlayingTrack && currentTrack?.id && playingTrackFingerprint) {
      return playingTrackFingerprint;
    }
    return albumFingerprint ?? null;
  }, [showPlayingTrack, currentTrack?.id, playingTrackFingerprint, albumFingerprint]);

  const displayTitle = useMemo(() => {
    if (showPlayingTrack && currentTrack?.id) {
      if (playingTrackTitle) {
        return `${playingTrackTitle}${playingArtist ? ` \u2022 ${playingArtist}` : ''}`;
      }
      return currentTrack.title || 'Now Playing';
    }
    return albumTitle;
  }, [showPlayingTrack, currentTrack, playingTrackTitle, playingArtist, albumTitle]);

  // Only show loading during the initial fetch, NOT when fingerprint is pending generation
  const isLoading = showPlayingTrack && currentTrack?.id
    ? playingTrackLoading
    : albumLoading;

  // Apply silence decay - motion fades gracefully over 2.5s when playback stops
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
  const containerStyles = {
    position: 'relative' as const,
    width: tokens.components.rightPanel.width,
    height: '100%',
    minHeight: 0,
    alignSelf: 'stretch',
    flexShrink: 0,
    background: tokens.components.rightPanel.background,
    backdropFilter: tokens.components.rightPanel.backdropFilter,
    border: 'none',
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

  const enhancementSection = <EnhancementSection />;

  // State 1: No track playing and no album hovered
  if (!currentTrack?.id && !albumFingerprint && !isLoading) {
    return <EmptyStatePane containerStyles={containerStyles} enhancementSection={enhancementSection} />;
  }

  // State 2: Track playing but fingerprint is being generated (pending)
  if (currentTrack?.id && !displayFingerprint && fingerprintPending) {
    return (
      <PendingStatePane
        containerStyles={containerStyles}
        enhancementSection={enhancementSection}
        displayTitle={displayTitle}
      />
    );
  }

  // State 3: Loading state (initial fetch)
  if (isLoading) {
    return (
      <LoadingStatePane
        containerStyles={containerStyles}
        enhancementSection={enhancementSection}
        isTrackPlaying={!!currentTrack?.id}
      />
    );
  }

  // State 4: No fingerprint available (edge case - API error or unexpected state)
  if (!displayFingerprint) {
    return (
      <NoFingerprintPane
        containerStyles={containerStyles}
        enhancementSection={enhancementSection}
        isTrackPlaying={!!currentTrack?.id}
      />
    );
  }

  // Compute character from fingerprint
  const character = computeAlbumCharacter(displayFingerprint);

  return (
    <Box sx={containerStyles}>
      <FloatingParticles isAnimating={isAnimating} intensity={intensity} count={15} />
      {enhancementSection}

      {/* Header with subtle glow */}
      <Box sx={{ mb: tokens.spacing.xl, position: 'relative', zIndex: tokens.zIndex.content }}>
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
            sx={{ color: tokens.colors.text.tertiary, fontSize: tokens.typography.fontSize.xs }}
          >
            {displayTitle}
          </Typography>
        )}
      </Box>

      <Box sx={{ position: 'relative', zIndex: tokens.zIndex.content }}>
        <WaveformVisualization fingerprint={displayFingerprint} isAnimating={isAnimating} intensity={intensity} />
      </Box>

      <Box sx={{ position: 'relative', zIndex: tokens.zIndex.content }}>
        <GlowingArc isAnimating={isAnimating} intensity={intensity} energyLevel={character.energyLevel} />
      </Box>

      <Box sx={{ position: 'relative', zIndex: tokens.zIndex.content }}>
        <CharacterTags tags={character.tags} isAnimating={isAnimating} intensity={intensity} />
      </Box>

      <Box sx={{ position: 'relative', zIndex: tokens.zIndex.content }}>
        <EnergyField energy={character.energyLevel} isAnimating={isAnimating} intensity={intensity} />
      </Box>

      <Box sx={{ mt: tokens.spacing.xl, position: 'relative', zIndex: tokens.zIndex.content }}>
        <RotatingDescription
          descriptions={character.rotatingDescriptions}
          staticDescription={character.description}
          isPlaying={isPlaying}
        />
      </Box>

      {/* Mood discovery prompt */}
      <Box
        sx={{
          mt: tokens.spacing.xxl,
          pt: tokens.spacing.lg,
          position: 'relative',
          zIndex: tokens.zIndex.content,
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
          Explore mood-based discovery...
        </Typography>
      </Box>
    </Box>
  );
};

export default AlbumCharacterPane;
