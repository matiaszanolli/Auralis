import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useVirtualizer } from '@tanstack/react-virtual';
import { usePlaybackQueue } from '@/hooks/player/usePlaybackQueue';
import { QueueTrackItem } from './QueueTrackItem';
import { QueueControlBar } from './QueueControlBar';
import { ClearQueueDialog } from './ClearQueueDialog';
import { styles, QUEUE_ITEM_HEIGHT, DRAG_EDGE_ZONE, DRAG_SCROLL_SPEED } from './styles';

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

  const queueScrollRef = useRef<HTMLDivElement>(null);
  const virtualizer = useVirtualizer({
    count: queue.length,
    getScrollElement: () => queueScrollRef.current,
    estimateSize: () => QUEUE_ITEM_HEIGHT,
    overscan: 5,
  });

  const scrollDirectionRef = useRef<number>(0);
  const rafIdRef = useRef<number | null>(null);

  const autoScrollLoop = useCallback(() => {
    const el = queueScrollRef.current;
    if (!el || scrollDirectionRef.current === 0) {
      rafIdRef.current = null;
      return;
    }
    el.scrollTop += scrollDirectionRef.current * DRAG_SCROLL_SPEED;
    rafIdRef.current = requestAnimationFrame(autoScrollLoop);
  }, []);

  const handleContainerDragOver = useCallback(
    (e: React.DragEvent<HTMLDivElement>) => {
      if (draggingIndex === null) return;
      e.preventDefault();
      const rect = e.currentTarget.getBoundingClientRect();
      const y = e.clientY - rect.top;

      if (y < DRAG_EDGE_ZONE) {
        scrollDirectionRef.current = -1;
      } else if (y > rect.height - DRAG_EDGE_ZONE) {
        scrollDirectionRef.current = 1;
      } else {
        scrollDirectionRef.current = 0;
      }

      if (scrollDirectionRef.current !== 0 && rafIdRef.current === null) {
        rafIdRef.current = requestAnimationFrame(autoScrollLoop);
      }
    },
    [draggingIndex, autoScrollLoop],
  );

  const stopAutoScroll = useCallback(() => {
    scrollDirectionRef.current = 0;
    if (rafIdRef.current !== null) {
      cancelAnimationFrame(rafIdRef.current);
      rafIdRef.current = null;
    }
  }, []);

  useEffect(() => {
    return () => {
      if (rafIdRef.current !== null) {
        cancelAnimationFrame(rafIdRef.current);
      }
    };
  }, []);

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

  const handleReorderTrack = useCallback(async (fromIndex: number, toIndex: number) => {
    if (fromIndex === toIndex) return;

    try {
      await reorderTrack(fromIndex, toIndex);
    } catch (err) {
      console.error('Failed to reorder track:', err);
    }
  }, [reorderTrack]);

  // Stable callbacks for virtualized list items (avoid per-render recreation)
  const handleDragEnd = useCallback(() => {
    if (draggingIndex !== null && dragTargetRef.current !== null && draggingIndex !== dragTargetRef.current) {
      handleReorderTrack(draggingIndex, dragTargetRef.current);
    }
    setDraggingIndex(null);
    dragTargetRef.current = null;
    stopAutoScroll();
  }, [draggingIndex, stopAutoScroll]);

  const handleDragOver = useCallback((toIndex: number) => {
    dragTargetRef.current = toIndex;
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
        <div style={styles.errorBanner}>
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
                  key={`${track.id}-${index}`}
                  track={track}
                  index={index}
                  isCurrentTrack={index === currentIndex}
                  isDragging={draggingIndex === index}
                  isHovered={hoveredIndex === index}
                  onRemove={() => handleRemoveTrack(index)}
                  onDragStart={() => {
                    setDraggingIndex(index);
                    dragTargetRef.current = null;
                  }}
                  onDragEnd={handleDragEnd}
                  onDragOver={handleDragOver}
                  onHover={(hovering) =>
                    setHoveredIndex(hovering ? index : null)
                  }
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
