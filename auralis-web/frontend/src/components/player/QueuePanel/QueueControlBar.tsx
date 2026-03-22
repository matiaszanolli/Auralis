import React from 'react';
import { styles } from './styles';

interface QueueControlBarProps {
  isShuffled: boolean;
  repeatMode: 'off' | 'all' | 'one';
  isLoading: boolean;
  queueLength: number;
  onToggleShuffle: () => void;
  onSetRepeatMode: (mode: 'off' | 'all' | 'one') => void;
  onClearQueue: () => void;
}

export const QueueControlBar = ({
  isShuffled,
  repeatMode,
  isLoading,
  queueLength,
  onToggleShuffle,
  onSetRepeatMode,
  onClearQueue,
}: QueueControlBarProps) => {
  return (
    <div style={styles.controlBar}>
      <button
        style={{
          ...styles.modeButton,
          ...(isShuffled ? styles.modeButtonActive : {}),
        }}
        onClick={onToggleShuffle}
        disabled={isLoading}
        title={isShuffled ? 'Shuffle: ON' : 'Shuffle: OFF'}
        aria-label={isShuffled ? 'Disable shuffle' : 'Enable shuffle'}
        aria-pressed={isShuffled}
      >
        🔀 Shuffle
      </button>

      <div style={styles.repeatModeButtons}>
        <button
          style={{
            ...styles.repeatButton,
            ...(repeatMode === 'off' ? styles.repeatButtonActive : {}),
          }}
          onClick={() => onSetRepeatMode('off')}
          disabled={isLoading}
          title="Repeat: OFF"
          aria-label="Turn off repeat"
          aria-pressed={repeatMode === 'off'}
        >
          ○
        </button>
        <button
          style={{
            ...styles.repeatButton,
            ...(repeatMode === 'all' ? styles.repeatButtonActive : {}),
          }}
          onClick={() => onSetRepeatMode('all')}
          disabled={isLoading}
          title="Repeat: ALL"
          aria-label="Repeat all tracks"
          aria-pressed={repeatMode === 'all'}
        >
          ↻
        </button>
        <button
          style={{
            ...styles.repeatButton,
            ...(repeatMode === 'one' ? styles.repeatButtonActive : {}),
          }}
          onClick={() => onSetRepeatMode('one')}
          disabled={isLoading}
          title="Repeat: ONE"
          aria-label="Repeat one track"
          aria-pressed={repeatMode === 'one'}
        >
          ↻1
        </button>
      </div>

      <button
        style={styles.clearButton}
        onClick={onClearQueue}
        disabled={isLoading || queueLength === 0}
        title="Clear queue"
        aria-label="Clear all tracks from queue"
      >
        ✕ Clear
      </button>
    </div>
  );
};
