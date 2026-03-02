/**
 * TrackList Virtualization Tests (issue #2348)
 *
 * Verifies that:
 * 1. With 10,000 tracks loaded, fewer than 50 DOM nodes are rendered.
 * 2. The inner div height equals 10,000 * ROW_HEIGHT (full virtual height).
 * 3. Rendered row count scales with viewport height, not list length.
 * 4. fetchMore is triggered when the last virtual item is in view.
 * 5. Error and empty states render without virtualization interference.
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

// ============================================================================
// Mock dependencies
// ============================================================================

const mockFetchMore = vi.fn().mockResolvedValue(undefined);

vi.mock('@/hooks/library/useLibraryQuery', () => ({
  useTracksQuery: vi.fn(),
}));

import { useTracksQuery } from '@/hooks/library/useLibraryQuery';
import { TrackList } from '../TrackList';

// ============================================================================
// Helpers
// ============================================================================

const ROW_HEIGHT = 56; // must match the constant in TrackList.tsx

function makeTrack(i: number) {
  return {
    id: i,
    title: `Track ${i}`,
    artist: `Artist ${Math.floor(i / 10)}`,
    album: `Album ${Math.floor(i / 20)}`,
    duration: 180 + (i % 60),
    file_path: `/music/track${i}.flac`,
    created_at: new Date().toISOString(),
  };
}

function makeTracks(count: number) {
  return Array.from({ length: count }, (_, i) => makeTrack(i));
}

/**
 * ResizeObserver mock that fires the callback synchronously when observe() is
 * called.  Replaced globally before each test so the virtualizer always gets
 * a deterministic viewport size.
 */
function installResizeObserver(viewportHeight: number) {
  // The virtualizer (v3) reads element size via two paths:
  //   1. element.getBoundingClientRect() — synchronous, on first scroll-element set
  //   2. ResizeObserver callback — prefers entry.borderBoxSize[0].blockSize,
  //      falls back to getBoundingClientRect() if borderBoxSize is empty
  //
  // We must mock BOTH so the virtualizer computes the correct range.
  vi.spyOn(Element.prototype, 'getBoundingClientRect').mockReturnValue({
    height: viewportHeight,
    width: 800,
    top: 0,
    left: 0,
    bottom: viewportHeight,
    right: 800,
    x: 0,
    y: 0,
    toJSON: () => ({}),
  } as DOMRect);

  const MockResizeObserver = class {
    private cb: ResizeObserverCallback;

    constructor(cb: ResizeObserverCallback) {
      this.cb = cb;
    }

    observe(target: Element, _options?: ResizeObserverOptions) {
      this.cb(
        [
          {
            contentRect: {
              height: viewportHeight,
              width: 800,
              top: 0,
              left: 0,
              bottom: viewportHeight,
              right: 800,
              x: 0,
              y: 0,
              toJSON: () => ({}),
            } as DOMRect,
            target,
            borderBoxSize: [{ blockSize: viewportHeight, inlineSize: 800 }],
            contentBoxSize: [{ blockSize: viewportHeight, inlineSize: 800 }],
            devicePixelContentBoxSize: [],
          },
        ],
        this as unknown as ResizeObserver
      );
    }

    unobserve() {}
    disconnect() {}
  };
  vi.stubGlobal('ResizeObserver', MockResizeObserver);
}

/** Render and wait until at least one button row is visible. */
async function renderAndWaitForRows(props: Parameters<typeof TrackList>[0] = {}) {
  const result = render(<TrackList {...props} />);
  await waitFor(() => {
    const rows = result.container.querySelectorAll('[role="button"]');
    expect(rows.length).toBeGreaterThan(0);
  });
  return result;
}

// ============================================================================
// Tests
// ============================================================================

