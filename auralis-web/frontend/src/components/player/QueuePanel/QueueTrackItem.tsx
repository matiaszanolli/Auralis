import React from 'react';
import { formatDuration } from '@/utils/timeFormat';
import type { Track } from '@/types/domain';
import { styles } from './styles';

export interface QueueTrackItemProps {
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
  style?: React.CSSProperties;
}

export const QueueTrackItem = ({
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
  style: positionStyle,
}: QueueTrackItemProps) => {
  const [isFocused, setIsFocused] = React.useState(false);
  const showActions = isHovered || isFocused;

  return (
    <li
      style={{
        ...styles.trackItem,
        ...(isCurrentTrack ? styles.trackItemCurrent : {}),
        ...(isDragging ? styles.trackItemDragging : {}),
        ...((isHovered || isFocused) ? styles.trackItemHovered : {}),
        ...positionStyle,
      }}
      tabIndex={0}
      role="option"
      aria-selected={isCurrentTrack}
      aria-label={`${track.title} by ${track.artist}, ${formatDuration(track.duration)}`}
      onMouseEnter={() => onHover(true)}
      onMouseLeave={() => onHover(false)}
      onFocus={() => setIsFocused(true)}
      onBlur={(e) => {
        if (!e.currentTarget.contains(e.relatedTarget as Node)) {
          setIsFocused(false);
        }
      }}
      onKeyDown={(e) => {
        if (e.key === 'Delete' || e.key === 'Backspace') {
          e.preventDefault();
          if (!disabled) onRemove();
        }
      }}
      draggable
      onDragStart={onDragStart}
      onDragEnd={onDragEnd}
      onDragOver={(e) => {
        e.preventDefault();
        onDragOver(index);
      }}
      title={`${track.title} - ${track.artist}`}
    >
      <span style={styles.trackIndex}>{index + 1}</span>

      <div style={styles.trackInfo}>
        <div style={styles.trackTitle}>
          {isCurrentTrack && <span style={styles.playingIcon}>▶</span>}
          {track.title}
        </div>
        <div style={styles.trackArtist}>{track.artist}</div>
      </div>

      <span style={styles.trackDuration}>{formatDuration(track.duration)}</span>

      {showActions && (
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
