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

import { useEffect, useRef, useSyncExternalStore } from 'react';
import { useWebSocketContext } from '@/contexts/WebSocketContext';
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
// The subscription is installed exactly once regardless of how many album cards
// mount (a 500-album grid must not create 500 WS subscriptions — #3575). It is
// now backed by WebSocketContext (#4380) instead of the retired singleton;
// context.subscribe has stable identity and is available immediately, so no
// manager-ready deferral is needed.
let globalRefCount = 0;
let unsubscribeFromManager: (() => void) | null = null;

function handleArtworkMessage(message: unknown): void {
  // The shared WS context fans out by message type, so we still match
  // before bumping — defensive against future cross-type dispatches.
  const msg = message as Partial<ArtworkUpdatedMessage>;
  if (msg && msg.type === 'artwork_updated' && msg.data && typeof msg.data.album_id === 'number') {
    bumpRevision(msg.data.album_id);
  }
}

function detachGlobalSubscription(): void {
  unsubscribeFromManager?.();
  unsubscribeFromManager = null;
}

function useGlobalArtworkSubscription(): void {
  const { subscribe } = useWebSocketContext();
  // Effect runs once per consumer mount; refcount keeps the single global
  // subscription alive while >=1 consumer is mounted. `subscribe` is identity-
  // stable (context useCallback), so this does not resubscribe on re-render.
  const initialized = useRef(false);
  useEffect(() => {
    if (initialized.current) return; // strict-mode double-invoke guard
    initialized.current = true;
    globalRefCount += 1;
    if (globalRefCount === 1) {
      unsubscribeFromManager = subscribe('artwork_updated', handleArtworkMessage);
    }
    return () => {
      globalRefCount = Math.max(0, globalRefCount - 1);
      if (globalRefCount === 0) {
        detachGlobalSubscription();
      }
      initialized.current = false;
    };
  }, [subscribe]);
}

/**
 * Returns a revision counter for the given album's artwork.
 * Increments whenever an `artwork_updated` WebSocket message arrives
 * for this album, causing a re-render with a cache-busted URL.
 */
export function useArtworkRevision(albumId: number): number {
  useGlobalArtworkSubscription();
  return useSyncExternalStore(
    (listener) => subscribeToAlbum(albumId, listener),
    () => getRevisionSnapshot(albumId),
    () => getRevisionSnapshot(albumId)
  );
}

// Test/debug helpers
export const _internal = {
  revisionMap,
  albumListeners,
  get globalRefCount() {
    return globalRefCount;
  },
  reset() {
    revisionMap.clear();
    albumListeners.clear();
    detachGlobalSubscription();
    globalRefCount = 0;
  },
};
