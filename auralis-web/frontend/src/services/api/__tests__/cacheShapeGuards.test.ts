/**
 * Shape guards for the two cache-telemetry endpoints (#4440)
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * These guards outlived `StandardizedAPIClient`, which #4693 retired. They are
 * now passed to `apiRequest`'s `validate` option by
 * `hooks/shared/useStandardizedAPI.ts` instead of being called from the
 * client's `unwrapCachePayload`, so the contract they enforce is unchanged and
 * still needs direct coverage.
 *
 * The contract: `/api/cache/stats` and `/api/cache/health` return their payload
 * BARE — no `{status,data}` envelope, and health carries no `timestamp`. #4440
 * fixed a version that gated on the envelope and therefore resolved `null` on
 * every 200 OK. A guard that accepted too much would bring that back silently.
 *
 * @copyright (C) 2024 Auralis Team
 * @license GPLv3, see LICENSE for more details
 */

import { describe, it, expect } from 'vitest';

import { isCacheStatsShape, isCacheHealthShape } from '../standardizedAPIClient';

const bareStats = {
  tier1: { chunks: 4, size_mb: 6, hits: 150, misses: 10, hit_rate: 0.938 },
  tier2: { chunks: 146, size_mb: 219, hits: 1350, misses: 90, hit_rate: 0.937 },
  overall: { total_chunks: 150, total_size_mb: 225, total_hits: 1500, total_misses: 100 },
};

const bareHealth = {
  healthy: true,
  tier1_size_mb: 6,
  tier2_size_mb: 200,
  total_size_mb: 206,
  // no `timestamp` — the endpoint does not emit one
};

describe('isCacheStatsShape', () => {
  it('accepts the bare payload the endpoint actually returns', () => {
    expect(isCacheStatsShape(bareStats)).toBe(true);
  });

  it.each([
    ['null', null],
    ['undefined', undefined],
    ['a string', 'stats'],
    ['a number', 42],
    ['an empty object', {}],
    ['missing overall', { tier1: {}, tier2: {} }],
    ['a null tier', { tier1: null, tier2: {}, overall: {} }],
  ])('rejects %s', (_label, value) => {
    expect(isCacheStatsShape(value)).toBe(false);
  });

  it('rejects an enveloped payload — the envelope is not what the endpoint sends', () => {
    expect(isCacheStatsShape({ status: 'success', data: bareStats })).toBe(false);
  });
});

describe('isCacheHealthShape', () => {
  it('accepts the bare payload, with no timestamp', () => {
    expect(isCacheHealthShape(bareHealth)).toBe(true);
  });

  it.each([
    ['null', null],
    ['undefined', undefined],
    ['an empty object', {}],
    ['a non-boolean healthy', { healthy: 'yes', total_size_mb: 1 }],
    ['a non-numeric total_size_mb', { healthy: true, total_size_mb: '206' }],
    ['missing total_size_mb', { healthy: true }],
  ])('rejects %s', (_label, value) => {
    expect(isCacheHealthShape(value)).toBe(false);
  });

  it('accepts healthy: false — unhealthy is a valid answer, not a bad shape', () => {
    expect(isCacheHealthShape({ ...bareHealth, healthy: false })).toBe(true);
  });
});
