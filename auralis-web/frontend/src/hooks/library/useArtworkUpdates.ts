/**
 * useArtworkRevision Hook
 *
 * Subscribes to `artwork_updated` WebSocket messages and tracks a per-album
 * revision counter. Components use the revision to cache-bust artwork URLs
 * so the browser fetches fresh artwork instead of serving stale cache.
 *
 * Usage:
 *   const revision = useArtworkRevision(albumId);
 *   const url = revision > 0
 *     ? `/api/albums/${albumId}/artwork?v=${revision}`
 *     : `/api/albums/${albumId}/artwork`;
 */

import { useState } from 'react';
import { useWebSocketSubscription } from '@/hooks/websocket/useWebSocketSubscription';
import type { ArtworkUpdatedMessage } from '@/types/websocket';

/**
 * Returns a revision counter for the given album's artwork.
 * Increments whenever an `artwork_updated` WebSocket message arrives
 * for this album, causing a re-render with a cache-busted URL.
 */
export function useArtworkRevision(albumId: number): number {
  const [revision, setRevision] = useState(0);

  useWebSocketSubscription(['artwork_updated'], (message) => {
    const msg = message as ArtworkUpdatedMessage;
    if (msg.data.album_id === albumId) {
      setRevision((prev) => prev + 1);
    }
  });

  return revision;
}
