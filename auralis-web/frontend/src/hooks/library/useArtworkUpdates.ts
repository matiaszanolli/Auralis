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
 *
 * #3575: Previously each consumer (AlbumCard, AlbumArt) installed its own
 * `artwork_updated` subscription instance, so a 500-album grid produced 500 WS
 * callbacks per broadcast, each filtering for its own `album_id` after the O(n)
 * dispatch. The new design installs a single global subscription (refcounted
 * across consumers) that maintains a `Map<albumId, revision>`. Consumers read
 * their slot via `useSyncExternalStore` and only re-render when their album's
 * counter advances. The subscription is backed by WebSocketContext (#4380).
 */

import { useCallback, useSyncExternalStore } from 'react';
import { createSharedSubscription } from '@/hooks/websocket/useWebSocketMessages';
import type { ArtworkUpdatedMessage } from '@/types/websocket';

// ----- Module-level revision store -----
const revisionMap: Map<number, number> = new Map();
const albumListeners: Map<number, Set<() => void>> = new Map();

function bumpRevision(albumId: number): void {
  const next = (revisionMap.get(albumId) ?? 0) + 1;
  revisionMap.set(albumId, next);
  const listeners = albumListeners.get(albumId);
  if (listeners) {
    for (const listener of listeners) listener();
  }
}

/**
 * Re-fetch every artwork this session has shown or revised, after a WebSocket outage (#6581).
 * An `artwork_updated` frame missed while disconnected named an album this client cannot know,
 * so all of them get a fresh cache-busting revision.
 */
export function refreshAllArtwork(): void {
  for (const albumId of new Set([...revisionMap.keys(), ...albumListeners.keys()])) bumpRevision(albumId);
}

function getRevisionSnapshot(albumId: number): number {
  return revisionMap.get(albumId) ?? 0;
}

function subscribeToAlbum(albumId: number, listener: () => void): () => void {
  let listeners = albumListeners.get(albumId);
  if (!listeners) {
    listeners = new Set();
    albumListeners.set(albumId, listeners);
  }
  listeners.add(listener);
  return () => {
    listeners?.delete(listener);
    if (listeners && listeners.size === 0) {
      albumListeners.delete(albumId);
    }
  };
}

// ----- Single global WS subscription, refcounted across consumers -----
// Installed once however many album cards mount (a 500-album grid must not create 500 WS
// subscriptions, #3575), backed by WebSocketContext (#4380) through the shared helper (#6633).
function handleArtworkMessage(msg: ArtworkUpdatedMessage): void {
  // Routed by message type, so `msg` is an artwork_updated frame; the payload
  // check guards a malformed frame off the wire.
  if (msg.data && typeof msg.data.album_id === 'number') {
    bumpRevision(msg.data.album_id);
  }
}

const artworkSubscription = createSharedSubscription(['artwork_updated'], handleArtworkMessage);

/**
 * Returns a revision counter for the given album's artwork.
 * Increments whenever an `artwork_updated` WebSocket message arrives
 * for this album, causing a re-render with a cache-busted URL.
 */
export function useArtworkRevision(albumId: number): number {
  artworkSubscription.use();
  // Stable per album: a fresh `subscribe` each render makes React unsubscribe and
  // resubscribe every card in a large grid on every grid re-render (#6428).
  const subscribe = useCallback((listener: () => void) => subscribeToAlbum(albumId, listener), [albumId]);
  return useSyncExternalStore(
    subscribe,
    () => getRevisionSnapshot(albumId),
    () => getRevisionSnapshot(albumId)
  );
}

// Test/debug helpers
export const _internal = {
  revisionMap,
  albumListeners,
  get globalRefCount() {
    return artworkSubscription.refCount;
  },
  reset() {
    revisionMap.clear();
    albumListeners.clear();
    artworkSubscription.reset();
  },
};
