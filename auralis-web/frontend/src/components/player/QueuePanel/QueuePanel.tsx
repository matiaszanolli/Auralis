import { usePlaybackQueue } from '@/hooks/player/usePlaybackQueue';
import { QueuePanelExpanded } from './QueuePanelExpanded';
import { styles } from './styles';

interface QueuePanelProps {
  collapsed?: boolean;
  onToggleCollapse?: () => void;
}

/**
 * #5007: QueuePanel used to call 9 `useCallback` hooks AFTER an
 * `if (collapsed) return (...)` early return — a Rules-of-Hooks violation
 * (mid-lifetime change in hook call count/order the moment `collapsed`
 * varies), the same defect class fixed as CRITICAL in `LibraryViewRouter.tsx`
 * (#3924). `usePlaybackQueue()` mounts real side effects (initial REST
 * fetch, WebSocket subscription), so it stays here, called exactly once
 * regardless of `collapsed`; every hook that's only needed when expanded now
 * lives in `QueuePanelExpanded`, called unconditionally by that component's
 * own single instance instead of conditionally by this one.
 */
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

  return (
    <QueuePanelExpanded
      queue={queue}
      currentIndex={currentIndex}
      isShuffled={isShuffled}
      repeatMode={repeatMode}
      isLoading={isLoading}
      error={error}
      removeTrack={removeTrack}
      reorderTrack={reorderTrack}
      toggleShuffle={toggleShuffle}
      setRepeatMode={setRepeatMode}
      clearQueue={clearQueue}
      onToggleCollapse={onToggleCollapse}
    />
  );
};

export default QueuePanel;
