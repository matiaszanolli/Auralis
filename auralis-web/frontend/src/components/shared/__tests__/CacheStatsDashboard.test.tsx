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

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen } from '@/test/test-utils';
import { CacheStatsDashboard } from '../CacheStatsDashboard';
import * as hooks from '@/hooks/shared/useStandardizedAPI';
import { mockCacheStats } from './test-utils';
import { TRACK_CACHE_ROW_HEIGHT } from '../CacheStatsDashboard/TrackCacheList';

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

// ============================================================================
// Per-track list virtualization (#4471)
// ============================================================================
//
// The per-track rows were a plain Object.entries().map() inside a fixed-height
// scroll container — one DOM node per cached track, with no windowing, unlike
// TrackList/QueuePanel. The cache track count is bounded by disk size rather
// than by anything the UI controls, so it can far exceed what is on screen.

describe('CacheStatsDashboard – per-track list virtualization (#4471)', () => {
  // jsdom has no layout: every element reports offsetWidth/offsetHeight of 0.
  // @tanstack/virtual-core measures the scroll element with
  // `getRect(el) => ({ width: el.offsetWidth, height: el.offsetHeight })`, so a
  // zero-height viewport makes the virtualizer mount NO rows — which would make
  // a "few rows rendered" assertion pass vacuously. Give elements the
  // component's real 300px viewport so the window under test is genuine.
  //
  // (Note this is offsetHeight, not getBoundingClientRect — stubbing the latter
  // has no effect on this library.)
  const VIEWPORT = 300;
  let originalOffsetHeight: PropertyDescriptor | undefined;

  beforeEach(() => {
    originalOffsetHeight = Object.getOwnPropertyDescriptor(
      HTMLElement.prototype,
      'offsetHeight'
    );
    Object.defineProperty(HTMLElement.prototype, 'offsetHeight', {
      configurable: true,
      get() {
        return VIEWPORT;
      },
    });
  });

  afterEach(() => {
    if (originalOffsetHeight) {
      Object.defineProperty(HTMLElement.prototype, 'offsetHeight', originalOffsetHeight);
    } else {
      delete (HTMLElement.prototype as unknown as Record<string, unknown>).offsetHeight;
    }
  });

  function mockWithTracks(count: number) {
    const tracks: Record<string, { track_id: number; completion_percent: number; fully_cached: boolean }> = {};
    for (let i = 0; i < count; i++) {
      tracks[String(i)] = {
        track_id: i,
        completion_percent: (i % 100),
        fully_cached: i % 2 === 0,
      };
    }
    vi.mocked(hooks.useCacheStats).mockReturnValue({
      data: { ...mockCacheStats, tracks },
      loading: false,
      error: null,
      refetch: vi.fn().mockResolvedValue(undefined),
    });
    return tracks;
  }

  it('renders only a windowed subset of rows for a large cache', () => {
    mockWithTracks(500);

    render(<CacheStatsDashboard showTracks />);

    const rows = screen.getAllByTestId('track-cache-row');
    // Unvirtualized this was 500 nodes. The exact window depends on the
    // measured viewport, so assert the property that matters: it is bounded
    // and far below the entry count, not an exact count.
    expect(rows.length).toBeGreaterThan(0);
    expect(rows.length).toBeLessThan(100);
  });

  it('sizes the spacer to the full entry count, so the scrollbar is honest', () => {
    mockWithTracks(500);

    render(<CacheStatsDashboard showTracks />);

    const list = screen.getByRole('list', { name: 'Per-track cache status' });
    // 500 rows × the fixed row height — the virtualizer reports the full
    // scrollable extent even though only a window is mounted.
    expect(parseInt(list.style.height, 10)).toBe(500 * TRACK_CACHE_ROW_HEIGHT);
  });

  it('still renders every row when the cache is small', () => {
    mockWithTracks(3);

    render(<CacheStatsDashboard showTracks />);

    expect(screen.getAllByTestId('track-cache-row')).toHaveLength(3);
  });

  it('renders nothing but the container for an empty cache', () => {
    mockWithTracks(0);

    render(<CacheStatsDashboard showTracks />);

    expect(screen.queryAllByTestId('track-cache-row')).toHaveLength(0);
  });
});
