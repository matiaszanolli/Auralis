/**
 * TrackGridView Tests (issue #3928)
 *
 * Verifies that:
 * 1. The non-virtualized fallback (unmeasurable container, jsdom default)
 *    still renders every track and only stamps the entry-animation style on
 *    the first 10 items.
 * 2. Once the scroll container and width are measurable, row-based
 *    virtualization bounds rendered TrackCard count well below the total
 *    track count for a large library.
 */

import { afterEach, describe, expect, it, vi } from 'vitest';
import { render, waitFor } from '@testing-library/react';
import { TrackGridView } from '../TrackGridView';
import type { LibraryTrack } from '@/types/domain';

function makeTrack(i: number): LibraryTrack {
  return {
    id: i,
    title: `Track ${i}`,
    artist: `Artist ${i}`,
    album: `Album ${i}`,
    duration: 180,
    filepath: `/music/track${i}.flac`,
  } as LibraryTrack;
}

function makeTracks(count: number): LibraryTrack[] {
  return Array.from({ length: count }, (_, i) => makeTrack(i + 1));
}

const noop = async () => {};

const baseProps = {
  hasMore: false,
  onTrackPlay: vi.fn(),
  onRemoveTrack: noop,
  onReorderQueue: noop,
  onShuffleQueue: noop,
  onClearQueue: noop,
};

/** Mirrors the mocking pattern in TrackList.virtualization.test.tsx: the
 * virtualizer measures via both getBoundingClientRect and ResizeObserver. */
function installMeasurableViewport(width = 1200, height = 800) {
  vi.spyOn(Element.prototype, 'getBoundingClientRect').mockReturnValue({
    height,
    width,
    top: 0,
    left: 0,
    bottom: height,
    right: width,
    x: 0,
    y: 0,
    toJSON: () => ({}),
  } as DOMRect);

  const MockResizeObserver = class {
    private cb: ResizeObserverCallback;
    constructor(cb: ResizeObserverCallback) {
      this.cb = cb;
    }
    observe(target: Element) {
      this.cb(
        [
          {
            contentRect: { width, height, top: 0, left: 0, bottom: height, right: width, x: 0, y: 0, toJSON: () => ({}) } as DOMRect,
            target,
            borderBoxSize: [{ blockSize: height, inlineSize: width }],
            contentBoxSize: [{ blockSize: height, inlineSize: width }],
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

describe('TrackGridView', () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    document.body.innerHTML = '';
  });

  it('renders every track and only animates the first 10 in the unmeasured fallback path', () => {
    const tracks = makeTracks(15);
    const { container } = render(<TrackGridView tracks={tracks} {...baseProps} />);

    const cards = container.querySelectorAll('.animate-fade-in-up');
    expect(cards.length).toBe(15);

    const animated = Array.from(cards).filter((el) => (el as HTMLElement).style.animationDelay);
    expect(animated.length).toBe(10);
    expect((cards[0] as HTMLElement).style.animationDelay).toBe('0s');
    expect((cards[9] as HTMLElement).style.animationDelay).toBe('0.45s');
    expect((cards[10] as HTMLElement).style.animationDelay).toBe('');
  });

  it('bounds rendered card count via row virtualization for a large track list', async () => {
    const scrollEl = document.createElement('div');
    scrollEl.id = 'app-main-content-scroll';
    document.body.appendChild(scrollEl);

    installMeasurableViewport(1200, 800);

    const tracks = makeTracks(5000);
    const { container } = render(<TrackGridView tracks={tracks} {...baseProps} />);

    await waitFor(() => {
      const cards = container.querySelectorAll('.animate-fade-in-up');
      expect(cards.length).toBeGreaterThan(0);
    });

    const cards = container.querySelectorAll('.animate-fade-in-up');
    // 800px viewport / 320px row + overscan should be a small handful of
    // rows worth of cards — nowhere near the full 5000-track list.
    expect(cards.length).toBeLessThan(100);
  });
});
