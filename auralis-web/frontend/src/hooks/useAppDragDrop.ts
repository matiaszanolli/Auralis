import { useCallback } from 'react';
import { DropResult } from '@hello-pangea/dnd';

/**
 * Toast notification function signature.
 * Used to display feedback to the user about drag-drop operations.
 */
type ToastNotifier = (message: string) => void;

/**
 * Configuration for drag-drop API endpoints and error handling.
 */
export interface DragDropConfig {
  info: ToastNotifier;
  success: ToastNotifier;
}

/**
 * Custom hook to handle drag-and-drop operations for the Auralis player.
 * Manages:
 * - Adding tracks to queue
 * - Adding tracks to playlists
 * - Reordering queue items
 * - Reordering playlist items
 *
 * Makes appropriate API calls based on drop target and provides user feedback.
 *
 * @param config Configuration with toast notification functions
 * @returns Object with handleDragEnd callback
 *
 * @example
 * const { handleDragEnd } = useAppDragDrop({
 *   info: (msg) => showToast(msg),
 *   success: (msg) => showToast(msg, 'success'),
 * });
 * // Use handleDragEnd in DragDropContext onDragEnd prop
 */
export const useAppDragDrop = ({ info, success }: DragDropConfig) => {
  const handleDragEnd = useCallback(
    async (result: DropResult) => {
      const { source, destination, draggableId } = result;

      // Dropped outside a valid droppable area
      if (!destination) {
        return;
      }

      // Dropped in the same position
      if (
        source.droppableId === destination.droppableId &&
        source.index === destination.index
      ) {
        return;
      }

      // Extract track ID from draggableId (format: "track-123")
      const trackId = parseInt(draggableId.replace('track-', ''), 10);

      try {
        // Handle different drop targets
        if (destination.droppableId === 'queue') {
          // ========================================
          // ADD TRACK TO QUEUE
          // ========================================
          await handleAddToQueue(trackId, destination.index, success);
        } else if (destination.droppableId.startsWith('playlist-')) {
          // ========================================
          // ADD TRACK TO PLAYLIST
          // ========================================
          const playlistId = parseInt(
            destination.droppableId.replace('playlist-', ''),
            10
          );
          await handleAddToPlaylist(
            trackId,
            playlistId,
            destination.index,
            success
          );
        } else if (destination.droppableId === source.droppableId) {
          // ========================================
          // REORDER WITHIN SAME LIST
          // ========================================
          if (source.droppableId === 'queue') {
            await handleReorderQueue(
              source.index,
              destination.index,
              info
            );
          } else if (source.droppableId.startsWith('playlist-')) {
            const playlistId = parseInt(
              source.droppableId.replace('playlist-', ''),
              10
            );
            await handleReorderPlaylist(
              playlistId,
              source.index,
              destination.index,
              info
            );
          }
        }
      } catch (err) {
        console.error('Drag and drop error:', err);
        info('Failed to complete drag and drop operation');
      }
    },
    [info, success]
  );

  return { handleDragEnd };
};

/**
 * Add a track to the queue at a specific position.
 */
async function handleAddToQueue(
  trackId: number,
  position: number,
  success: ToastNotifier
) {
  const response = await fetch('/api/player/queue/add-track', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      track_id: trackId,
      position,
    }),
  });

  if (!response.ok) {
    throw new Error('Failed to add track to queue');
  }

  success(`Added track to queue at position ${position + 1}`);
}

/**
 * Add a track to a specific playlist.
 */
async function handleAddToPlaylist(
  trackId: number,
  playlistId: number,
  position: number,
  success: ToastNotifier
) {
  const response = await fetch(`/api/playlists/${playlistId}/tracks/add`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      track_id: trackId,
      position,
    }),
  });

  if (!response.ok) {
    throw new Error('Failed to add track to playlist');
  }

  success('Added track to playlist');
}

/**
 * Reorder tracks within the queue.
 */
async function handleReorderQueue(
  fromIndex: number,
  toIndex: number,
  info: ToastNotifier
) {
  const response = await fetch('/api/player/queue/move', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      from_index: fromIndex,
      to_index: toIndex,
    }),
  });

  if (!response.ok) {
    throw new Error('Failed to reorder queue');
  }

  info('Queue reordered');
}

/**
 * Reorder tracks within a playlist.
 */
async function handleReorderPlaylist(
  playlistId: number,
  fromIndex: number,
  toIndex: number,
  info: ToastNotifier
) {
  const response = await fetch(
    `/api/playlists/${playlistId}/tracks/reorder`,
    {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        from_index: fromIndex,
        to_index: toIndex,
      }),
    }
  );

  if (!response.ok) {
    throw new Error('Failed to reorder playlist');
  }

  info('Playlist reordered');
}
