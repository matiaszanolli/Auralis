/**
 * Cache telemetry hook tests — `useCacheStats` / `useCacheHealth`
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Written for #4693, which retires `StandardizedAPIClient` and moves these two
 * endpoints onto `utils/apiRequest.ts`. #4486 had recorded that this path was
 * untested at both layers, and it was: the only test touching these hooks
 * (`CacheStatsDashboard.test.tsx`) mocks `useCacheStats` wholesale, so nothing
 * exercised the request, the shape guard or the error path.
 *
 * These are characterization tests. They were written and made green against
 * the OLD `CacheAwareAPIClient` implementation *before* the transport swap, so
 * that "the same tests still pass" is real evidence the swap preserved
 * behaviour rather than an assertion about the new code only.
 *
 * @copyright (C) 2024 Auralis Team
 * @license GPLv3, see LICENSE for more details
 */

import { describe, it, expect, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';

import { server } from '@/test/mocks/server';
import { AllProviders } from '@/test/test-utils';
import { useCacheStats, useCacheHealth } from '../useStandardizedAPI';
import { mockCacheStats } from '@/components/shared/__tests__/test-utils';

const mockCacheHealth = {
  healthy: true,
  total_size_mb: 225.0,
  max_size_mb: 500.0,
  usage_percent: 45.0,
};

describe('useCacheStats / useCacheHealth (#4693)', () => {
  beforeEach(() => {
    server.use(
      http.get('/api/cache/stats', () => HttpResponse.json(mockCacheStats)),
      http.get('/api/cache/health', () => HttpResponse.json(mockCacheHealth))
    );
  });

  describe('useCacheStats', () => {
    it('resolves the bare payload the backend actually returns', async () => {
      // The endpoint returns CacheStats directly, with no {status,data}
      // envelope. #4440 fixed a version that gated on the envelope and so
      // resolved null on every 200 OK — this pins the bare shape.
      const { result } = renderHook(() => useCacheStats(), { wrapper: AllProviders });

      await waitFor(() => expect(result.current.loading).toBe(false));

      expect(result.current.data).toEqual(mockCacheStats);
      expect(result.current.error).toBeNull();
    });

    it('reports an error rather than null data when the shape is wrong', async () => {
      server.use(
        http.get('/api/cache/stats', () => HttpResponse.json({ nonsense: true }))
      );

      const { result } = renderHook(() => useCacheStats(), { wrapper: AllProviders });

      await waitFor(() => expect(result.current.error).not.toBeNull());
      expect(result.current.data).toBeNull();
    });

    it('reports an error on an HTTP failure', async () => {
      server.use(
        http.get('/api/cache/stats', () =>
          HttpResponse.json({ detail: 'cache unavailable' }, { status: 503 })
        )
      );

      const { result } = renderHook(() => useCacheStats(), { wrapper: AllProviders });

      await waitFor(() => expect(result.current.error).not.toBeNull());
      expect(result.current.data).toBeNull();
    });

    it('exposes a stable refetch across renders', async () => {
      const { result, rerender } = renderHook(() => useCacheStats(), {
        wrapper: AllProviders,
      });

      await waitFor(() => expect(result.current.loading).toBe(false));
      const first = result.current.refetch;
      rerender();

      expect(result.current.refetch).toBe(first);
    });
  });

  describe('useCacheHealth', () => {
    it('resolves the bare payload and derives the health flags', async () => {
      const { result } = renderHook(() => useCacheHealth(), { wrapper: AllProviders });

      await waitFor(() => expect(result.current.loading).toBe(false));

      expect(result.current.data).toEqual(mockCacheHealth);
      expect(result.current.isHealthy).toBe(true);
      expect(result.current.healthStatus).toBe('healthy');
    });

    it('reports critical when the backend says unhealthy', async () => {
      server.use(
        http.get('/api/cache/health', () =>
          HttpResponse.json({ ...mockCacheHealth, healthy: false })
        )
      );

      const { result } = renderHook(() => useCacheHealth(), { wrapper: AllProviders });

      await waitFor(() => expect(result.current.loading).toBe(false));

      expect(result.current.isHealthy).toBe(false);
      expect(result.current.healthStatus).toBe('critical');
    });

    it('reports critical, not healthy, while the request is failing', async () => {
      // `healthy` defaults to false when data is null, so a failed request
      // must not read as a healthy cache.
      server.use(
        http.get('/api/cache/health', () => HttpResponse.json({ bad: 'shape' }))
      );

      const { result } = renderHook(() => useCacheHealth(), { wrapper: AllProviders });

      await waitFor(() => expect(result.current.error).not.toBeNull());

      expect(result.current.isHealthy).toBe(false);
      expect(result.current.healthStatus).toBe('critical');
    });
  });
});
