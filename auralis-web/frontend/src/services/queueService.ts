/**
 * Queue Management Service
 *
 * Provides API functions for manipulating the playback queue:
 * - Remove tracks from queue
 * - Reorder queue
 * - Shuffle queue
 * - Clear queue
 */

import { get, post, put, del } from '../utils/apiRequest';
import { ENDPOINTS } from '../config/api';

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

/**
 * Get current queue
 */
export async function getQueue(): Promise<QueueResponse> {
  return get(ENDPOINTS.QUEUE);
}

/**
 * Remove track from queue at specified index
 */
export async function removeTrackFromQueue(index: number): Promise<void> {
  await del(ENDPOINTS.QUEUE_TRACK(index));
}

/**
 * Reorder the queue
 * @param newOrder Array of indices in new order
 */
export async function reorderQueue(newOrder: number[]): Promise<void> {
  await put(ENDPOINTS.QUEUE_REORDER, { new_order: newOrder });
}

/**
 * Shuffle the queue (keeps current track in place)
 */
export async function shuffleQueue(): Promise<void> {
  await post(ENDPOINTS.QUEUE_SHUFFLE);
}

/**
 * Clear the entire queue
 */
export async function clearQueue(): Promise<void> {
  await post(ENDPOINTS.QUEUE_CLEAR);
}

/**
 * Set the queue with new tracks
 * @param trackIds Array of track IDs
 * @param startIndex Index to start playing from (default: 0)
 */
export async function setQueue(trackIds: number[], startIndex: number = 0): Promise<void> {
  await post(ENDPOINTS.QUEUE, {
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
