/**
 * apiRequest runtime shape-guard tests (#4607)
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * `Response.json()` is `Promise<any>`, so before #4607 every typed API response
 * was a compile-time-only contract — backend field drift surfaced downstream as
 * `undefined`/NaN rather than at the boundary (#3593, #3976, #4440, #4441).
 *
 * These drive the REAL `apiRequest()` against a mocked `global.fetch`, asserting
 * the optional `validate` guard rejects a drifted payload, leaves the happy path
 * untouched, and never runs on the 204 No Content path.
 *
 * WIRING: intentionally does NOT `vi.mock('@/utils/apiRequest')`.
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { apiRequest, get, APIRequestError } from '../apiRequest';
import {
  isQueueResponseShape,
  isTracksListShape,
  isArtistTracksResponseShape,
  isPlaylistsListShape,
} from '@/api/responseGuards';

function makeResponse(init: {
  ok: boolean;
  status: number;
  json?: () => Promise<unknown>;
}): Response {
  return {
    ok: init.ok,
    status: init.status,
    statusText: '',
    json: init.json ?? (async () => ({})),
  } as unknown as Response;
}

describe('apiRequest validate option (#4607)', () => {
  beforeEach(() => {
    global.fetch = vi.fn();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('resolves unchanged when the guard passes (no happy-path behaviour change)', async () => {
    const payload = { tracks: [{ id: 1, title: 'x' }], total: 1 };
    (global.fetch as any).mockResolvedValue(
      makeResponse({ ok: true, status: 200, json: async () => payload })
    );

    const result = await get('/api/library/tracks', { validate: isTracksListShape });

    expect(result).toEqual(payload);
  });

  it('throws APIRequestError naming the endpoint when the guard fails', async () => {
    // `tracks` renamed — exactly the drift class this guard exists to catch.
    (global.fetch as any).mockResolvedValue(
      makeResponse({ ok: true, status: 200, json: async () => ({ items_renamed: [] }) })
    );

    await expect(
      get('/api/library/tracks', { validate: isTracksListShape })
    ).rejects.toThrow(APIRequestError);

    await expect(
      get('/api/library/tracks', { validate: isTracksListShape })
    ).rejects.toThrow(/\/api\/library\/tracks/);
  });

  it('does NOT invoke the guard on a 204 No Content response', async () => {
    const guard = vi.fn(() => false);
    (global.fetch as any).mockResolvedValue(makeResponse({ ok: true, status: 204 }));

    const result = await apiRequest('/api/something', { validate: guard });

    expect(guard).not.toHaveBeenCalled();
    expect(result).toBeUndefined();
  });

  it('behaves exactly as before when no guard is supplied', async () => {
    const drifted = { totally: 'unexpected' };
    (global.fetch as any).mockResolvedValue(
      makeResponse({ ok: true, status: 200, json: async () => drifted })
    );

    // No validate → no runtime check, same as pre-#4607.
    await expect(get('/api/library/tracks')).resolves.toEqual(drifted);
  });

  it('surfaces the guard failure as a catchable error, not an unhandled rejection', async () => {
    (global.fetch as any).mockResolvedValue(
      makeResponse({ ok: true, status: 200, json: async () => ({ bad: true }) })
    );

    let caught: unknown = null;
    try {
      await get('/api/player/queue', { validate: isQueueResponseShape });
    } catch (e) {
      caught = e;
    }

    expect(caught).toBeInstanceOf(APIRequestError);
    expect((caught as APIRequestError).detail).toMatch(/backend contract changed/i);
  });
});

describe('responseGuards (#4607)', () => {
  it('isQueueResponseShape accepts the real bare-object queue payload', () => {
    expect(
      isQueueResponseShape({
        tracks: [{ id: 1, title: 't', duration: 1, filepath: '/a' }],
        current_index: 0,
        track_count: 1,
      })
    ).toBe(true);
  });

  it('isQueueResponseShape rejects an array — the #4441 mismatch', () => {
    expect(isQueueResponseShape([{ tracks: [] }])).toBe(false);
  });

  it('isQueueResponseShape rejects a wrong-typed current_index', () => {
    expect(isQueueResponseShape({ tracks: [], current_index: 'first' })).toBe(false);
  });

  it('isQueueResponseShape accepts a boolean shuffle_enabled (#4787)', () => {
    expect(isQueueResponseShape({ tracks: [], shuffle_enabled: true })).toBe(true);
    expect(isQueueResponseShape({ tracks: [], shuffle_enabled: false })).toBe(true);
  });

  it('isQueueResponseShape rejects a wrong-typed shuffle_enabled (#4787)', () => {
    expect(isQueueResponseShape({ tracks: [], shuffle_enabled: 'yes' })).toBe(false);
  });

  it('isQueueResponseShape accepts a missing shuffle_enabled (field is optional)', () => {
    expect(isQueueResponseShape({ tracks: [] })).toBe(true);
  });

  it('isTracksListShape accepts either the named key or the generic items key', () => {
    expect(isTracksListShape({ tracks: [{ id: 1 }] })).toBe(true);
    expect(isTracksListShape({ items: [{ id: 1 }] })).toBe(true);
  });

  it('isTracksListShape rejects entries missing a numeric id', () => {
    expect(isTracksListShape({ tracks: [{ title: 'no id' }] })).toBe(false);
  });

  it('isTracksListShape rejects a non-numeric total', () => {
    expect(isTracksListShape({ tracks: [], total: 'many' })).toBe(false);
  });

  it('isArtistTracksResponseShape requires id, name and a track array', () => {
    expect(
      isArtistTracksResponseShape({ id: 1, name: 'A', tracks: [{ id: 2 }] })
    ).toBe(true);
    expect(isArtistTracksResponseShape({ id: 1, tracks: [] })).toBe(false);
    expect(isArtistTracksResponseShape({ name: 'A', tracks: [] })).toBe(false);
  });

  it('isPlaylistsListShape accepts both a bare array and an envelope', () => {
    expect(isPlaylistsListShape([{ id: 1, name: 'p' }])).toBe(true);
    expect(isPlaylistsListShape({ playlists: [{ id: 1, name: 'p' }] })).toBe(true);
    expect(isPlaylistsListShape({ playlists: [{ id: 1 }] })).toBe(false);
  });

  it('guards reject null and primitives rather than throwing', () => {
    for (const guard of [isQueueResponseShape, isTracksListShape, isArtistTracksResponseShape]) {
      expect(guard(null)).toBe(false);
      expect(guard(undefined)).toBe(false);
      expect(guard('a string')).toBe(false);
      expect(guard(42)).toBe(false);
    }
  });
});
