import { useCallback, useRef, useState } from 'react';
import { useVirtualizer } from '@tanstack/react-virtual';
import type { QueueTrack, RepeatMode, Track } from '@/types/domain';
import type { ApiError } from '@/types/api';
import { QueueTrackItem } from './QueueTrackItem';
import { QueueControlBar } from './QueueControlBar';
import { ClearQueueDialog } from './ClearQueueDialog';
import { useQueueAutoScroll } from './useQueueAutoScroll';
import { useQueueKeyboardReorder } from './useQueueKeyboardReorder';
import { useQueueRovingFocus } from './useQueueRovingFocus';
import { useQueueActions } from './useQueueActions';
import { useQueueRowKeys } from './useQueueRowKeys';
import { styles, QUEUE_ITEM_HEIGHT } from './styles';

interface QueuePanelExpandedProps {
  queue: (Track | QueueTrack)[];
  currentIndex: number;
  isShuffled: boolean;
  repeatMode: RepeatMode;
  isLoading: boolean;
  error: ApiError | null;
  removeTrack: (index: number) => Promise<void>;
  reorderTrack: (fromIndex: number, toIndex: number) => Promise<void>;
  toggleShuffle: () => Promise<void>;
  setRepeatMode: (mode: RepeatMode) => Promise<void>;
  clearQueue: () => Promise<void>;
  onToggleCollapse?: () => void;
}

/**
 * The `!collapsed` body of QueuePanel, extracted into its own component
 * (#5007) so it owns its nine trailing hooks unconditionally instead of
 * calling them after a conditional early return in the parent — the same
 * Rules-of-Hooks defect class fixed as CRITICAL in `LibraryViewRouter.tsx`
 * (#3924). `queue`/`currentIndex`/etc. come from the parent's single
 * `usePlaybackQueue()` call as props rather than a second call here —
 * `usePlaybackQueue()` mounts `useQueueFetch`'s initial REST fetch and
 * `useQueueSubscription`'s WebSocket subscription, so calling it twice would
 * duplicate both, not just re-read the same state.
 */
export const QueuePanelExpanded = ({
  queue,
  currentIndex,
  isShuffled,
  repeatMode,
  isLoading,
  error,
  removeTrack,
  reorderTrack,
  toggleShuffle,
  setRepeatMode,
  clearQueue,
  onToggleCollapse,
}: QueuePanelExpandedProps) => {
  const [draggingIndex, setDraggingIndex] = useState<number | null>(null);
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);
  const dragTargetRef = useRef<number | null>(null);
  const rowKeys = useQueueRowKeys(queue);

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

  const { handleKeyboardReorder, handleRemove: handleRemoveTrack, announcement } = useQueueKeyboardReorder({
    queue,
    reorderTrack,
    removeTrack,
    scrollElementRef: queueScrollRef,
    virtualizer,
  });

  const { tabStopIndex, onListKeyDown, onListFocus } = useQueueRovingFocus({
    queueLength: queue.length,
    scrollElementRef: queueScrollRef,
    virtualizer,
  });

  const {
    showClearConfirm,
    handleToggleShuffle,
    handleSetRepeatMode,
    requestClearQueue,
    cancelClearQueue,
    confirmClearQueue,
  } = useQueueActions({ toggleShuffle, setRepeatMode, clearQueue });

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
        <h2 style={styles.title}>Queue ({queue.length})</h2>
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
        onClearQueue={requestClearQueue}
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
            onKeyDown={onListKeyDown}
            onFocus={onListFocus}
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
                  tabIndex={index === tabStopIndex ? 0 : -1}
                  setSize={queue.length}
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
          onCancel={cancelClearQueue}
        />
      )}
    </div>
  );
};

export default QueuePanelExpanded;
