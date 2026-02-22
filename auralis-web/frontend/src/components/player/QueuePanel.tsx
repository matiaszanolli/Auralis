/**
 * QueuePanel Component
 * ~~~~~~~~~~~~~~~~~~~
 *
 * Displays and manages the playback queue with full controls.
 * Shows all queued tracks with ability to reorder, remove, and manage playback order.
 *
 * Features:
 * - Display current queue with visual indicators
 * - Drag-and-drop reordering (future enhancement)
 * - Remove tracks from queue
 * - Toggle shuffle and repeat modes
 * - Highlight current playing track
 * - Responsive design for all screen sizes
 *
 * Usage:
 * ```typescript
 * <QueuePanel collapsed={false} onToggleCollapse={() => {}} />
 * ```
 *
 * @module components/player/QueuePanel
 */

import React, { useState } from 'react';
import { tokens } from '@/design-system';
import { usePlaybackQueue } from '@/hooks/player/usePlaybackQueue';
import type { Track } from '@/types/domain';

interface QueuePanelProps {
  /** Whether panel is collapsed */
  collapsed?: boolean;

  /** Callback when collapse toggle is clicked */
  onToggleCollapse?: () => void;
}

/**
 * QueuePanel Component
 *
 * Displays the playback queue with interactive controls.
 * Allows users to reorder, remove, and manage queue settings.
 */
export const QueuePanel: React.FC<QueuePanelProps> = ({
  collapsed = false,
  onToggleCollapse,
}) => {
  const {
    queue,
    currentIndex,
    isShuffled,
    repeatMode,
    removeTrack,
    reorderTrack,
    toggleShuffle,
    setRepeatMode,
    clearQueue,
    isLoading,
    error,
  } = usePlaybackQueue();

  // Local state for UI interactions
  const [draggingIndex, setDraggingIndex] = useState<number | null>(null);
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);

  if (collapsed) {
    return (
      <div style={styles.collapsedContainer}>
        <button
          style={styles.toggleButton}
          onClick={onToggleCollapse}
          title="Expand queue"
          aria-label="Expand queue panel"
        >
          ▶ Queue ({queue.length})
        </button>
      </div>
    );
  }

  const handleRemoveTrack = async (index: number) => {
    try {
      await removeTrack(index);
    } catch (err) {
      console.error('Failed to remove track from queue:', err);
    }
  };

  const handleToggleShuffle = async () => {
    try {
      await toggleShuffle();
    } catch (err) {
      console.error('Failed to toggle shuffle:', err);
    }
  };

  const handleSetRepeatMode = async (mode: 'off' | 'all' | 'one') => {
    try {
      await setRepeatMode(mode);
    } catch (err) {
      console.error('Failed to set repeat mode:', err);
    }
  };

  const handleClearQueue = async () => {
    if (confirm('Clear the entire queue?')) {
      try {
        await clearQueue();
      } catch (err) {
        console.error('Failed to clear queue:', err);
      }
    }
  };

  const handleReorderTrack = async (fromIndex: number, toIndex: number) => {
    if (fromIndex === toIndex) return;

    try {
      await reorderTrack(fromIndex, toIndex);
    } catch (err) {
      console.error('Failed to reorder track:', err);
    }
  };

  return (
    <div style={styles.container}>
      {/* Header */}
      <div style={styles.header}>
        <h3 style={styles.title}>Queue ({queue.length})</h3>
        <button
          style={styles.toggleButton}
          onClick={onToggleCollapse}
          title="Collapse queue"
          aria-label="Collapse queue panel"
        >
          ▼
        </button>
      </div>

      {/* Control Bar */}
      <div style={styles.controlBar}>
        <button
          style={{
            ...styles.modeButton,
            ...(isShuffled ? styles.modeButtonActive : {}),
          }}
          onClick={handleToggleShuffle}
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
            onClick={() => handleSetRepeatMode('off')}
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
            onClick={() => handleSetRepeatMode('all')}
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
            onClick={() => handleSetRepeatMode('one')}
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
          onClick={handleClearQueue}
          disabled={isLoading || queue.length === 0}
          title="Clear queue"
          aria-label="Clear all tracks from queue"
        >
          ✕ Clear
        </button>
      </div>

      {/* Error Display */}
      {error && (
        <div style={styles.errorBanner}>
          <span>{error.message}</span>
        </div>
      )}

      {/* Queue List */}
      <div style={styles.queueContainer}>
        {queue.length === 0 ? (
          <div style={styles.emptyState}>
            <p>Queue is empty</p>
            <p style={styles.emptySubtext}>Add tracks to get started</p>
          </div>
        ) : (
          <ul style={styles.queueList}>
            {queue.map((track, index) => (
              <QueueTrackItem
                key={`${track.id}-${index}`}
                track={track}
                index={index}
                isCurrentTrack={index === currentIndex}
                isDragging={draggingIndex === index}
                isHovered={hoveredIndex === index}
                onRemove={() => handleRemoveTrack(index)}
                onDragStart={() => setDraggingIndex(index)}
                onDragEnd={() => setDraggingIndex(null)}
                onDragOver={(toIndex) => {
                  if (draggingIndex !== null && draggingIndex !== toIndex) {
                    handleReorderTrack(draggingIndex, toIndex);
                  }
                }}
                onHover={(hovering) =>
                  setHoveredIndex(hovering ? index : null)
                }
                disabled={isLoading}
              />
            ))}
          </ul>
        )}
      </div>
    </div>
  );
};

