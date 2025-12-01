/**
 * Player - Phase 5 Orchestration Component
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Master player component that integrates all 6 Phase 4 UI components
 * (TimeDisplay, BufferingIndicator, ProgressBar, PlaybackControls, VolumeControl, TrackDisplay)
 * with the 3 core hooks (usePlayerStreaming, usePlayerControls, usePlayerDisplay).
 *
 * This is a thin orchestration layer that:
 * - Wires hook data to component props
 * - Handles audio element reference
 * - Coordinates streaming, controls, and display
 * - Provides responsive layout
 *
 * @component
 * @example
 * ```tsx
 * <Player />
 * ```
 */

import React, { useRef, useEffect, useMemo } from 'react';
import { tokens } from '@/design-system';

// Phase 4 UI Components
import TimeDisplay from './TimeDisplay';
import BufferingIndicator from './BufferingIndicator';
import ProgressBar from './ProgressBar';
import PlaybackControls from './PlaybackControls';
import VolumeControl from './VolumeControl';
import TrackDisplay from './TrackDisplay';

// Core Phase 3 Hooks
import { usePlayerStreaming, PlayerStreamingState } from '@/hooks/usePlayerStreaming';
import { usePlayerControls, PlayerControls } from '@/hooks/usePlayerControls';
import { usePlayerDisplay, PlayerDisplayInfo } from '@/hooks/usePlayerDisplay';

// Existing hooks for track info
import { useCurrentTrack } from '@/hooks/player/usePlaybackState';
import { useSelector } from 'react-redux';

/**
 * Player Component
 *
 * Full-featured music player with streaming synchronization,
 * playback controls, volume control, progress tracking, and time display.
 *
 * Architecture:
 * - Layer 1: Hooks (usePlayerStreaming, usePlayerControls, usePlayerDisplay)
 * - Layer 2: 6 UI Components (props-based, no internal state)
 * - Layer 3: Responsive layout with design tokens
 */
const Player: React.FC = () => {
  // Audio element reference for streaming synchronization
  const audioElementRef = useRef<HTMLAudioElement | null>(null);

  // Redux state for current playback info
  const currentTrack = useCurrentTrack();
  const state = useSelector((state: any) => state.player || {});

  // Phase 3 Hook: Core streaming synchronization
  // Handles timing, buffering, position tracking, and WebSocket sync
  const streaming = usePlayerStreaming({
    audioElement: audioElementRef.current,
    syncInterval: 5000,
    driftThreshold: 500,
    updateInterval: 100,
  });

  // Phase 3 Hook: Control operations
  // Provides play, pause, seek, volume, next, previous callbacks
  const controls = usePlayerControls({
    onPlay: async () => {
      if (audioElementRef.current) {
        audioElementRef.current.play();
      }
    },
    onPause: async () => {
      if (audioElementRef.current) {
        audioElementRef.current.pause();
      }
    },
    onSeek: async (position: number) => {
      if (audioElementRef.current) {
        audioElementRef.current.currentTime = position;
      }
    },
    onSetVolume: async (volume: number) => {
      if (audioElementRef.current) {
        audioElementRef.current.volume = volume / 100;
      }
    },
  });

  // Phase 3 Hook: Display formatting
  // Converts raw streaming data to formatted display strings
  const display = usePlayerDisplay({
    currentTime: streaming.currentTime,
    duration: streaming.duration,
    isPlaying: streaming.isPlaying,
    bufferedPercentage: streaming.bufferedPercentage,
  });

  // Set audio element reference when HiddenAudioElement is available
  useEffect(() => {
    const audioElement = document.querySelector('audio') as HTMLAudioElement;
    if (audioElement) {
      audioElementRef.current = audioElement;
    }
  }, []);

  // Extract volume from state or audio element (0-1 range, convert to 0-100 for components)
  const volume = useMemo(() => {
    if (audioElementRef.current) {
      return audioElementRef.current.volume * 100;
    }
    return state.volume ?? 50;
  }, [state.volume, streaming.isPlaying]);

  // Muted state - check if volume is 0 or explicitly muted
  const isMuted = useMemo(() => {
    return volume === 0 || state.isMuted === true;
  }, [volume, state.isMuted]);

  return (
    <div
      data-testid="player"
      style={styles.player}
    >
      {/* Top Section: Track Display + Time */}
      <div style={styles.topSection}>
        <div style={styles.trackAndTimeContainer}>
          {/* Track Information (Title, Artist, Album) */}
          <TrackDisplay
            title={currentTrack?.title ?? 'No track playing'}
            artist={currentTrack?.artist}
            album={currentTrack?.album}
            isLoading={streaming.isBuffering}
            className="player-track-display"
          />

          {/* Current Time Display */}
          <TimeDisplay
            currentTime={streaming.currentTime}
            duration={streaming.duration}
            isLive={display.isLiveContent}
          />
        </div>
      </div>

      {/* Middle Section: Progress Bar with Buffering Indicator */}
      <div style={styles.progressSection}>
        {/* Buffering Indicator Overlay */}
        <BufferingIndicator
          isBuffering={streaming.isBuffering}
          bufferedPercentage={streaming.bufferedPercentage}
        />

        {/* Seekable Progress Bar */}
        <ProgressBar
          currentTime={streaming.currentTime}
          duration={streaming.duration}
          bufferedPercentage={streaming.bufferedPercentage}
          onSeek={async (position) => {
            await controls.seek(position);
          }}
          disabled={streaming.isError}
        />
      </div>

      {/* Bottom Section: Controls + Volume */}
      <div style={styles.controlsSection}>
        {/* Playback Controls (Play, Pause, Next, Previous) */}
        <PlaybackControls
          isPlaying={streaming.isPlaying}
          onPlay={controls.play}
          onPause={controls.pause}
          onNext={controls.nextTrack}
          onPrevious={controls.previousTrack}
          isLoading={controls.isLoading || streaming.isBuffering}
          disabled={streaming.isError}
        />

        {/* Volume Control (Slider + Mute Button) */}
        <VolumeControl
          volume={volume / 100}
          onVolumeChange={async (vol) => {
            await controls.setVolume(vol * 100);
          }}
          isMuted={isMuted}
          onMuteToggle={async () => {
            const newVolume = isMuted ? 50 : 0;
            await controls.setVolume(newVolume);
          }}
          disabled={streaming.isError}
        />
      </div>

      {/* Error State Indicator */}
      {streaming.isError && (
        <div style={styles.errorBanner}>
          <span style={styles.errorText}>
            {streaming.errorMessage || 'Playback error occurred'}
          </span>
        </div>
      )}
    </div>
  );
};

