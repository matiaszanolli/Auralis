/**
 * FingerprintCache — IndexedDB round-trip, TTL expiry and cleanup (#4478)
 *
 * The 378-line persistence layer behind the fingerprint UI had no tests: the
 * only file that referenced it — `hooks/fingerprint/useFingerprintCache`, since
 * deleted in #4239 — mocked the whole module in its own tests, so nothing ever
 * exercised a real IndexedDB round-trip, the 30-day expiry, or the cleanup
 * sweep. These drive the real class against `fake-indexeddb`, which jsdom does
 * not provide on its own.
 *
 * With that hook gone the cache has no consumer at all, so these tests are now
 * its only exercise. They are kept rather than deleted alongside it: the class
 * is correct, self-contained persistence, and it is what a real client-side
 * fingerprint cache would be built on if one is ever wired up.
 *
 * Each test gets a fresh database and a fresh `FingerprintCache`, because the
 * class caches its `IDBDatabase` handle for the life of the instance.
 */

import 'fake-indexeddb/auto';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { IDBFactory } from 'fake-indexeddb';
import { FingerprintCache, getFingerprintCache } from '../FingerprintCache';
import type { AudioFingerprint } from '@/types/domain';

const DAY_MS = 24 * 60 * 60 * 1000;
const CACHE_TTL_MS = 30 * DAY_MS;

/** Minimal fingerprint payload — the cache is agnostic to the 25 dimensions. */
const fingerprint = (overrides: Partial<AudioFingerprint> = {}) =>
  ({
    tempo: 120,
    energy: 0.8,
    loudness: -9.5,
    ...overrides,
  } as unknown as Omit<AudioFingerprint, 'trackId'>);

/**
 * Fake only `Date`, never the timer queue.
 *
 * fake-indexeddb fires its transaction and request callbacks from
 * `setImmediate`/microtasks, so a full `vi.useFakeTimers()` freezes every
 * IndexedDB operation and the awaits below never resolve.
 */
const useFakeClock = () => vi.useFakeTimers({ toFake: ['Date'] });

let cache: FingerprintCache;

beforeEach(async () => {
  // A brand-new factory wipes every database between tests.
  globalThis.indexedDB = new IDBFactory();
  cache = new FingerprintCache();
  await cache.init();
});

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

describe('round-trip', () => {
  it('stores and reads back a fingerprint', async () => {
    await cache.set(1, fingerprint({ tempo: 128 }));

    const read = await cache.get(1);

    expect(read).toMatchObject({ trackId: 1, tempo: 128 });
  });

  it('returns null for a track that was never cached', async () => {
    expect(await cache.get(999)).toBeNull();
  });

  it('overwrites an existing entry rather than duplicating it', async () => {
    await cache.set(1, fingerprint({ tempo: 100 }));
    await cache.set(1, fingerprint({ tempo: 180 }));

    expect(await cache.get(1)).toMatchObject({ tempo: 180 });
    expect(await cache.getAllKeys()).toEqual([1]);
  });

  it('reports presence via has()', async () => {
    await cache.set(7, fingerprint());

    expect(await cache.has(7)).toBe(true);
    expect(await cache.has(8)).toBe(false);
  });

  it('deletes a single entry, leaving the rest', async () => {
    await cache.set(1, fingerprint());
    await cache.set(2, fingerprint());

    await cache.delete(1);

    expect(await cache.get(1)).toBeNull();
    expect(await cache.get(2)).not.toBeNull();
  });

  it('clears every entry', async () => {
    await cache.set(1, fingerprint());
    await cache.set(2, fingerprint());

    await cache.clear();

    expect(await cache.getAllKeys()).toEqual([]);
  });

  it('survives a new cache instance over the same database', async () => {
    await cache.set(42, fingerprint({ tempo: 90 }));

    const reopened = new FingerprintCache();
    await reopened.init();

    expect(await reopened.get(42)).toMatchObject({ trackId: 42, tempo: 90 });
  });
});

describe('TTL expiry', () => {
  it('evicts an entry older than the 30-day TTL on read', async () => {
    useFakeClock();
    vi.setSystemTime(new Date('2026-01-01T00:00:00Z'));
    await cache.set(1, fingerprint());

    // One day past the TTL.
    vi.setSystemTime(new Date(Date.now() + CACHE_TTL_MS + DAY_MS));

    expect(await cache.get(1)).toBeNull();

    // The read is what removes it — the entry must actually be gone, not just
    // filtered out of this one response.
    vi.useRealTimers();
    await vi.waitFor(async () => {
      expect(await cache.getAllKeys()).toEqual([]);
    });
  });

  it('keeps an entry that is old but still inside the TTL', async () => {
    useFakeClock();
    vi.setSystemTime(new Date('2026-01-01T00:00:00Z'));
    await cache.set(1, fingerprint({ tempo: 111 }));

    // One day short of the TTL.
    vi.setSystemTime(new Date(Date.now() + CACHE_TTL_MS - DAY_MS));

    expect(await cache.get(1)).toMatchObject({ tempo: 111 });
    expect(await cache.getAllKeys()).toEqual([1]);
  });

  it('reports an expired entry as absent via has()', async () => {
    useFakeClock();
    vi.setSystemTime(new Date('2026-01-01T00:00:00Z'));
    await cache.set(1, fingerprint());

    vi.setSystemTime(new Date(Date.now() + CACHE_TTL_MS + DAY_MS));

    expect(await cache.has(1)).toBe(false);
  });
});