/**
 * QueueTrackItem Component
 *
 * Individual track item in the queue with remove and drag handles.
 */
interface QueueTrackItemProps {
  track: Track;
  index: number;
  isCurrentTrack: boolean;
  isDragging: boolean;
  isHovered: boolean;
  onRemove: () => void;
  onDragStart: () => void;
  onDragEnd: () => void;
  onDragOver: (toIndex: number) => void;
  onHover: (hovering: boolean) => void;
  disabled: boolean;
}

const QueueTrackItem: React.FC<QueueTrackItemProps> = ({
  track,
  index,
  isCurrentTrack,
  isDragging,
  isHovered,
  onRemove,
  onDragStart,
  onDragEnd,
  onDragOver,
  onHover,
  disabled,
}) => {
  return (
    <li
      style={{
        ...styles.trackItem,
        ...(isCurrentTrack ? styles.trackItemCurrent : {}),
        ...(isDragging ? styles.trackItemDragging : {}),
        ...(isHovered ? styles.trackItemHovered : {}),
      }}
      onMouseEnter={() => onHover(true)}
      onMouseLeave={() => onHover(false)}
      draggable
      onDragStart={onDragStart}
      onDragEnd={onDragEnd}
      onDragOver={(e) => {
        e.preventDefault();
        onDragOver(index);
      }}
      title={`${track.title} - ${track.artist}`}
    >
      {/* Index and Drag Handle */}
      <span style={styles.trackIndex}>{index + 1}</span>

      {/* Track Info */}
      <div style={styles.trackInfo}>
        <div style={styles.trackTitle}>
          {isCurrentTrack && <span style={styles.playingIcon}>▶</span>}
          {track.title}
        </div>
        <div style={styles.trackArtist}>{track.artist}</div>
      </div>

      {/* Duration */}
      <span style={styles.trackDuration}>{formatDuration(track.duration)}</span>

      {/* Remove Button (visible on hover) */}
      {isHovered && (
        <button
          style={styles.removeButton}
          onClick={(e) => {
            e.preventDefault();
            onRemove();
          }}
          disabled={disabled}
          title="Remove from queue"
          aria-label={`Remove ${track.title} from queue`}
        >
          ✕
        </button>
      )}
    </li>
  );
};

/**
 * Format duration in MM:SS or HH:MM:SS format
 */
function formatDuration(seconds: number): string {
  if (!isFinite(seconds)) return '0:00';
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = Math.floor(seconds % 60);

  if (hours > 0) {
    return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  }
  return `${minutes}:${secs.toString().padStart(2, '0')}`;
}

