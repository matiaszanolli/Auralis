/**
 * ShuffleModeSelector Component
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Displays and controls shuffle mode selection.
 * Shows available modes with descriptions and allows switching between them.
 *
 * Features:
 * - 6 different shuffle modes (Random, Weighted, Album, Artist, Temporal, No Repeat)
 * - Mode descriptions on hover
 * - Active mode highlighting
 * - Keyboard accessible
 * - Responsive design with design tokens
 *
 * Usage:
 * ```typescript
 * <ShuffleModeSelector
 *   currentMode="random"
 *   onModeChange={(mode) => applyShuffle(mode)}
 * />
 * ```
 *
 * @module components/player/ShuffleModeSelector
 */

import React, { useState } from 'react';
import { tokens } from '@/design-system';
import { QueueShuffler } from '@/utils/queue/queue_shuffler';
import type { ShuffleMode } from '@/utils/queue/queue_shuffler';

interface ShuffleModeSelectorProps {
  /** Currently active shuffle mode */
  currentMode: ShuffleMode;

  /** Callback when mode is selected */
  onModeChange: (mode: ShuffleMode) => void;

  /** Whether selector is disabled */
  disabled?: boolean;
}

/**
 * ShuffleModeSelector Component
 *
 * Provides UI for selecting different shuffle modes.
 */
export const ShuffleModeSelector: React.FC<ShuffleModeSelectorProps> = ({
  currentMode,
  onModeChange,
  disabled = false,
}) => {
  const [hoveredMode, setHoveredMode] = useState<ShuffleMode | null>(null);
  const modes = QueueShuffler.getModes();

  return (
    <div style={styles.container}>
      <div style={styles.modesGrid}>
        {modes.map((modeInfo) => (
          <button
            key={modeInfo.mode}
            style={{
              ...styles.modeButton,
              ...(currentMode === modeInfo.mode ? styles.modeButtonActive : {}),
            }}
            onClick={() => onModeChange(modeInfo.mode)}
            onMouseEnter={() => setHoveredMode(modeInfo.mode)}
            onMouseLeave={() => setHoveredMode(null)}
            disabled={disabled}
            title={modeInfo.description}
            aria-label={`Shuffle mode: ${modeInfo.name}`}
            aria-pressed={currentMode === modeInfo.mode}
          >
            <div style={styles.modeIcon}>{getModeIcon(modeInfo.mode)}</div>
            <div style={styles.modeName}>{modeInfo.name}</div>
          </button>
        ))}
      </div>

      {/* Description tooltip */}
      {hoveredMode && (
        <div style={styles.tooltip}>
          {modes.find((m) => m.mode === hoveredMode)?.description}
        </div>
      )}
    </div>
  );
};

/**
 * Get icon for shuffle mode
 */
function getModeIcon(mode: ShuffleMode): string {
  switch (mode) {
    case 'random':
      return '🔀';
    case 'weighted':
      return '⭐';
    case 'album':
      return '💿';
    case 'artist':
      return '🎤';
    case 'temporal':
      return '⏱️';
    case 'no_repeat':
      return '⛔';
    default:
      return '🔀';
  }
}

/**
 * Component styles using design tokens
 */
const styles = {
  container: {
    display: 'flex',
    flexDirection: 'column' as const,
    gap: tokens.spacing.md,
  },

  modesGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(80px, 1fr))',
    gap: tokens.spacing.sm,
  },

  modeButton: {
    display: 'flex',
    flexDirection: 'column' as const,
    alignItems: 'center',
    gap: tokens.spacing.xs,
    padding: tokens.spacing.md,
    borderRadius: tokens.borderRadius.md,
    border: `1px solid ${tokens.colors.border.default}`,
    backgroundColor: tokens.colors.bg.secondary,
    color: tokens.colors.text.primary,
    cursor: 'pointer',
    fontSize: tokens.typography.fontSize.sm,
    fontWeight: tokens.typography.fontWeight.semibold,
    transition: 'all 0.2s',

    ':hover': {
      backgroundColor: tokens.colors.bg.tertiary,
      borderColor: tokens.colors.accent.primary || '#0066cc',
    },

    ':disabled': {
      opacity: 0.5,
      cursor: 'not-allowed',
    },

    ':focus': {
      outline: `2px solid ${tokens.colors.accent.primary || '#0066cc'}`,
      outlineOffset: '2px',
    },
  },

  modeButtonActive: {
    backgroundColor: tokens.colors.accent.primary || '#0066cc',
    color: tokens.colors.text.inverse || '#ffffff',
    borderColor: tokens.colors.accent.primary || '#0066cc',
  },

  modeIcon: {
    fontSize: '24px',
  },

  modeName: {
    textAlign: 'center' as const,
    whiteSpace: 'nowrap' as const,
    overflow: 'hidden',
    textOverflow: 'ellipsis',
  },

  tooltip: {
    padding: tokens.spacing.sm,
    backgroundColor: tokens.colors.bg.tertiary,
    borderRadius: tokens.borderRadius.sm,
    border: `1px solid ${tokens.colors.border.default}`,
    fontSize: tokens.typography.fontSize.xs,
    color: tokens.colors.text.secondary,
    textAlign: 'center' as const,
  },
};

export default ShuffleModeSelector;
