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

import React, { useRef, useEffect, useMemo, useState } from 'react';
import { tokens } from '@/design-system';

// Phase 4 UI Components
import TimeDisplay from './TimeDisplay';
import BufferingIndicator from './BufferingIndicator';
import ProgressBar from './ProgressBar';
import PlaybackControls from './PlaybackControls';
import VolumeControl from './VolumeControl';
import TrackDisplay from './TrackDisplay';

// Phase 6 Queue Component
import QueuePanel from './QueuePanel';

// Core Phase 3 Hooks
import { usePlayerStreaming, PlayerStreamingState } from '@/hooks/usePlayerStreaming';
import { usePlayerControls, PlayerControls } from '@/hooks/usePlayerControls';
import { usePlayerDisplay, PlayerDisplayInfo } from '@/hooks/usePlayerDisplay';

// Existing hooks for track info
import { useCurrentTrack } from '@/hooks/player/usePlaybackState';
import { usePlayerAPI } from '@/hooks/usePlayerAPI';
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

  // Queue panel visibility state
  const [queuePanelOpen, setQueuePanelOpen] = useState(false);

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

  // Get backend player API for play/pause/next/previous
  const playerAPI = usePlayerAPI();

  // Phase 3 Hook: Control operations
  // Provides play, pause, seek, volume, next, previous callbacks
  const controls = usePlayerControls({
    onPlay: async () => {
      // CRITICAL: Ensure audio element is ready before playing
      // This prevents race condition where play() called before src is set
      if (audioElementRef.current) {
        // Step 1: Ensure audio element has a src
        if (!audioElementRef.current.src) {
          console.warn('[Player] Audio element has no src set, waiting for HiddenAudioElement...');
          // Wait up to 2 seconds for HiddenAudioElement to set src
          let waited = 0;
          while (!audioElementRef.current.src && waited < 2000) {
            await new Promise(resolve => setTimeout(resolve, 100));
            waited += 100;
          }
          if (!audioElementRef.current.src) {
            console.error('[Player] Audio src not set after 2s, cannot play');
            return;
          }
        }

        // Step 2: Wait for audio to be ready (canplay event)
        // Only wait if not already ready or loading
        if (
          audioElementRef.current.readyState < 2 && // HAVE_CURRENT_DATA = 2
          audioElementRef.current.networkState === 2 // LOADING
        ) {
          console.log('[Player] Waiting for audio to be ready (canplay)...');
          await new Promise<void>((resolve) => {
            const handler = () => {
              audioElementRef.current?.removeEventListener('canplay', handler);
              resolve();
            };
            audioElementRef.current?.addEventListener('canplay', handler);
            // Timeout after 5 seconds
            setTimeout(() => {
              audioElementRef.current?.removeEventListener('canplay', handler);
              resolve();
            }, 5000);
          });
        }
      }

      // Step 3: Tell backend to play (this broadcasts state to all clients)
      await playerAPI.play();

      // Step 4: Play the HTML5 audio element
      if (audioElementRef.current) {
        try {
          await audioElementRef.current.play();
        } catch (err) {
          console.warn('[Player] Audio element play failed:', err);
        }
      }
    },
    onPause: async () => {
      // Sync with backend player state
      await playerAPI.pause();
      // Also pause the HTML5 audio element
      if (audioElementRef.current) {
        audioElementRef.current.pause();
      }
    },
    onSeek: async (position: number) => {
      // Sync with backend player state
      await playerAPI.seek(position);
      // Also seek the HTML5 audio element
      if (audioElementRef.current) {
        audioElementRef.current.currentTime = position;
      }
    },
    onSetVolume: async (volume: number) => {
      // Sync with backend player state
      await playerAPI.setVolume(volume);
      // Also set HTML5 audio element volume
      if (audioElementRef.current) {
        audioElementRef.current.volume = volume / 100;
      }
    },
    onNextTrack: async () => {
      await playerAPI.next();
    },
    onPreviousTrack: async () => {
      await playerAPI.previous();
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

      {/* Bottom Section: Controls + Volume + Queue Button */}
      <div style={styles.controlsSection}>
        <div style={styles.controlsRow}>
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

          {/* Queue Button */}
          <button
            onClick={() => setQueuePanelOpen(!queuePanelOpen)}
            style={{
              ...styles.queueButton,
              backgroundColor: queuePanelOpen ? tokens.colors.accent.primary : 'transparent',
              color: queuePanelOpen ? tokens.colors.text.primary : tokens.colors.text.secondary,
            }}
            title="Toggle queue panel"
            aria-label="Toggle queue panel"
          >
            ♪ Queue
          </button>
        </div>

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

      {/* Queue Panel - Expands when opened */}
      {queuePanelOpen && (
        <div style={styles.queuePanelWrapper}>
          <QueuePanel
            collapsed={false}
            onToggleCollapse={() => setQueuePanelOpen(false)}
          />
        </div>
      )}

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

  controlsRow: {
    display: 'flex',
    gap: tokens.spacing.md,
    alignItems: 'center',
    justifyContent: 'space-between',

    '@media (max-width: 768px)': {
      gap: tokens.spacing.sm,
    },
  },

  queueButton: {
    padding: `${tokens.spacing.sm} ${tokens.spacing.md}`,
    border: `1px solid ${tokens.colors.border.default}`,
    borderRadius: tokens.borderRadius.md,
    cursor: 'pointer',
    fontSize: tokens.typography.fontSize.sm,
    fontWeight: 500,
    transition: 'all 0.2s ease-in-out',
    whiteSpace: 'nowrap' as const,

    '&:hover': {
      borderColor: tokens.colors.accent.primary,
      transform: 'scale(1.02)',
    },
  },

  queuePanelWrapper: {
    borderTop: `1px solid ${tokens.colors.border.default}`,
    paddingTop: tokens.spacing.md,
    marginTop: tokens.spacing.md,
    maxHeight: '400px',
    overflowY: 'auto' as const,
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
