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

  // Direct API command functions (no state management here, Redux handles that)
  const apiPlay = async () => {
    try {
      await fetch('/api/player/play', { method: 'POST' });
    } catch (err) {
      console.error('[Player] Play command error:', err);
    }
  };

  const apiPause = async () => {
    try {
      await fetch('/api/player/pause', { method: 'POST' });
    } catch (err) {
      console.error('[Player] Pause command error:', err);
    }
  };

  const apiSeek = async (position: number) => {
    try {
      await fetch('/api/player/seek', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ position })
      });
    } catch (err) {
      console.error('[Player] Seek command error:', err);
    }
  };

  const apiSetVolume = async (volume: number) => {
    try {
      await fetch('/api/player/volume', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ volume })
      });
    } catch (err) {
      console.error('[Player] Volume command error:', err);
    }
  };

  const apiNext = async () => {
    try {
      await fetch('/api/player/next', { method: 'POST' });
    } catch (err) {
      console.error('[Player] Next command error:', err);
    }
  };

  const apiPrevious = async () => {
    try {
      await fetch('/api/player/previous', { method: 'POST' });
    } catch (err) {
      console.error('[Player] Previous command error:', err);
    }
  };

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
      await apiPlay();

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
      // Call backend API (Redux state will sync via WebSocket)
      await apiPause();
      // Also pause the HTML5 audio element
      if (audioElementRef.current) {
        audioElementRef.current.pause();
      }
    },
    onSeek: async (position: number) => {
      // Call backend API (Redux state will sync via WebSocket)
      await apiSeek(position);
      // Also seek the HTML5 audio element
      if (audioElementRef.current) {
        audioElementRef.current.currentTime = position;
      }
    },
    onSetVolume: async (volume: number) => {
      // Call backend API (Redux state will sync via WebSocket)
      await apiSetVolume(volume);
      // Also set HTML5 audio element volume
      if (audioElementRef.current) {
        audioElementRef.current.volume = volume / 100;
      }
    },
    onNextTrack: async () => {
      await apiNext();
    },
    onPreviousTrack: async () => {
      await apiPrevious();
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
      {/* Progress Bar - Full width at top */}
      <div style={styles.progressBarContainer}>
        <BufferingIndicator
          isBuffering={streaming.isBuffering}
          bufferedPercentage={streaming.bufferedPercentage}
        />
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

      {/* Main compact player row */}
      <div style={styles.mainRow}>
        {/* Left: Track info + time */}
        <div style={styles.trackInfoSection}>
          <TrackDisplay
            title={currentTrack?.title ?? 'No track'}
            artist={currentTrack?.artist}
            album={currentTrack?.album}
            isLoading={streaming.isBuffering}
            className="player-track-display"
          />
          <TimeDisplay
            currentTime={streaming.currentTime}
            duration={streaming.duration}
            isLive={display.isLiveContent}
          />
        </div>

        {/* Center: Playback Controls */}
        <PlaybackControls
          isPlaying={streaming.isPlaying}
          onPlay={controls.play}
          onPause={controls.pause}
          onNext={controls.nextTrack}
          onPrevious={controls.previousTrack}
          isLoading={controls.isLoading || streaming.isBuffering}
          disabled={streaming.isError}
        />

        {/* Right: Volume + Queue */}
        <div style={styles.rightSection}>
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

          {/* Queue Button - Compact */}
          <button
            onClick={() => setQueuePanelOpen(!queuePanelOpen)}
            style={{
              ...styles.queueButton,
              backgroundColor: queuePanelOpen ? tokens.colors.accent.primary : 'transparent',
              color: tokens.colors.text.primary,
              borderColor: queuePanelOpen ? tokens.colors.accent.primary : tokens.colors.border.medium,
            }}
            title="Toggle queue (Q)"
            aria-label="Toggle queue"
            onMouseEnter={(e) => {
              e.currentTarget.style.borderColor = tokens.colors.accent.primary;
              if (!queuePanelOpen) {
                e.currentTarget.style.backgroundColor = tokens.colors.bg.secondary;
              }
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.borderColor = tokens.colors.border.medium;
              if (!queuePanelOpen) {
                e.currentTarget.style.backgroundColor = 'transparent';
              }
            }}
          >
            ♪
          </button>
        </div>
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
    borderTop: `1px solid ${tokens.colors.border.medium}`,
    boxShadow: tokens.shadows.sm,
    zIndex: 1000,
    padding: 0,
    gap: 0,
  },

  progressBarContainer: {
    width: '100%',
    height: 'auto',
    padding: `${tokens.spacing.sm} ${tokens.spacing.lg}`,
    paddingBottom: tokens.spacing.xs,
  },

  mainRow: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: tokens.spacing.lg,
    padding: `${tokens.spacing.md} ${tokens.spacing.lg}`,
    minHeight: '64px',

    '@media (max-width: 768px)': {
      flexDirection: 'column' as const,
      alignItems: 'stretch',
      padding: tokens.spacing.md,
      minHeight: 'auto',
      gap: tokens.spacing.md,
    },
  },

  trackInfoSection: {
    display: 'flex',
    alignItems: 'center',
    gap: tokens.spacing.md,
    minWidth: '200px',
    flex: '1 1 auto',

    '@media (max-width: 768px)': {
      minWidth: 'auto',
      width: '100%',
    },
  },

  rightSection: {
    display: 'flex',
    alignItems: 'center',
    gap: tokens.spacing.md,
    flex: '1 1 auto',
    justifyContent: 'flex-end',

    '@media (max-width: 768px)': {
      width: '100%',
      justifyContent: 'space-between',
    },
  },

  queueButton: {
    width: '40px',
    height: '40px',
    padding: 0,
    border: `1px solid ${tokens.colors.border.medium}`,
    borderRadius: tokens.borderRadius.md,
    cursor: 'pointer',
    fontSize: tokens.typography.fontSize.lg,
    fontWeight: tokens.typography.fontWeight.medium,
    transition: tokens.transitions.all,
    backgroundColor: 'transparent',
    color: tokens.colors.text.primary,
    outline: 'none',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
  },

  queuePanelWrapper: {
    borderTop: `1px solid ${tokens.colors.border.medium}`,
    padding: tokens.spacing.lg,
    maxHeight: '400px',
    overflowY: 'auto' as const,
    backgroundColor: tokens.colors.bg.secondary,
  },

  errorBanner: {
    display: 'flex',
    alignItems: 'center',
    padding: tokens.spacing.md,
    backgroundColor: tokens.colors.accent.error || '#ff4444',
    borderRadius: tokens.borderRadius.md,
    margin: tokens.spacing.sm,
  },

  errorText: {
    color: tokens.colors.text.primary,
    fontSize: tokens.typography.fontSize.sm,
    fontWeight: tokens.typography.fontWeight.bold,
  },
};

export default Player;
