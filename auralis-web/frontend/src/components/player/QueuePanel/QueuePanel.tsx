import { useCallback, useMemo, useRef, useState } from 'react';
import { useVirtualizer } from '@tanstack/react-virtual';
import { usePlaybackQueue } from '@/hooks/player/usePlaybackQueue';
import { QueueTrackItem } from './QueueTrackItem';
import { QueueControlBar } from './QueueControlBar';
import { ClearQueueDialog } from './ClearQueueDialog';
import { useQueueAutoScroll } from './useQueueAutoScroll';
import { useQueueKeyboardReorder } from './useQueueKeyboardReorder';
import { styles, QUEUE_ITEM_HEIGHT } from './styles';

interface QueuePanelProps {
  collapsed?: boolean;
  onToggleCollapse?: () => void;
}

export const QueuePanel = ({
  collapsed = false,
  onToggleCollapse,
}: QueuePanelProps) => {
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

  const [draggingIndex, setDraggingIndex] = useState<number | null>(null);
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);
  const [showClearConfirm, setShowClearConfirm] = useState(false);
  const dragTargetRef = useRef<number | null>(null);

  // Stable per-row React keys (#4428).
  //
  // The key used to be `${track.id}-${index}`, which made position part of a
  // row's identity: any reorder or mid-queue removal changed the key of every
  // shifted row, so React unmounted and remounted them — precisely what
  // QueueTrackItem's React.memo was added to avoid (#4177) — and each remount
  // dropped the row's internal isFocused/hover state.
  //
  // Keying on `track.id` alone is not safe: the backend queue does not dedupe
  // (QueueController.add_track appends unconditionally), so the same track can
  // legitimately appear twice and would collide. Disambiguate duplicates by
  // occurrence ordinal instead of array index — a queue of unique tracks then
  // gets a fully position-independent key, and in a queue with duplicates only
  // the duplicates' own relative order can change a key.
  const rowKeys = useMemo(() => {
    const seen = new Map<number, number>();
    return queue.map((track) => {
      const occurrence = seen.get(track.id) ?? 0;
      seen.set(track.id, occurrence + 1);
      return occurrence === 0 ? `qt-${track.id}` : `qt-${track.id}#${occurrence}`;
    });
  }, [queue]);

  const queueScrollRef = useRef<HTMLDivElement>(null);
  const virtualizer = useVirtualizer({
    count: queue.length,
    getScrollElement: () => queueScrollRef.current,
    estimateSize: () => QUEUE_ITEM_HEIGHT,
    overscan: 5,
  });

  const { handleContainerDragOver, stopAutoScroll } = useQueueAutoScroll({
    scrollElementRef: queueScrollRef,
    isDragActive: draggingIndex !== null,
  });

  const handleReorderTrack = useCallback(async (fromIndex: number, toIndex: number) => {
    if (fromIndex === toIndex) return;

    try {
      await reorderTrack(fromIndex, toIndex);
    } catch (err) {
      console.error('Failed to reorder track:', err);
    }
  }, [reorderTrack]);

  const { handleKeyboardReorder, announcement } = useQueueKeyboardReorder({
    queue,
    reorderTrack,
    scrollElementRef: queueScrollRef,
    virtualizer,
  });

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

  const handleRemoveTrack = useCallback(async (index: number) => {
    try {
      await removeTrack(index);
    } catch (err) {
      console.error('Failed to remove track from queue:', err);
    }
  }, [removeTrack]);

  const handleToggleShuffle = useCallback(async () => {
    try {
      await toggleShuffle();
    } catch (err) {
      console.error('Failed to toggle shuffle:', err);
    }
  }, [toggleShuffle]);

  const handleSetRepeatMode = useCallback(async (mode: 'off' | 'all' | 'one') => {
    try {
      await setRepeatMode(mode);
    } catch (err) {
      console.error('Failed to set repeat mode:', err);
    }
  }, [setRepeatMode]);

  const handleClearQueue = useCallback(() => {
    setShowClearConfirm(true);
  }, []);

  const confirmClearQueue = useCallback(async () => {
    setShowClearConfirm(false);
    try {
      await clearQueue();
    } catch (err) {
      console.error('Failed to clear queue:', err);
    }
  }, [clearQueue]);

  // Stable callbacks for virtualized list items (avoid per-render recreation)
  const handleDragEnd = useCallback(() => {
    if (draggingIndex !== null && dragTargetRef.current !== null && draggingIndex !== dragTargetRef.current) {
      handleReorderTrack(draggingIndex, dragTargetRef.current);
    }
    setDraggingIndex(null);
    dragTargetRef.current = null;
    stopAutoScroll();
  }, [draggingIndex, handleReorderTrack, stopAutoScroll]);

  const handleDragOver = useCallback((toIndex: number) => {
    dragTargetRef.current = toIndex;
  }, []);

  // Stable per-item handlers (take the index) so QueueTrackItem's React.memo
  // holds across hover/drag — passing inline closures per row would defeat it
  // and re-render every visible row on each hover (#4177).
  const handleDragStart = useCallback((index: number) => {
    setDraggingIndex(index);
    dragTargetRef.current = null;
  }, []);

  const handleHover = useCallback((index: number, hovering: boolean) => {
    setHoveredIndex(hovering ? index : null);
  }, []);

  return (
    <div style={styles.container}>
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

      <QueueControlBar
        isShuffled={isShuffled}
        repeatMode={repeatMode}
        isLoading={isLoading}
        queueLength={queue.length}
        onToggleShuffle={handleToggleShuffle}
        onSetRepeatMode={handleSetRepeatMode}
        onClearQueue={handleClearQueue}
      />

      {error && (
        <div style={styles.errorBanner} role="alert">
          <span>{error.message}</span>
        </div>
      )}

      <div
        style={styles.queueContainer}
        ref={queueScrollRef}
        onDragOver={handleContainerDragOver}
        onDragLeave={stopAutoScroll}
        onDrop={stopAutoScroll}
      >
        {queue.length === 0 ? (
          <div style={styles.emptyState}>
            <p>Queue is empty</p>
            <p style={styles.emptySubtext}>Add tracks to get started</p>
          </div>
        ) : (
          <ul
            // #3649: an ordered playback queue is a list of items, not a
            // selection widget. role="list" + aria-current="true" on the
            // playing item conveys "now playing" without conflating it
            // with the AT concept of "selected".
            role="list"
            aria-label="Queue tracks"
            style={{
              ...styles.queueList,
              height: virtualizer.getTotalSize(),
              position: 'relative' as const,
            }}
          >
            {virtualizer.getVirtualItems().map((virtualRow) => {
              const track = queue[virtualRow.index];
              const index = virtualRow.index;
              return (
                <QueueTrackItem
                  key={rowKeys[index]}
                  track={track}
                  index={index}
                  isCurrentTrack={index === currentIndex}
                  isDragging={draggingIndex === index}
                  isHovered={hoveredIndex === index}
                  onRemove={handleRemoveTrack}
                  onReorder={handleKeyboardReorder}
                  onDragStart={handleDragStart}
                  onDragEnd={handleDragEnd}
                  onDragOver={handleDragOver}
                  onHover={handleHover}
                  disabled={isLoading}
                  style={{
                    position: 'absolute' as const,
                    top: 0,
                    left: 0,
                    width: '100%',
                    transform: `translateY(${virtualRow.start}px)`,
                  }}
                />
              );
            })}
          </ul>
        )}
      </div>

      {/* Reorder feedback (#4536). A keyboard move has no visual affordance and
          the row silently changes place, so the new position is announced here.
          role="status" is implicitly aria-live="polite". */}
      <div role="status" aria-live="polite" style={styles.visuallyHidden}>
        {announcement}
      </div>

      {showClearConfirm && (
        <ClearQueueDialog
          onConfirm={confirmClearQueue}
          onCancel={() => setShowClearConfirm(false)}
        />
      )}
    </div>
  );
};

export default QueuePanel;
