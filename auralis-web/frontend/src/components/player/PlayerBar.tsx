/**
 * PlayerBar Component
 * ~~~~~~~~~~~~~~~~~~~
 *
 * Main player bar - composite component combining all player sub-components.
 * Organizes TrackInfo, ProgressBar, PlaybackControls, and VolumeControl in a unified layout.
 *
 * Usage:
 * ```typescript
 * <PlayerBar />
 * ```
 *
 * Props: None required (uses hooks internally)
 *
 * Responsive Layout:
 * - Desktop: Vertical stack with artwork on left, controls on right
 * - Tablet: Stacked vertically with full width
 * - Mobile: Minimal, horizontal layout with artwork at top
 *
 * @module components/player/PlayerBar
 */

import React, { memo } from 'react';
import { tokens } from '@/design-system/tokens';
import PlaybackControls from './PlaybackControls';
import ProgressBar from './ProgressBar';
import TrackInfo from './TrackInfo';
import VolumeControl from './VolumeControl';

/**
 * PlayerBar component
 *
 * Main music player component with full playback controls.
 * Shows current track, progress, playback buttons, and volume.
 * Responsive design adapts to different screen sizes.
 *
 * This is a composite/container component that brings together
 * all player sub-components in an organized layout.
 */
const PlayerBar: React.FC = () => {
  return (
    <div style={styles.playerBar}>
      {/* Main player container */}
      <div style={styles.mainContent}>
        {/* Left: Track info and progress */}
        <div style={styles.leftSection}>
          <TrackInfo />
          <ProgressBar />
        </div>

        {/* Right: Controls and volume */}
        <div style={styles.rightSection}>
          <PlaybackControls />
          <VolumeControl />
        </div>
      </div>
    </div>
  );
};

/**
 * Memoize to prevent unnecessary re-renders of entire player
 * Even though this uses hooks, React's optimization still helps
 */
const MemoizedPlayerBar = memo(PlayerBar);

/**
 * Component styles using design tokens
 *
 * Responsive breakpoints:
 * - 1024px: Desktop (side-by-side layout)
 * - 768px: Tablet (stacked layout)
 * - 480px: Mobile (minimal layout)
 */
const styles = {
  playerBar: {
    display: 'flex',
    flexDirection: 'column' as const,
    width: '100%',
    backgroundColor: tokens.colors.bg.primary,
    borderTop: `1px solid ${tokens.colors.border.default}`,
    boxShadow: tokens.shadows.lg,
    zIndex: 1000, // Above other content

    // Responsive: Mobile first, then scale up
    '@media (max-width: 480px)': {
      padding: tokens.spacing.sm,
    },
    '@media (min-width: 481px)': {
      padding: tokens.spacing.md,
    },
  },

  mainContent: {
    display: 'flex',
    gap: tokens.spacing.lg,
    flexDirection: 'row' as const,
    alignItems: 'flex-start',

    // Responsive: Stack on mobile/tablet
    '@media (max-width: 1024px)': {
      flexDirection: 'column' as const,
      alignItems: 'stretch',
      gap: tokens.spacing.md,
    },
  },

  leftSection: {
    display: 'flex',
    flexDirection: 'column' as const,
    gap: tokens.spacing.md,
    flex: 1,
    minWidth: '0', // Prevent flex overflow

    '@media (max-width: 1024px)': {
      width: '100%',
    },
  },

  rightSection: {
    display: 'flex',
    flexDirection: 'column' as const,
    gap: tokens.spacing.md,
    minWidth: '300px',

    '@media (max-width: 1024px)': {
      width: '100%',
      minWidth: 'auto',
      flexDirection: 'row' as const,
      justifyContent: 'space-between',
    },

    '@media (max-width: 768px)': {
      flexDirection: 'column' as const,
    },
  },
};

export { PlayerBar, MemoizedPlayerBar };
export default MemoizedPlayerBar;
