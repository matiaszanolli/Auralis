import { CSSProperties, memo, useState } from 'react';
import { formatDuration } from '@/utils/timeFormat';
import type { Track, QueueTrack } from '@/types/domain';
import { styles } from './styles';

export interface QueueTrackItemProps {
  track: Track | QueueTrack;
  index: number;
  isCurrentTrack: boolean;
  isDragging: boolean;
  isHovered: boolean;
  // Callbacks receive the item's index so the parent can pass STABLE handlers
  // (defined once) instead of per-item closures, which is what lets React.memo
  // skip re-rendering unaffected rows on hover/drag (#4177).
  onRemove: (index: number) => void;
  onDragStart: (index: number) => void;
  onDragEnd: () => void;
  onDragOver: (toIndex: number) => void;
  onHover: (index: number, hovering: boolean) => void;
  disabled: boolean;
  style?: CSSProperties;
}

const QueueTrackItemImpl = ({
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
  const [isFocused, setIsFocused] = useState(false);
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
      role="listitem"
      tabIndex={0}
      aria-current={isCurrentTrack ? 'true' : undefined}
      aria-label={`${track.title} by ${track.artist}, ${formatDuration(track.duration)}`}
      onMouseEnter={() => onHover(index, true)}
      onMouseLeave={() => onHover(index, false)}
      onFocus={() => setIsFocused(true)}
      onBlur={(e) => {
        if (!e.currentTarget.contains(e.relatedTarget as Node)) {
          setIsFocused(false);
        }
      }}
      onKeyDown={(e) => {
        if (e.key === 'Delete' || e.key === 'Backspace') {
          e.preventDefault();
          if (!disabled) onRemove(index);
        }
      }}
      draggable
      onDragStart={() => onDragStart(index)}
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
            onRemove(index);
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

/** Shallow value comparison for the per-item positioning style. The virtualizer
 *  hands a fresh style object each render with identical values (same scroll
 *  position), which would defeat React.memo's default reference check. */
function shallowEqualStyle(a?: CSSProperties, b?: CSSProperties): boolean {
  if (a === b) return true;
  if (!a || !b) return false;
  const ak = Object.keys(a) as (keyof CSSProperties)[];
  const bk = Object.keys(b);
  if (ak.length !== bk.length) return false;
  return ak.every((k) => a[k] === b[k]);
}

/**
 * Memoized so hovering/dragging one row (which re-renders QueuePanel and the
 * whole virtual window) does not re-render the other visible rows (#4177).
 * Requires the parent to pass stable handlers (it does — they take the index).
 */
export const QueueTrackItem = memo(QueueTrackItemImpl, (prev, next) =>
  prev.track === next.track &&
  prev.index === next.index &&
  prev.isCurrentTrack === next.isCurrentTrack &&
  prev.isDragging === next.isDragging &&
  prev.isHovered === next.isHovered &&
  prev.disabled === next.disabled &&
  prev.onRemove === next.onRemove &&
  prev.onDragStart === next.onDragStart &&
  prev.onDragEnd === next.onDragEnd &&
  prev.onDragOver === next.onDragOver &&
  prev.onHover === next.onHover &&
  shallowEqualStyle(prev.style, next.style)
);
