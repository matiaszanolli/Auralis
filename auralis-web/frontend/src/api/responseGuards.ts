/**
 * Runtime Response Shape Guards
 *
 * `Response.json()` is `Promise<any>`, so every typed API response in this app
 * is a compile-time-only contract — backend field drift surfaces as a downstream
 * `undefined`/NaN far from its cause rather than as an error at the boundary
 * (#3593, #3976, #4440, #4441 were all found that way, always after visible
 * breakage). These guards close that gap for the highest-traffic endpoints (#4607).
 *
 * Deliberately NOT a schema library. This is a localhost-only desktop app that
 * ships with the one backend it talks to, so full runtime validation would be
 * disproportionate. Each guard checks only the fields consumers actually depend
 * on — enough to catch a renamed, dropped, or retyped field, cheap enough to run
 * on every response.
 *
 * Extends the `isCacheStatsShape`/`isCacheHealthShape` pattern established for
 * #4440 in services/api/standardizedAPIClient.ts.
 *
 * Pass one via the `validate` option on any `apiRequest`-backed call:
 * @example
 * get('/api/player/queue', { validate: isQueueResponseShape });
 */

/** Narrow an unknown value to an indexable object. */
function asObject(v: unknown): Record<string, unknown> | null {
  return v && typeof v === 'object' && !Array.isArray(v)
    ? (v as Record<string, unknown>)
    : null;
}

/**
 * True when `v` is an array whose entries all look like library items —
 * an object carrying a numeric `id`.
 */
function isItemArray(v: unknown): boolean {
  return (
    Array.isArray(v) &&
    v.every((item) => {
      const o = asObject(item);
      return o !== null && typeof o.id === 'number';
    })
  );
}

/**
 * Shape of a paginated library list response under a given collection key.
 *
 * The backend returns `{ tracks: [...], total, offset }` (or `albums`/`artists`),
 * and `useLibraryQuery` also accepts a generic `items` key. Accepts either, so a
 * guard failure means a genuinely unexpected payload, not a naming variant.
 */
function makeListGuard(collectionKey: string) {
  return function isListShape(v: unknown): boolean {
    const o = asObject(v);
    if (!o) return false;

    const collection = o[collectionKey] ?? o.items;
    if (!isItemArray(collection)) return false;

    // `total` is optional across these endpoints, but must be numeric when present.
    if (o.total !== undefined && typeof o.total !== 'number') return false;
    if (o.offset !== undefined && typeof o.offset !== 'number') return false;

    return true;
  };
}

/** `GET /api/library/tracks` — see #4611 for the transformer this feeds. */
export const isTracksListShape = makeListGuard('tracks');

/** `GET /api/library/albums` */
export const isAlbumsListShape = makeListGuard('albums');

/** `GET /api/library/artists` */
export const isArtistsListShape = makeListGuard('artists');

/**
 * `GET /api/player/queue`.
 *
 * This endpoint returns a bare object, never an array — the assumption that it
 * returned an array is exactly what made `getQueue()` discard every real
 * response for a hardcoded empty queue (#4441). Guarding it means that class of
 * mismatch fails loudly at the boundary instead of rendering an empty queue.
 */
export function isQueueResponseShape(v: unknown): boolean {
  const o = asObject(v);
  if (!o) return false;
  if (!isItemArray(o.tracks)) return false;
  if (o.current_index !== undefined && typeof o.current_index !== 'number') return false;
  if (o.track_count !== undefined && typeof o.track_count !== 'number') return false;
  // #4787: shuffle_enabled is the one true field name QueueManager emits — a
  // wrong-typed value here is the same class of drift that let useQueueFetch
  // silently read a phantom is_shuffled/isShuffled key for months.
  if (o.shuffle_enabled !== undefined && typeof o.shuffle_enabled !== 'boolean') return false;
  return true;
}

/** `GET /api/artists/{id}/tracks` — consumers read `tracks` and `name`. */
export function isArtistTracksResponseShape(v: unknown): boolean {
  const o = asObject(v);
  if (!o) return false;
  if (typeof o.id !== 'number') return false;
  if (typeof o.name !== 'string') return false;
  return isItemArray(o.tracks);
}

/** A single playlist — consumers read `id`, `name` and `track_count`. */
export function isPlaylistShape(v: unknown): boolean {
  const o = asObject(v);
  if (!o) return false;
  if (typeof o.id !== 'number') return false;
  if (typeof o.name !== 'string') return false;
  if (o.track_count !== undefined && typeof o.track_count !== 'number') return false;
  return true;
}

/**
 * `GET /api/playlists`.
 *
 * Accepts a bare array or a `{ playlists: [...] }` envelope — the factory's
 * `list()` is typed `Promise<T[]>` while several endpoints return an object,
 * the same mismatch class as #4441.
 */
export function isPlaylistsListShape(v: unknown): boolean {
  if (Array.isArray(v)) return v.every(isPlaylistShape);
  const o = asObject(v);
  if (!o) return false;
  const collection = o.playlists ?? o.items;
  return Array.isArray(collection) && collection.every(isPlaylistShape);
}

/**
 * `GET /api/settings`.
 *
 * Checks only the handful of fields consumers branch on; the settings payload
 * is broad and mostly optional, so a strict check would be brittle.
 */
export function isUserSettingsShape(v: unknown): boolean {
  if (Array.isArray(v)) return v.every(isUserSettingsShape);
  const o = asObject(v);
  if (!o) return false;
  if (o.scan_folders !== undefined && !Array.isArray(o.scan_folders)) return false;
  if (o.auto_scan !== undefined && typeof o.auto_scan !== 'boolean') return false;
  if (o.crossfade_enabled !== undefined && typeof o.crossfade_enabled !== 'boolean') return false;
  return true;
}

/**
 * `GET /api/player/status` — the player state consumers poll.
 *
 * Only `state` is required; position/duration are absent before a track loads.
 */
export function isPlayerStatusShape(v: unknown): boolean {
  const o = asObject(v);
  if (!o) return false;
  if (typeof o.state !== 'string' && typeof o.status !== 'string') return false;
  if (o.position !== undefined && typeof o.position !== 'number') return false;
  if (o.duration !== undefined && typeof o.duration !== 'number') return false;
  return true;
}
