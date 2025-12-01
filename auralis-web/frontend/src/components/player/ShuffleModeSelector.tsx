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
import { QueueShuffler } from '@/utils/queue/queue_shuffler';
import type { ShuffleMode } from '@/utils/queue/queue_shuffler';
import styles from './ShuffleModeSelector.module.css';

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
    <div className={styles.container}>
      <div className={styles.modesGrid}>
        {modes.map((modeInfo) => (
          <button
            key={modeInfo.mode}
            className={`${styles.modeButton} ${
              currentMode === modeInfo.mode ? styles.modeButtonActive : ''
            }`}
            onClick={() => onModeChange(modeInfo.mode)}
            onMouseEnter={() => setHoveredMode(modeInfo.mode)}
            onMouseLeave={() => setHoveredMode(null)}
            disabled={disabled}
            title={modeInfo.description}
            aria-label={`Shuffle mode: ${modeInfo.name}`}
            aria-pressed={currentMode === modeInfo.mode}
          >
            <div className={styles.modeIcon}>{getModeIcon(modeInfo.mode)}</div>
            <div className={styles.modeName}>{modeInfo.name}</div>
          </button>
        ))}
      </div>

      {/* Description tooltip */}
      {hoveredMode && (
        <div className={styles.tooltip}>
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

export default ShuffleModeSelector;
