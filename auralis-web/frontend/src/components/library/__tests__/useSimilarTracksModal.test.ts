/**
 * useSimilarTracksModal close keeps the mount gate (#5397)
 *
 * CozyLibraryView mounts SimilarTracksModal while `similarTrackId` is set.
 * The close handler used to clear it together with `open`, which unmounted
 * the modal before MUI's exit transition could run.
 */

import { describe, it, expect, vi } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useSimilarTracksModal } from '../useSimilarTracksModal';
import type { LibraryTrack } from '@/types/domain';

const tracks = [
  { id: 7, title: 'Roads' },
  { id: 8, title: 'Glory Box' },
] as LibraryTrack[];

describe('useSimilarTracksModal (#5397)', () => {
  it('is not mountable before the first open', () => {
    const { result } = renderHook(() => useSimilarTracksModal({ tracks, onPlayTrack: vi.fn() }));
    expect(result.current.similarTrackId).toBeNull();
    expect(result.current.similarTracksModalOpen).toBe(false);
  });

  it('closing flips only `open`, keeping the track for the exit transition', () => {
    const { result } = renderHook(() => useSimilarTracksModal({ tracks, onPlayTrack: vi.fn() }));

    act(() => result.current.handleFindSimilar(7));
    expect(result.current.similarTracksModalOpen).toBe(true);

    act(() => result.current.handleCloseSimilarTracksModal());
    expect(result.current.similarTracksModalOpen).toBe(false);
    expect(result.current.similarTrackId).toBe(7);
    expect(result.current.similarTrackTitle).toBe('Roads');
  });

  it('the next open replaces the retained track', () => {
    const { result } = renderHook(() => useSimilarTracksModal({ tracks, onPlayTrack: vi.fn() }));

    act(() => result.current.handleFindSimilar(7));
    act(() => result.current.handleCloseSimilarTracksModal());
    act(() => result.current.handleFindSimilar(8));

    expect(result.current.similarTracksModalOpen).toBe(true);
    expect(result.current.similarTrackId).toBe(8);
    expect(result.current.similarTrackTitle).toBe('Glory Box');
  });

  // #5660: handleFindSimilar reaches every library row, so a new identity per
  // render defeated the rows' memo on every page append and search keystroke.
  it('keeps handleFindSimilar identity across track-list changes and finds in the latest list', () => {
    const { result, rerender } = renderHook(
      ({ t }) => useSimilarTracksModal({ tracks: t, onPlayTrack: vi.fn() }),
      { initialProps: { t: tracks } }
    );
    const first = result.current.handleFindSimilar;

    rerender({ t: [...tracks, { id: 9, title: 'Overrated' } as LibraryTrack] });
    expect(result.current.handleFindSimilar).toBe(first);

    act(() => result.current.handleFindSimilar(9));
    expect(result.current.similarTrackTitle).toBe('Overrated');
  });
});

describe('useSimilarTracksModal playing a similar track (#5888)', () => {
  it('plays a track from the host list with that row', () => {
    const onPlayTrack = vi.fn();
    const { result } = renderHook(() => useSimilarTracksModal({ tracks, onPlayTrack }));

    act(() => result.current.handlePlaySimilarTrack(8));

    expect(onPlayTrack).toHaveBeenCalledWith(tracks[1]);
  });

  it('still plays a similar track that is not in the host view\'s loaded list', () => {
    const onPlayTrack = vi.fn();
    const { result } = renderHook(() => useSimilarTracksModal({ tracks, onPlayTrack }));

    act(() => result.current.handlePlaySimilarTrack(4242)); // library-wide hit, not on this page

    expect(onPlayTrack).toHaveBeenCalledWith({ id: 4242 });
  });
});