/**
 * Component styles using design tokens
 *
 * Layout:
 * - Top: Track display + current time
 * - Middle: Progress bar with buffering
 * - Bottom: Playback controls + volume
 *
 * Responsive breakpoints:
 * - Desktop (1024px+): Full width side-by-side
 * - Tablet (768-1024px): Stacked, adjusted spacing
 * - Mobile (<768px): Compact, minimal spacing
 */
const styles = {
  player: {
    display: 'flex',
    flexDirection: 'column' as const,
    width: '100%',
    backgroundColor: tokens.colors.bg.primary,
    borderTop: `1px solid ${tokens.colors.border.default}`,
    boxShadow: tokens.shadows.lg,
    zIndex: 1000,
    padding: tokens.spacing.md,
    gap: tokens.spacing.md,

    // Mobile: Compact
    '@media (max-width: 480px)': {
      padding: tokens.spacing.sm,
      gap: tokens.spacing.sm,
    },

    // Tablet
    '@media (max-width: 768px)': {
      padding: tokens.spacing.md,
      gap: tokens.spacing.sm,
    },
  },

  topSection: {
    display: 'flex',
    flexDirection: 'column' as const,
    gap: tokens.spacing.md,

    '@media (max-width: 768px)': {
      gap: tokens.spacing.sm,
    },
  },

  trackAndTimeContainer: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    gap: tokens.spacing.md,

    '@media (max-width: 768px)': {
      flexDirection: 'column' as const,
      alignItems: 'stretch',
      gap: tokens.spacing.sm,
    },
  },

  progressSection: {
    display: 'flex',
    flexDirection: 'column' as const,
    gap: tokens.spacing.sm,
    position: 'relative' as const,
  },

  controlsSection: {
    display: 'flex',
    flexDirection: 'column' as const,
    gap: tokens.spacing.md,
    alignItems: 'stretch',

    '@media (max-width: 768px)': {
      gap: tokens.spacing.sm,
    },
  },

  errorBanner: {
    display: 'flex',
    alignItems: 'center',
    padding: tokens.spacing.md,
    backgroundColor: tokens.colors.accent.error || '#ff4444',
    borderRadius: tokens.borderRadius.md,
    marginTop: tokens.spacing.sm,
  },

  errorText: {
    color: tokens.colors.text.primary,
    fontSize: tokens.typography.fontSize.sm,
    fontWeight: 'bold',
  },
};

export default Player;
