/**
 * TrackListViewContent roving-focus retry is bounded and cancellable (#5634)
 *
 * tryFocus re-queued requestAnimationFrame for as long as the target row was
 * missing — an unbounded ~60 Hz loop when the list unmounted mid-navigation
 * or the row never mounted. The retry is now capped (MAX_FOCUS_RETRY_FRAMES)
 * and the pending frame is cancelled in the effect cleanup.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { act } from 'react';
import { fireEvent } from '@testing-library/react';
import { render } from '@/test/test-utils';
import type { LibraryTrack } from '@/types/domain';
import { TrackListViewContent } from '../TrackListViewContent';

vi.mock('@tanstack/react-virtual', () => ({
  useVirtualizer: (opts: { count: number }) => ({
    // Deliberately render fewer rows than exist: indices at/after the cut
    // never mount a row, which is what used to drive the retry loop forever.
    getVirtualItems: () =>
      Array.from({ length: Math.min(opts.count, 2) }, (_, i) => ({
        index: i,
        size: 56,
        start: i * 56,
      })),
    getTotalSize: () => opts.count * 56,
    options: { scrollMargin: 0 },
    scrollToIndex: vi.fn(),
  }),
}));

function makeTrack(id: number): LibraryTrack {
  return {
    id,
    title: `Track ${id}`,
    artist: `Artist ${id}`,
    album: 'Album',
    duration: 180,
    filepath: `/music/${id}.flac`,
  } as LibraryTrack;
}

const tracks = [makeTrack(1), makeTrack(2), makeTrack(3), makeTrack(4), makeTrack(5)];

function renderList() {
  return render(
    <TrackListViewContent
      tracks={tracks}
      hasMore={false}
      isLoadingMore={false}
      totalTracks={tracks.length}
      isPlaying={false}
      selectedTracks={new Set()}
      isSelected={() => false}
      onToggleSelect={vi.fn()}
      onTrackPlay={vi.fn()}
      onPause={vi.fn()}
      onEditMetadata={vi.fn()}
    />
  );
}

describe('TrackListViewContent focus retry bounds (#5634)', () => {
  let rafCallbacks: FrameRequestCallback[];
  let rafSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    rafCallbacks = [];
    rafSpy = vi.spyOn(window, 'requestAnimationFrame').mockImplementation((cb) => {
      rafCallbacks.push(cb);
      return rafCallbacks.length;
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  const flushFrames = async (n: number) => {
    for (let i = 0; i < n; i++) {
      const cbs = rafCallbacks.splice(0);
      if (cbs.length === 0) return;
      await act(async () => {
        cbs.forEach((cb) => cb(16));
      });
    }
  };

  it('gives up after a bounded number of frames when the row never mounts', async () => {
    const { container } = renderList();

    // Navigate to the last row (index 4), which the mock never renders.
    fireEvent.keyDown(container.querySelector('[role="listbox"]')!, { key: 'End' });
    await flushFrames(20);

    expect(rafSpy).toHaveBeenCalledTimes(5); // MAX_FOCUS_RETRY_FRAMES, not unbounded
  });

  it('cancels the pending retry frame when the effect is torn down', async () => {
    const cancelSpy = vi.spyOn(window, 'cancelAnimationFrame').mockImplementation(() => {});
    const { container, unmount } = renderList();

    fireEvent.keyDown(container.querySelector('[role="listbox"]')!, { key: 'End' });
    expect(rafCallbacks.length).toBeGreaterThan(0);

    unmount();
    expect(cancelSpy).toHaveBeenCalled();
  });
});
