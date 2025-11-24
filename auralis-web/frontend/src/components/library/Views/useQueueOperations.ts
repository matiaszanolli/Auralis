import { useCallback } from 'react';
import * as queueService from '../../../services/queueService';
import { useToast } from '../../shared/Toast';

export interface UseQueueOperationsProps {
  onRemoveTrack?: () => void;
  onReorderQueue?: () => void;
  onShuffleQueue?: () => void;
  onClearQueue?: () => void;
}

/**
 * useQueueOperations - Encapsulates queue management handlers
 *
 * Manages all queue service operations with toast notifications.
 */
export const useQueueOperations = ({
  onRemoveTrack,
  onReorderQueue,
  onShuffleQueue,
  onClearQueue,
}: UseQueueOperationsProps) => {
  const { success, error, info } = useToast();

  const handleRemoveTrack = useCallback(
    async (index: number) => {
      try {
        await queueService.removeTrackFromQueue(index);
        info('Track removed from queue');
        onRemoveTrack?.();
      } catch (err) {
        error('Failed to remove track from queue');
      }
    },
    [info, error, onRemoveTrack]
  );

  const handleReorderQueue = useCallback(
    async (newOrder: number[]) => {
      try {
        await queueService.reorderQueue(newOrder);
        success('Queue reordered');
        onReorderQueue?.();
      } catch (err) {
        error('Failed to reorder queue');
      }
    },
    [success, error, onReorderQueue]
  );

  const handleShuffleQueue = useCallback(
    async () => {
      try {
        await queueService.shuffleQueue();
        success('Queue shuffled');
        onShuffleQueue?.();
      } catch (err) {
        error('Failed to shuffle queue');
      }
    },
    [success, error, onShuffleQueue]
  );

  const handleClearQueue = useCallback(
    async () => {
      try {
        await queueService.clearQueue();
        info('Queue cleared');
        onClearQueue?.();
      } catch (err) {
        error('Failed to clear queue');
      }
    },
    [info, error, onClearQueue]
  );

  return {
    handleRemoveTrack,
    handleReorderQueue,
    handleShuffleQueue,
    handleClearQueue,
  };
};