/**
 * Component styles using design tokens
 */
const styles = {
  container: {
    display: 'flex',
    flexDirection: 'column' as const,
    width: '100%',
    height: '100%',
    backgroundColor: tokens.colors.bg.primary,
    borderLeft: `1px solid ${tokens.colors.border.light}`,
    overflow: 'hidden',
  },

  collapsedContainer: {
    display: 'flex',
    padding: tokens.spacing.md,
  },

  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: tokens.spacing.md,
    borderBottom: `1px solid ${tokens.colors.border.light}`,
  },

  title: {
    margin: 0,
    fontSize: tokens.typography.fontSize.lg,
    fontWeight: tokens.typography.fontWeight.bold,
    color: tokens.colors.text.primary,
  },

  toggleButton: {
    background: 'none',
    border: 'none',
    color: tokens.colors.text.primary,
    cursor: 'pointer',
    fontSize: tokens.typography.fontSize.lg,
    padding: tokens.spacing.sm,
    borderRadius: tokens.borderRadius.md,
    transition: 'background-color 0.2s',

    ':hover': {
      backgroundColor: tokens.colors.bg.secondary,
    },
  },

  controlBar: {
    display: 'flex',
    gap: tokens.spacing.sm,
    padding: tokens.spacing.md,
    borderBottom: `1px solid ${tokens.colors.border.light}`,
    flexWrap: 'wrap' as const,
  },

  modeButton: {
    padding: `${tokens.spacing.xs} ${tokens.spacing.sm}`,
    borderRadius: tokens.borderRadius.md,
    border: `1px solid ${tokens.colors.border.light}`,
    backgroundColor: tokens.colors.bg.secondary,
    color: tokens.colors.text.primary,
    cursor: 'pointer',
    fontSize: tokens.typography.fontSize.sm,
    fontWeight: tokens.typography.fontWeight.semibold,
    transition: 'all 0.2s',

    ':hover': {
      backgroundColor: tokens.colors.bg.tertiary,
    },

    ':disabled': {
      opacity: 0.5,
      cursor: 'not-allowed',
    },
  },

  modeButtonActive: {
    backgroundColor: tokens.colors.accent.primary,
    color: tokens.colors.text.primaryFull, // White text on accent background
    borderColor: tokens.colors.accent.primary,
  },

  repeatModeButtons: {
    display: 'flex',
    gap: tokens.spacing.xs,
    borderLeft: `1px solid ${tokens.colors.border.light}`,
    paddingLeft: tokens.spacing.sm,
    marginLeft: tokens.spacing.sm,
  },

  repeatButton: {
    padding: `${tokens.spacing.xs} ${tokens.spacing.sm}`,
    borderRadius: tokens.borderRadius.md,
    border: `1px solid ${tokens.colors.border.light}`,
    backgroundColor: tokens.colors.bg.secondary,
    color: tokens.colors.text.primary,
    cursor: 'pointer',
    fontSize: tokens.typography.fontSize.sm,
    fontWeight: tokens.typography.fontWeight.bold,
    transition: 'all 0.2s',
    minWidth: '36px',

    ':hover': {
      backgroundColor: tokens.colors.bg.tertiary,
    },

    ':disabled': {
      opacity: 0.5,
      cursor: 'not-allowed',
    },
  },

  repeatButtonActive: {
    backgroundColor: tokens.colors.accent.primary,
    color: tokens.colors.text.primaryFull, // White text on accent background
    borderColor: tokens.colors.accent.primary,
  },

  clearButton: {
    marginLeft: 'auto',
    padding: `${tokens.spacing.xs} ${tokens.spacing.sm}`,
    borderRadius: tokens.borderRadius.md,
    border: `1px solid ${tokens.colors.border.light}`,
    backgroundColor: tokens.colors.bg.secondary,
    color: tokens.colors.text.primary,
    cursor: 'pointer',
    fontSize: tokens.typography.fontSize.sm,
    transition: 'all 0.2s',

    ':hover': {
      backgroundColor: tokens.colors.semantic.error,
      color: tokens.colors.text.primaryFull, // White text on error background
    },

    ':disabled': {
      opacity: 0.5,
      cursor: 'not-allowed',
    },
  },

  errorBanner: {
    padding: tokens.spacing.md,
    backgroundColor: tokens.colors.semantic.error,
    color: tokens.colors.text.primaryFull, // White text on error background
    fontSize: tokens.typography.fontSize.sm,
  },

  queueContainer: {
    flex: 1,
    overflow: 'auto',
    display: 'flex',
    flexDirection: 'column' as const,
  },

  queueList: {
    listStyle: 'none',
    margin: 0,
    padding: 0,
  },

  trackItem: {
    display: 'flex',
    alignItems: 'center',
    gap: tokens.spacing.md,
    padding: tokens.spacing.md,
    borderBottom: `1px solid ${tokens.colors.border.light}`,
    cursor: 'move',
    transition: 'background-color 0.2s, opacity 0.2s',

    ':hover': {
      backgroundColor: tokens.colors.bg.secondary,
    },
  },

  trackItemCurrent: {
    backgroundColor: tokens.colors.bg.secondary,
    borderLeft: `3px solid ${tokens.colors.accent.primary}`,
    paddingLeft: `calc(${tokens.spacing.md} - 3px)`,
  },

  trackItemDragging: {
    opacity: 0.6,
    backgroundColor: tokens.colors.bg.tertiary,
  },

  trackItemHovered: {
    backgroundColor: tokens.colors.bg.secondary,
  },

  trackIndex: {
    width: '32px',
    textAlign: 'center' as const,
    color: tokens.colors.text.tertiary,
    fontWeight: tokens.typography.fontWeight.semibold,
    fontSize: tokens.typography.fontSize.sm,
    flexShrink: 0,
  },

  trackInfo: {
    flex: 1,
    minWidth: 0,
    display: 'flex',
    flexDirection: 'column' as const,
    gap: tokens.spacing.xs,
  },

  trackTitle: {
    color: tokens.colors.text.primary,
    fontSize: tokens.typography.fontSize.md,
    fontWeight: tokens.typography.fontWeight.semibold,
    whiteSpace: 'nowrap' as const,
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    display: 'flex',
    alignItems: 'center',
    gap: tokens.spacing.xs,
  },

  playingIcon: {
    color: tokens.colors.accent.primary,
    fontSize: tokens.typography.fontSize.sm,
    flexShrink: 0,
  },

  trackArtist: {
    color: tokens.colors.text.tertiary,
    fontSize: tokens.typography.fontSize.sm,
    whiteSpace: 'nowrap' as const,
    overflow: 'hidden',
    textOverflow: 'ellipsis',
  },

  trackDuration: {
    color: tokens.colors.text.tertiary,
    fontSize: tokens.typography.fontSize.sm,
    fontVariantNumeric: 'tabular-nums' as const,
    flexShrink: 0,
    minWidth: '48px',
    textAlign: 'right' as const,
  },

  removeButton: {
    padding: tokens.spacing.xs,
    borderRadius: tokens.borderRadius.md,
    border: 'none',
    backgroundColor: tokens.colors.semantic.error,
    color: tokens.colors.text.primaryFull, // White text on error background
    cursor: 'pointer',
    fontSize: tokens.typography.fontSize.md,
    transition: 'opacity 0.2s',
    flexShrink: 0,

    ':hover': {
      opacity: 0.8,
    },

    ':disabled': {
      opacity: 0.5,
      cursor: 'not-allowed',
    },
  },

  emptyState: {
    display: 'flex',
    flexDirection: 'column' as const,
    alignItems: 'center',
    justifyContent: 'center',
    flex: 1,
    color: tokens.colors.text.tertiary,
    textAlign: 'center' as const,
  },

  emptySubtext: {
    fontSize: tokens.typography.fontSize.sm,
    color: tokens.colors.text.tertiary,
    marginTop: tokens.spacing.sm,
  },
};

export default QueuePanel;
