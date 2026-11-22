import { useCallback, useState } from 'react';
import type { RepeatMode } from '@/types/domain';

interface QueueActionDeps {
  toggleShuffle: () => Promise<void>;
  setRepeatMode: (mode: RepeatMode) => Promise<void>;
  clearQueue: () => Promise<void>;
}

/** Run *action*, logging (not rethrowing) a failure: the queue hook already surfaces it as `error`. */
async function logFailure(label: string, action: () => Promise<void>): Promise<void> {
  try {
    await action();
  } catch (err) {
    console.error(`Failed to ${label}:`, err);
  }
}

/**
 * The control-bar actions of the expanded queue panel (#6703): shuffle, repeat
 * mode, and Clear Queue behind its confirmation dialog. Each handler is stable
 * for the lifetime of its underlying action.
 */
export function useQueueActions({ toggleShuffle, setRepeatMode, clearQueue }: QueueActionDeps) {
  const [showClearConfirm, setShowClearConfirm] = useState(false);

  const handleToggleShuffle = useCallback(
    () => logFailure('toggle shuffle', toggleShuffle),
    [toggleShuffle]
  );
  const handleSetRepeatMode = useCallback(
    (mode: RepeatMode) => logFailure('set repeat mode', () => setRepeatMode(mode)),
    [setRepeatMode]
  );
  const requestClearQueue = useCallback(() => setShowClearConfirm(true), []);
  const cancelClearQueue = useCallback(() => setShowClearConfirm(false), []);
  const confirmClearQueue = useCallback(() => {
    setShowClearConfirm(false);
    return logFailure('clear queue', clearQueue);
  }, [clearQueue]);

  return {
    showClearConfirm,
    handleToggleShuffle,
    handleSetRepeatMode,
    requestClearQueue,
    cancelClearQueue,
    confirmClearQueue,
  };
}
