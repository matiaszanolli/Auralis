/**
 * PlayerBar Component - Premium Glass-Effect Player Footer
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Main player bar dock with glass morphism effect (semi-translucent with blur).
 * Composite component organizing:
 * - Album cover artwork (left)
 * - Track info and progress bar (center)
 * - Playback controls and volume (right)
 *
 * Design System:
 * - Glass effect: rgba(13, 17, 26, 0.92) background with 12px blur
 * - Elevation: Level 4 surface with soft shadow
 * - Brand accent: Soft Violet (#7366F0) for controls, Electric Aqua for audio-reactive
 * - Height: Fixed 96px with flexible content area
 * - Border: Subtle soft violet top border (0.12 opacity)
 *
 * Responsive Layout:
 * - Desktop (1024px+): Horizontal layout - cover | info+progress | controls+volume
 * - Tablet (768-1023px): Stacked layout - cover + info+progress centered, controls below
 * - Mobile (<768px): Vertical stack - cover small, minimal controls, full-width progress
 *
 * @module components/player/PlayerBar
 */

import React, { memo } from 'react';
import { tokens } from '@/design-system';
import PlaybackControls from './PlaybackControls';
import ProgressBar from './ProgressBar';
import TrackInfo from './TrackInfo';
import VolumeControl from './VolumeControl';

interface PlayerBarProps {
  currentTime?: number;
  duration?: number;
  isPlaying?: boolean;
  onSeek?: (time: number) => void;
  onPlay?: () => void | Promise<void>;
  onPause?: () => void | Promise<void>;
  onNext?: () => void | Promise<void>;
  onPrevious?: () => void | Promise<void>;
  volume?: number;
  onVolumeChange?: (volume: number) => void | Promise<void>;
}

/**
 * PlayerBar component - Premium glass-effect player footer
 *
 * DEPRECATED: Use PlayerBarV2Connected from @/components/player-bar-v2 instead.
 * This is a simplified presentational component. For the full connected player,
 * see PlayerBarV2Connected which integrates with Redux state and WebSocket.
 *
 * Main music player component with glass morphism design.
 * Composite/container component bringing together all player sub-components:
 * - Album artwork (left, fixed 256px on desktop)
 * - Track info and full-width progress bar (center, flex)
 * - Playback controls and volume (right, fixed width on desktop)
 *
 * Responsive design:
 * - Desktop (1024px+): Horizontal layout
 * - Tablet (768-1023px): Stacked with horizontal controls
 * - Mobile (<768px): Vertical stack
 */
const PlayerBar: React.FC<PlayerBarProps> = ({
  currentTime = 0,
  duration = 0,
  isPlaying = false,
  onSeek = () => {},
  onPlay = () => {},
  onPause = () => {},
  onNext = () => {},
  onPrevious = () => {},
  volume = 50,
  onVolumeChange = () => {},
}) => {
  return (
    <div style={styles.playerBar}>
      {/* Glass-effect background container */}
      <div style={styles.glassContainer}>
        {/* Main content - three sections */}
        <div style={styles.mainContent}>
          {/* Left: Album artwork */}
          <div style={styles.leftSection}>
            <TrackInfo />
          </div>

          {/* Center: Progress bar (full width) */}
          <div style={styles.centerSection}>
            <ProgressBar
              currentTime={currentTime}
              duration={duration}
              onSeek={onSeek}
            />
          </div>

          {/* Right: Controls and volume */}
          <div style={styles.rightSection}>
            <PlaybackControls
              isPlaying={isPlaying}
              onPlay={onPlay}
              onPause={onPause}
              onNext={onNext}
              onPrevious={onPrevious}
            />
            <VolumeControl
              volume={volume / 100}
              onVolumeChange={onVolumeChange}
            />
          </div>
        </div>
      </div>
    </div>
  );
};

/**
 * Memoize to prevent unnecessary re-renders
 */
const MemoizedPlayerBar = memo(PlayerBar);

/**
 * Component styles with glass morphism and elevation hierarchy
 *
 * Desktop layout: artwork (fixed 256px) | progress (flex) | controls (fixed width)
 * Responsive: Stacks vertically on tablet/mobile with adjusted sizing
 */
const styles = {
  playerBar: {
    position: 'fixed' as const,
    bottom: 0,
    left: 0,
    right: 0,
    width: '100%',
    height: tokens.components.playerBar.height,
    zIndex: tokens.zIndex.fixed,
    display: 'flex',
    flexDirection: 'column' as const,
  },

  glassContainer: {
    display: 'flex',
    flexDirection: 'column' as const,
    width: '100%',
    height: '100%',
    // Glass morphism effect: use component token for background
    backgroundColor: tokens.components.playerBar.background,
    backdropFilter: tokens.components.playerBar.backdropFilter,
    borderTop: tokens.components.playerBar.borderTop,
    boxShadow: tokens.components.playerBar.shadow,
    padding: tokens.spacing.md,
    boxSizing: 'border-box' as const,
  },

  mainContent: {
    display: 'flex',
    flexDirection: 'row' as const,
    width: '100%',
    height: '100%',
    gap: tokens.spacing.lg,
    alignItems: 'center',
    justifyContent: 'space-between',

    // Tablet: Stack vertically with smaller gaps
    '@media (max-width: 1023px)': {
      flexDirection: 'column' as const,
      alignItems: 'stretch',
      gap: tokens.spacing.md,
      overflow: 'auto',
    },

    // Mobile: Even more compact
    '@media (max-width: 768px)': {
      gap: tokens.spacing.sm,
      padding: tokens.spacing.sm,
    },
  },

  leftSection: {
    // Album artwork: 256px fixed on desktop, responsive on smaller screens
    width: '256px',
    height: '100%',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    flexShrink: 0,

    // Tablet: Hide or minimize artwork
    '@media (max-width: 1023px)': {
      width: '100%',
      height: 'auto',
      minHeight: '60px',
    },

    // Mobile: Very compact
    '@media (max-width: 768px)': {
      minHeight: '48px',
    },
  },

  centerSection: {
    // Progress bar: Takes remaining space
    flex: 1,
    display: 'flex',
    flexDirection: 'column' as const,
    justifyContent: 'center',
    minWidth: 0, // Prevent flex overflow

    '@media (max-width: 1023px)': {
      width: '100%',
    },
  },

  rightSection: {
    // Controls + Volume: Fixed width on desktop, flex row on tablet/mobile
    width: '320px',
    display: 'flex',
    flexDirection: 'column' as const,
    gap: tokens.spacing.sm,
    flexShrink: 0,

    // Tablet: Horizontal layout for controls + volume
    '@media (max-width: 1023px)': {
      width: '100%',
      flexDirection: 'row' as const,
      justifyContent: 'space-between',
      gap: tokens.spacing.md,
    },

    // Mobile: Stack vertically again for better thumb target
    '@media (max-width: 768px)': {
      flexDirection: 'column' as const,
      gap: tokens.spacing.sm,
    },
  },
};

export { PlayerBar, MemoizedPlayerBar };
export default MemoizedPlayerBar;
