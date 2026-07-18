/**
 * CacheStatsDashboard Component Tests
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Regression test for #4310: the footer's "Auto-refreshing every Xs" label
 * must be derived from CACHE_STATS_REFRESH_INTERVAL_MS (the same constant
 * useCacheStats uses for its refetchInterval), not a separate hardcoded
 * string literal.
 *
 * @copyright (C) 2024 Auralis Team
 * @license GPLv3, see LICENSE for more details
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@/test/test-utils';
import { CacheStatsDashboard } from '../CacheStatsDashboard';
import * as hooks from '@/hooks/shared/useStandardizedAPI';
import { mockCacheStats } from './test-utils';

vi.mock('@/hooks/shared/useStandardizedAPI', async () => {
  const actual = await vi.importActual<typeof hooks>('@/hooks/shared/useStandardizedAPI');
  return {
    ...actual,
    useCacheStats: vi.fn(),
  };
});

describe('CacheStatsDashboard', () => {
  it('derives the auto-refresh footer label from CACHE_STATS_REFRESH_INTERVAL_MS', () => {
    vi.mocked(hooks.useCacheStats).mockReturnValue({
      data: mockCacheStats,
      loading: false,
      error: null,
      refetch: vi.fn().mockResolvedValue(undefined),
    });

    render(<CacheStatsDashboard />);

    const expectedSeconds = hooks.CACHE_STATS_REFRESH_INTERVAL_MS / 1000;
    expect(screen.getByText(`Auto-refreshing every ${expectedSeconds}s`)).toBeInTheDocument();
  });
});
