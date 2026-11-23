import { memo, useCallback } from 'react';
import { usePlaybackControls } from '@/contexts/PlaybackSessionContext';
import { useSelector } from 'react-redux';
import { usePlaybackQueue } from '@/hooks/player/usePlaybackQueue';
import { playerSelectors } from '@/store/selectors';
import type { RootState } from '@/store';
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
const QueuePanelComponent = ({
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
  const { followRemovedTrack, stopForClearedQueue } = usePlaybackControls();
  // The queue pointer is 0 for a queue built while nothing plays; no row is playing then (#6591).
  const hasCurrentTrack = useSelector((state: RootState) => playerSelectors.selectCurrentTrack(state) != null);
  const playingIndex = hasCurrentTrack ? currentIndex : -1;

  // #6016: removing the current row moves playback to the track that takes its
  // slot (the session checks it really was the playing track: ids can repeat).
  const removeTrackFollowingPlayback = useCallback(
    async (index: number) => {
      const removedId = index === playingIndex ? queue[index]?.id : undefined;
      await removeTrack(index);
      if (removedId != null) await followRemovedTrack(index, removedId);
    },
    [playingIndex, queue, removeTrack, followRemovedTrack]
  );
  // #6561: Clear empties the queue under the playing track, so playback stops with it.
  const clearQueueStoppingPlayback = useCallback(async () => {
    await clearQueue();
    await stopForClearedQueue();
  }, [clearQueue, stopForClearedQueue]);

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
      currentIndex={playingIndex}
      isShuffled={isShuffled}
      repeatMode={repeatMode}
      isLoading={isLoading}
      error={error}
      removeTrack={removeTrackFollowingPlayback}
      reorderTrack={reorderTrack}
      toggleShuffle={toggleShuffle}
      setRepeatMode={setRepeatMode}
      clearQueue={clearQueueStoppingPlayback}
      onToggleCollapse={onToggleCollapse}
    />
  );
};

/**
 * Memoized (#4632): this is the expensive one. `Player` re-renders 10x/second
 * while a track is playing (it subscribes to the position tick to render the
 * progress bar) and QueuePanel is always mounted — hidden via CSS, not
 * unmounted, to preserve scroll and focus (#2541). So every tick re-invoked
 * `usePlaybackQueue()`, re-ran `useVirtualizer()` in QueuePanelExpanded, and
 * rebuilt the JSX for every visible row. Only the leaf `QueueTrackItem`s were
 * protected (#4177); all the reconciliation above them still happened.
 *
 * `memo` blocks re-renders driven by the parent only — `usePlaybackQueue()`
 * subscribes to the store itself, so genuine queue changes still re-render this
 * component, and the always-mounted #2541 behaviour is unaffected.
 *
 * This also covers `QueueControlBar`, which the issue listed as a sixth direct
 * child of `Player`: it is actually a grandchild, rendered by
 * `QueuePanelExpanded` below, so it stops re-rendering on the tick as soon as
 * this component does.
 */
export const QueuePanel = memo(QueuePanelComponent);

QueuePanel.displayName = 'QueuePanel';

export default QueuePanel;
