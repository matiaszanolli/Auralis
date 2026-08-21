import { useCallback } from 'react';
import { DropResult } from '@hello-pangea/dnd';

import { APIRequestError, post, put } from '@/utils/apiRequest';

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
        // Surface the backend detail (carried on err.message) so the user sees
        // an actionable message instead of a generic fallback (#3989).
        info(err instanceof Error ? err.message : 'Failed to complete drag and drop operation');
      }
    },
    [info, success]
  );

  return { handleDragEnd };
};

/**
 * Run a drag-drop mutation, keeping the handler's specific fallback message.
 *
 * These four handlers used bare `fetch()` with no signal and no timeout, so a
 * hung backend left the action pending forever with no feedback — drag-drop
 * has no loading indicator either (#4694). They now go through `apiRequest`,
 * which applies the app-wide 30s timeout (#4442) and already prefers the
 * backend's `detail` field, which is what #3989 wanted.
 *
 * The wrapper exists for the one case `apiRequest` cannot know about: an HTTP
 * error with no `detail` in the body. `apiRequest` renders that as
 * "Request failed with status 500", where these toasts want "Failed to add
 * track to queue".
 *
 * Discriminating on `statusCode`, not on `detail` alone, is deliberate: a
 * timeout is also an `APIRequestError` with no `detail`, but it carries
 * `statusCode: 0`. Testing `!detail` by itself would replace
 * "Request timed out after 30000ms" with the generic fallback and hide exactly
 * the failure this issue is about.
 */
async function withFallbackMessage(
  fallback: string,
  send: () => Promise<unknown>
): Promise<void> {
  try {
    await send();
  } catch (err) {
    if (err instanceof APIRequestError && err.statusCode !== 0 && !err.detail) {
      throw new Error(fallback);
    }
    throw err;
  }
}

/**
 * Add a track to the queue at a specific position.
 */
async function handleAddToQueue(
  trackId: number,
  position: number,
  success: ToastNotifier
) {
  await withFallbackMessage('Failed to add track to queue', () =>
    post('/api/player/queue/add-track', { track_id: trackId, position })
  );

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
  await withFallbackMessage('Failed to add track to playlist', () =>
    post(`/api/playlists/${playlistId}/tracks/add`, { track_id: trackId, position })
  );

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
  await withFallbackMessage('Failed to reorder queue', () =>
    put('/api/player/queue/move', { from_index: fromIndex, to_index: toIndex })
  );

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
  await withFallbackMessage('Failed to reorder playlist', () =>
    put(`/api/playlists/${playlistId}/tracks/reorder`, {
      from_index: fromIndex,
      to_index: toIndex,
    })
  );

  info('Playlist reordered');
}