describe('cleanup sweep', () => {
  it('counts the entries it evicts and leaves fresh ones alone', async () => {
    useFakeClock();
    vi.setSystemTime(new Date('2026-01-01T00:00:00Z'));
    await cache.set(1, fingerprint());
    await cache.set(2, fingerprint());

    // Two entries age past the TTL; a third is written just before the sweep.
    vi.setSystemTime(new Date(Date.now() + CACHE_TTL_MS + DAY_MS));
    await cache.set(3, fingerprint());

    const deleted = await cache.cleanup();

    expect(deleted).toBe(2);
    expect(await cache.getAllKeys()).toEqual([3]);
  });

  it('reports zero on an empty cache', async () => {
    expect(await cache.cleanup()).toBe(0);
  });

  it('reports zero when nothing has expired', async () => {
    await cache.set(1, fingerprint());
    await cache.set(2, fingerprint());

    expect(await cache.cleanup()).toBe(0);
    expect(await cache.getAllKeys()).toEqual([1, 2]);
  });
});

describe('stats', () => {
  it('returns zeroed stats for an empty cache', async () => {
    expect(await cache.getStats()).toEqual({
      total: 0,
      sizeMB: 0,
      oldestTimestamp: null,
      newestTimestamp: null,
    });
  });

  it('reports totals and the oldest/newest timestamps', async () => {
    useFakeClock();
    const first = new Date('2026-01-01T00:00:00Z');
    vi.setSystemTime(first);
    await cache.set(1, fingerprint());

    const second = new Date(first.getTime() + DAY_MS);
    vi.setSystemTime(second);
    await cache.set(2, fingerprint());

    const stats = await cache.getStats();

    expect(stats.total).toBe(2);
    expect(stats.oldestTimestamp).toBe(first.getTime());
    expect(stats.newestTimestamp).toBe(second.getTime());
    expect(stats.sizeMB).toBeGreaterThan(0);
  });

  it('getSize grows with the number of entries', async () => {
    const empty = await cache.getSize();
    await cache.set(1, fingerprint());
    const oneEntry = await cache.getSize();

    expect(empty).toBe(0);
    expect(oneEntry).toBeGreaterThan(empty);
  });
});

describe('initialization', () => {
  it('is idempotent — concurrent init() calls share one promise', async () => {
    const fresh = new FingerprintCache();
    const openSpy = vi.spyOn(globalThis.indexedDB, 'open');

    await Promise.all([fresh.init(), fresh.init(), fresh.init()]);

    expect(openSpy).toHaveBeenCalledTimes(1);
  });

  it('initializes lazily when an operation runs before init()', async () => {
    const fresh = new FingerprintCache();

    await fresh.set(5, fingerprint({ tempo: 140 }));

    expect(await fresh.get(5)).toMatchObject({ tempo: 140 });
  });

  it('degrades to a no-op cache when IndexedDB is unavailable', async () => {
    const original = globalThis.indexedDB;
    // `init()` checks `'indexedDB' in window` and resolves without a db handle.
    // Every operation must then be inert rather than throwing.
    // @ts-expect-error — deleting a global to model an unsupported browser
    delete globalThis.indexedDB;
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});

    try {
      const unsupported = new FingerprintCache();
      await unsupported.init();

      expect(warnSpy).toHaveBeenCalledWith('IndexedDB not supported in this browser');

      await expect(unsupported.set(1, fingerprint())).resolves.toBeUndefined();
      await expect(unsupported.get(1)).resolves.toBeNull();
      await expect(unsupported.getAllKeys()).resolves.toEqual([]);
      await expect(unsupported.getSize()).resolves.toBe(0);
      await expect(unsupported.cleanup()).resolves.toBe(0);
      await expect(unsupported.getStats()).resolves.toEqual({
        total: 0,
        sizeMB: 0,
        oldestTimestamp: null,
        newestTimestamp: null,
      });
    } finally {
      globalThis.indexedDB = original;
    }
  });
});

describe('getFingerprintCache singleton', () => {
  it('returns the same instance on repeated calls', () => {
    expect(getFingerprintCache()).toBe(getFingerprintCache());
  });
});