describe('TrackList — virtualization', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Restore resolved value after clearAllMocks wipes the implementation
    mockFetchMore.mockResolvedValue(undefined);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  // --------------------------------------------------------------------------
  // 1. Primary acceptance criterion: < 50 DOM nodes for 10,000 tracks
  // --------------------------------------------------------------------------

  it('renders fewer than 50 row nodes for 10,000 tracks (600px viewport)', async () => {
    installResizeObserver(600);

    vi.mocked(useTracksQuery).mockReturnValue({
      data: makeTracks(10_000),
      isLoading: false,
      error: null,
      hasMore: false,
      fetchMore: mockFetchMore,
    } as any);

    const { container } = await renderAndWaitForRows();

    const rows = container.querySelectorAll('[role="button"]');
    // 600px / 56px ≈ 10.7 visible rows + 5 overscan = ~16; must be < 50
    expect(rows.length).toBeLessThan(50);
  });

  // --------------------------------------------------------------------------
  // 2. Inner container height = total virtual height
  // --------------------------------------------------------------------------

  it('sets inner container height to tracks.length * ROW_HEIGHT', async () => {
    installResizeObserver(600);

    const TRACK_COUNT = 10_000;
    vi.mocked(useTracksQuery).mockReturnValue({
      data: makeTracks(TRACK_COUNT),
      isLoading: false,
      error: null,
      hasMore: false,
      fetchMore: mockFetchMore,
    } as any);

    const { container } = await renderAndWaitForRows();

    // The inner div with position:relative holds total virtual height
    const inner = container.querySelector('[style*="position: relative"]') as HTMLElement;
    expect(inner).toBeTruthy();
    const heightPx = parseInt(inner.style.height, 10);
    expect(heightPx).toBe(TRACK_COUNT * ROW_HEIGHT);
  });

  // --------------------------------------------------------------------------
  // 3. Rendered count scales with viewport, not list size
  // --------------------------------------------------------------------------

  it('renders more rows for a taller viewport', async () => {
    const TRACK_COUNT = 10_000;

    vi.mocked(useTracksQuery).mockReturnValue({
      data: makeTracks(TRACK_COUNT),
      isLoading: false,
      error: null,
      hasMore: false,
      fetchMore: mockFetchMore,
    } as any);

    // Small viewport
    installResizeObserver(200);
    const { container: smallContainer, unmount: unmountSmall } = await renderAndWaitForRows();
    const smallCount = smallContainer.querySelectorAll('[role="button"]').length;
    unmountSmall();

    // Large viewport
    installResizeObserver(1200);
    const { container: largeContainer } = await renderAndWaitForRows();
    const largeCount = largeContainer.querySelectorAll('[role="button"]').length;

    expect(largeCount).toBeGreaterThan(smallCount);
    // Neither should be anywhere near the full list size
    expect(smallCount).toBeLessThan(50);
    expect(largeCount).toBeLessThan(50);
  });

  // --------------------------------------------------------------------------
  // 4. Track click triggers onTrackSelect with correct track
  // --------------------------------------------------------------------------

  it('calls onTrackSelect with the correct track when a row is clicked', async () => {
    installResizeObserver(600);

    const tracks = makeTracks(100);
    vi.mocked(useTracksQuery).mockReturnValue({
      data: tracks,
      isLoading: false,
      error: null,
      hasMore: false,
      fetchMore: mockFetchMore,
    } as any);

    const onSelect = vi.fn();
    await renderAndWaitForRows({ onTrackSelect: onSelect });

    const firstRow = screen.getAllByRole('button')[0];
    await userEvent.click(firstRow);

    expect(onSelect).toHaveBeenCalledTimes(1);
    expect(onSelect).toHaveBeenCalledWith(tracks[0]);
  });

  // --------------------------------------------------------------------------
  // 5. Error state renders without crash
  // --------------------------------------------------------------------------

  it('renders error state when query fails', () => {
    installResizeObserver(600);

    vi.mocked(useTracksQuery).mockReturnValue({
      data: [],
      isLoading: false,
      error: new Error('Network error'),
      hasMore: false,
      fetchMore: mockFetchMore,
    } as any);

    render(<TrackList />);
    expect(screen.getByText('Failed to load tracks')).toBeInTheDocument();
  });

  // --------------------------------------------------------------------------
  // 6. Empty state renders when no tracks
  // --------------------------------------------------------------------------

  it('renders empty state when track list is empty', () => {
    installResizeObserver(600);

    vi.mocked(useTracksQuery).mockReturnValue({
      data: [],
      isLoading: false,
      error: null,
      hasMore: false,
      fetchMore: mockFetchMore,
    } as any);

    render(<TrackList />);
    expect(screen.getByText('No tracks found')).toBeInTheDocument();
  });

  // --------------------------------------------------------------------------
  // 7. Loading indicator appears while fetching
  // --------------------------------------------------------------------------

  it('shows loading indicator while isLoading is true', () => {
    installResizeObserver(600);

    vi.mocked(useTracksQuery).mockReturnValue({
      data: makeTracks(5),
      isLoading: true,
      error: null,
      hasMore: true,
      fetchMore: mockFetchMore,
    } as any);

    render(<TrackList />);
    expect(screen.getByText('Loading more tracks...')).toBeInTheDocument();
  });

  // --------------------------------------------------------------------------
  // 8. fetchMore triggered when last virtual item is in view
  // --------------------------------------------------------------------------

  it('calls fetchMore when last loaded track enters the virtual window', async () => {
    // 5 tracks × 56px = 280px total height; 600px viewport shows all → last in view
    installResizeObserver(600);

    vi.mocked(useTracksQuery).mockReturnValue({
      data: makeTracks(5),
      isLoading: false,
      error: null,
      hasMore: true,
      fetchMore: mockFetchMore,
    } as any);

    await renderAndWaitForRows();

    // All 5 tracks are in the virtual window; the fetchMore effect fires
    await waitFor(() => {
      expect(mockFetchMore).toHaveBeenCalled();
    });
  });
});
