/**
 * Queue Management Service (Phase 5a)
 *
 * Provides API functions for manipulating the playback queue:
 * - Remove tracks from queue
 * - Reorder queue
 * - Shuffle queue
 * - Clear queue
 *
 * Refactored using Service Factory Pattern (Phase 5a) to reduce code duplication.
 */

import { ENDPOINTS } from '../config/api';
import { createCrudService } from '../utils/serviceFactory';

export interface QueueTrack {
  id: number;
  title: string;
  artist?: string;
  album?: string;
  duration: number;
  filepath: string;
}

export interface QueueResponse {
  tracks: QueueTrack[];
  current_index: number;
  total_tracks: number;
}

export interface SetQueueRequest {
  tracks: number[];
  start_index?: number;
}

// Create base CRUD service using factory
const crudService = createCrudService<QueueResponse, SetQueueRequest>({
  list: ENDPOINTS.QUEUE,
  delete: (index) => ENDPOINTS.QUEUE_TRACK(index),
  custom: {
    reorder: ENDPOINTS.QUEUE_REORDER,
    shuffle: ENDPOINTS.QUEUE_SHUFFLE,
    clear: ENDPOINTS.QUEUE_CLEAR,
    set: ENDPOINTS.QUEUE,
  },
});

/**
 * Get current queue
 */
export async function getQueue(): Promise<QueueResponse> {
  const result = await crudService.list();
  // list() returns an array, but for queue we expect the first item or create a response
  if (Array.isArray(result) && result.length > 0) {
    return result[0];
  }
  // Return empty queue response if list is empty
  return { tracks: [], current_index: 0, total_tracks: 0 };
}

/**
 * Remove track from queue at specified index
 */
export async function removeTrackFromQueue(index: number): Promise<void> {
  await crudService.delete(index);
}

/**
 * Reorder the queue
 * @param newOrder Array of indices in new order
 */
export async function reorderQueue(newOrder: number[]): Promise<void> {
  await crudService.custom('reorder', 'put', { new_order: newOrder });
}

/**
 * Shuffle the queue (keeps current track in place)
 */
export async function shuffleQueue(): Promise<void> {
  await crudService.custom('shuffle', 'post', {});
}

/**
 * Clear the entire queue
 */
export async function clearQueue(): Promise<void> {
  await crudService.custom('clear', 'post', {});
}

/**
 * Set the queue with new tracks
 * @param trackIds Array of track IDs
 * @param startIndex Index to start playing from (default: 0)
 */
export async function setQueue(trackIds: number[], startIndex: number = 0): Promise<void> {
  await crudService.custom('set', 'post', {
    tracks: trackIds,
    start_index: startIndex,
  });
}

export default {
  getQueue,
  removeTrackFromQueue,
  reorderQueue,
  shuffleQueue,
  clearQueue,
  setQueue,
};
