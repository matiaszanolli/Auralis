/**
 * Queue Management Service
 *
 * Provides API functions for manipulating the playback queue:
 * - Remove tracks from queue
 * - Reorder queue
 * - Shuffle queue
 * - Clear queue
 */

const API_BASE = 'http://localhost:8765/api';

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
  const response = await fetch(`${API_BASE}/player/queue`);

  if (!response.ok) {
    throw new Error(`Failed to get queue: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Remove track from queue at specified index
 */
export async function removeTrackFromQueue(index: number): Promise<void> {
  const response = await fetch(`${API_BASE}/player/queue/${index}`, {
    method: 'DELETE',
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to remove track from queue');
  }
}

/**
 * Reorder the queue
 * @param newOrder Array of indices in new order
 */
export async function reorderQueue(newOrder: number[]): Promise<void> {
  const response = await fetch(`${API_BASE}/player/queue/reorder`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ new_order: newOrder }),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to reorder queue');
  }
}

/**
 * Shuffle the queue (keeps current track in place)
 */
export async function shuffleQueue(): Promise<void> {
  const response = await fetch(`${API_BASE}/player/queue/shuffle`, {
    method: 'POST',
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to shuffle queue');
  }
}

/**
 * Clear the entire queue
 */
export async function clearQueue(): Promise<void> {
  const response = await fetch(`${API_BASE}/player/queue/clear`, {
    method: 'POST',
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to clear queue');
  }
}

/**
 * Set the queue with new tracks
 * @param trackIds Array of track IDs
 * @param startIndex Index to start playing from (default: 0)
 */
export async function setQueue(trackIds: number[], startIndex: number = 0): Promise<void> {
  const response = await fetch(`${API_BASE}/player/queue`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      tracks: trackIds,
      start_index: startIndex,
    }),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to set queue');
  }
}

export default {
  getQueue,
  removeTrackFromQueue,
  reorderQueue,
  shuffleQueue,
  clearQueue,
  setQueue,
};
